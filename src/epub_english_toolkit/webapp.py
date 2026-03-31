from __future__ import annotations

from contextlib import asynccontextmanager
import secrets
from datetime import date
from pathlib import Path
import re
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .services import create_study_pack, get_progress_summary, get_today_plan, import_book, list_books, list_packs, load_pack
from .storage import ensure_dir
from .tracking import set_item_status
from .web_db import create_upload_job, get_upload_job, init_db, list_upload_jobs, update_upload_job
from .web_settings import WebSettings, load_web_settings

try:
    import multipart  # type: ignore  # noqa: F401

    HAS_MULTIPART = True
except Exception:
    HAS_MULTIPART = False


def create_app(settings: WebSettings | None = None) -> FastAPI:
    settings = settings or load_web_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_runtime(settings)
        yield

    app = FastAPI(title="EPUB English Toolkit", lifespan=lifespan)
    templates = Jinja2Templates(directory=str(settings.templates_root))
    templates.env.globals["app_name"] = "EPUB English Toolkit"
    app.mount("/static", StaticFiles(directory=str(settings.static_root)), name="static")
    security = HTTPBasic(auto_error=False)

    def auth(request: Request, credentials: HTTPBasicCredentials | None) -> None:
        if not settings.basic_auth_username:
            return
        if credentials is None:
            raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Basic"})
        username_ok = secrets.compare_digest(credentials.username, settings.basic_auth_username)
        password_ok = secrets.compare_digest(credentials.password, settings.basic_auth_password)
        if not (username_ok and password_ok):
            raise HTTPException(status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Basic"})

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard", status_code=302)

    @app.get("/dashboard")
    def dashboard(request: Request, credentials: HTTPBasicCredentials | None = Depends(security)):
        auth(request, credentials)
        today = date.today()
        context = {
            "request": request,
            "today": today.isoformat(),
            "today_plan": get_today_plan(settings.packs_root, settings.tracker_path, today),
            "progress": get_progress_summary(settings.packs_root, settings.tracker_path),
            "books": list_books(settings.library_root)[:12],
            "packs": list_packs(settings.packs_root, settings.tracker_path)[:12],
            "jobs": list_upload_jobs(settings.database_path, limit=12),
        }
        return templates.TemplateResponse("dashboard.html", context)

    @app.get("/upload")
    def upload_form(request: Request, credentials: HTTPBasicCredentials | None = Depends(security)):
        auth(request, credentials)
        return templates.TemplateResponse(
            "upload.html",
            {
                "request": request,
                "today": date.today().isoformat(),
                "default_mode": settings.default_mode,
                "default_focus_topics": settings.default_focus_topics,
                "upload_enabled": HAS_MULTIPART,
            },
        )

    if HAS_MULTIPART:

        @app.post("/upload")
        async def upload_epub(
            request: Request,
            background_tasks: BackgroundTasks,
            file: UploadFile = File(...),
            start_date: str = Form(...),
            mode: str = Form("ielts"),
            focus_topics: str = Form("politics,business,culture"),
            main_count: int = Form(2),
            short_count: int = Form(3),
            credentials: HTTPBasicCredentials | None = Depends(security),
        ):
            auth(request, credentials)
            if not file.filename or not file.filename.lower().endswith(".epub"):
                raise HTTPException(status_code=400, detail="Please upload an .epub file.")

            original_name = Path(file.filename).name
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", original_name)
            upload_path = settings.uploads_root / f"{date.today().isoformat()}-{secrets.token_hex(4)}-{safe_name}"
            ensure_dir(upload_path.parent)
            content = await file.read()
            upload_path.write_bytes(content)

            job_id = create_upload_job(
                settings.database_path,
                filename=original_name,
                stored_path=str(upload_path),
                mode=mode,
                focus_topics=focus_topics,
                start_date=start_date,
                main_count=main_count,
                short_count=short_count,
            )
            background_tasks.add_task(process_upload_job, settings, job_id)
            return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)

    else:

        @app.post("/upload")
        async def upload_disabled(request: Request, credentials: HTTPBasicCredentials | None = Depends(security)):
            auth(request, credentials)
            raise HTTPException(status_code=503, detail="Upload support requires python-multipart to be installed.")

    @app.get("/jobs/{job_id}")
    def job_detail(job_id: int, request: Request, credentials: HTTPBasicCredentials | None = Depends(security)):
        auth(request, credentials)
        job = get_upload_job(settings.database_path, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        pack = load_pack(settings.packs_root, job["pack_id"], settings.tracker_path) if job.get("pack_id") else None
        return templates.TemplateResponse(
            "job_detail.html",
            {
                "request": request,
                "job": job,
                "pack": pack,
            },
        )

    @app.get("/packs/{pack_id}")
    def pack_detail(pack_id: str, request: Request, credentials: HTTPBasicCredentials | None = Depends(security)):
        auth(request, credentials)
        pack = load_pack(settings.packs_root, pack_id, settings.tracker_path)
        return templates.TemplateResponse("pack_detail.html", {"request": request, "pack": pack})

    @app.get("/progress/update")
    def update_progress(
        request: Request,
        item_id: str,
        kind: str,
        pack_id: str = "",
        status: str = "completed",
        note: str = "",
        next_url: str = "/dashboard",
        credentials: HTTPBasicCredentials | None = Depends(security),
    ):
        auth(request, credentials)
        set_item_status(settings.tracker_path, item_id, status, kind=kind, pack_id=pack_id or None, note=note)
        return RedirectResponse(url=next_url or "/dashboard", status_code=303)

    return app


def init_runtime(settings: WebSettings) -> None:
    ensure_dir(settings.data_root)
    ensure_dir(settings.uploads_root)
    ensure_dir(settings.library_root)
    ensure_dir(settings.packs_root)
    ensure_dir(settings.tracker_path.parent)
    init_db(settings.database_path)


def process_upload_job(settings: WebSettings, job_id: int) -> None:
    job = get_upload_job(settings.database_path, job_id)
    if not job:
        return
    try:
        update_upload_job(settings.database_path, job_id, status="processing", error_message="")
        import_result = import_book(Path(job["stored_path"]), settings.library_root)
        focus_topics = [item.strip() for item in job["focus_topics"].split(",") if item.strip()]
        pack_result = create_study_pack(
            book_id=import_result["book_id"],
            library_root=settings.library_root,
            packs_root=settings.packs_root,
            start_date=date.fromisoformat(job["start_date"]),
            focus_topics=focus_topics,
            main_count=int(job["main_count"]),
            short_count=int(job["short_count"]),
            mode=job["mode"],
        )
        update_upload_job(
            settings.database_path,
            job_id,
            status="completed",
            book_id=import_result["book_id"],
            pack_id=pack_result["pack_id"],
        )
    except Exception as exc:
        update_upload_job(settings.database_path, job_id, status="failed", error_message=str(exc))


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("epub_english_toolkit.webapp:app", host="0.0.0.0", port=8000, reload=False)
