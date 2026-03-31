# EPUB English Toolkit

一个面向 `EPUB -> 英语学习流程` 的轻量工具箱。它把周刊或新闻类 `epub` 文件转换成可以持续复用的学习材料，重点支持：

- 导入文章库
- 自动挑选精读和泛读文章
- 自动生成口语、写作、词块和复习任务
- 自动输出某一天的学习清单

当前版本完全基于 Python 标准库，不依赖第三方包。

新增能力：

- 完成状态追踪
- 难度评分
- Web 仪表盘
- Markdown 导出
- TTS 文本导出，可选 Windows `wav` 语音合成
- Anki TSV 导出
- Notion CSV 导出
- IELTS 模式学习包

## 目录结构

```text
data/
  library/
    <book-id>/
      book.json
      articles.json
  study_packs/
    <pack-id>/
      pack.json
src/
  epub_english_toolkit/
```

## 快速开始

在工作区根目录运行：

```powershell
python study_tool.py import-epub --epub "D:\BaiduSyncdisk\英语\TE\2026\TE-2026-03-21 - caixinshop.epub"
python study_tool.py make-study-pack --book-id te-2026-03-21 --start-date 2026-03-31 --focus-topics politics business culture --mode ielts
python study_tool.py daily-plan --date 2026-03-31
python study_tool.py progress-report
```

## 命令说明

### `import-epub`

把一个 `epub` 文件导入成结构化文章库。

输出：

- `book.json`：书籍级元数据
- `articles.json`：文章列表和正文段落

### `make-study-pack`

根据一本已导入的书生成一周学习包。

生成内容包括：

- 2 篇精读文章
- 3 篇短文章
- 每天的阅读任务
- 每篇文章的口语任务
- 每篇文章的写作任务
- 词块候选
- 第 0 / 1 / 3 / 7 / 14 天复习安排
- 每篇文章难度评分

可选：

- `--mode general`
- `--mode ielts`

### `daily-plan`

汇总某一天要学的新内容和应复习的内容。

### `set-status`

标记学习任务或复习任务是否完成。

```powershell
python study_tool.py set-status --id "te-2026-03-21-2026-03-31:study:1" --kind study --pack-id te-2026-03-21-2026-03-31
```

### `progress-report`

给出当前学习包数量、任务数、预估口语训练时长和写作任务数。

### 导出命令

```powershell
python study_tool.py export-pack-markdown --pack-id te-2026-03-21-2026-03-31
python study_tool.py export-daily-markdown --date 2026-03-31
python study_tool.py export-anki --pack-id te-2026-03-21-2026-03-31
python study_tool.py export-notion --pack-id te-2026-03-21-2026-03-31
python study_tool.py export-tts --pack-id te-2026-03-21-2026-03-31
python study_tool.py export-tts --pack-id te-2026-03-21-2026-03-31 --audio
```

默认输出目录：

- `exports/markdown`
- `exports/anki`
- `exports/notion`
- `exports/tts`

## Web 版

运行本地 Web 版：

```powershell
python run_web.py
```

默认访问：

```text
http://127.0.0.1:8000
```

Web 版支持：

- 上传 EPUB
- 后台生成学习包
- 今日学习面板
- 完成状态按钮
- 进度展示

服务器部署请看：

- [服务器部署说明书.md](D:/BaiduSyncdisk/英语/TE/英语学习代码/服务器部署说明书.md)

## 推荐使用方式

每周运行一次：

1. 导入新的 `epub`
2. 生成一个新的学习包
3. 每天打开 `daily-plan`
4. 学完后把口语录音和作文保存在你自己的笔记系统里

## 当前版本的边界

- 词汇抽取目前是启发式规则，还不是语言学级别分析
- 文章难度是启发式分数，不等于正式 CEFR 测评
- TTS 音频导出依赖 Windows 本地语音
- Notion/Anki 目前是导出文件，不是实时同步
- 在同步盘目录下偶尔会出现残留 `.tmp` 文件，一般不影响使用

这些都适合放进下一阶段优化里。
