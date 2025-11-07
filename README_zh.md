# Meeting Summary（视频 → Whisper → Ollama）

🌐 [English README](README.md) | 中文

轻量级工具集：将会议视频转换为文字记录，并使用本地 Ollama 模型生成结构化的 Markdown 摘要。工具包含分阶段的命令行模块，以及一个简洁的 Flask Web 界面，支持一键/编程式流水线。

<p align="center">
	<img src="readme-img/zh-empty.png" alt="UI" style="max-width:400px; height:auto; margin:12px 0;" />
</p>

## 主要特性
- 端到端流程：视频 → 音频（FFmpeg）→ 转写（Whisper）→ 总结（Ollama）。
- 各阶段可独立使用（extract、transcribe、summarize）。
- 支持 Whisper 语言提示；当存在分段信息时可导出 SRT。
- 自动对超长文本分块，并合并为单个 Markdown 摘要。
- 统一将产物输出到 `output/` 目录；可选 Flask Web UI + SSE 实时进度。
- 广泛支持主流音视频容器/编码格式。

## 环境要求
- Python 3.13+
- 已在 PATH 中可用的 [FFmpeg](https://ffmpeg.org/download.html)
- 本地运行的 [Ollama](https://ollama.com/download)，且已拉取所需模型（示例默认：`qwen3:30b-a3b`）
- 根据硬件选择合适的 Whisper 模型（CPU/GPU）

## 安装

以可编辑模式安装：

Windows CMD：
```cmd
pip install -e .
REM Web 界面（可选）
pip install -e ".[web]"
REM 开发工具（可选）
pip install -e ".[dev]"
```

或使用 uv：
```bash
uv pip install -e ".[dev,web]"
```

## 快速上手——完整流水线

处理一个会议视频（端到端）：
```bash
python -m meeting_summary path/to/meeting.mp4 -o output -w turbo -c 8000 -p "Focus on decisions and owners"
```

常用参数：
- `-o, --outdir`：输出目录（音频、转写、摘要）
- `-w, --whisper-model`：Whisper 检查点（如 tiny、base、small、medium、large、turbo）
- `-l, --language`：Whisper 语言提示（如 en、zh）
- `-m, --ollama-model`：本地 Ollama 模型名（内部前缀 `ollama/`）
- `-c, --context-length`：单次总结的最大字符数；设为 `0` 关闭分块
- `-p, --extra-prompt`：附加到总结提示词后的额外指令

`output/` 下的典型产物：
- `<stem>.wav` —— 提取的单声道音频
- `<stem>.transcript.txt` —— Whisper 原始转写
- `<stem>.srt` —— 字幕（若有分段数据）
- `<stem>.summary.md` —— Ollama 生成的最终 Markdown 摘要

### 支持的媒体格式

视频 ➜ 音频（容器）：
`mp4, mov, mkv, avi, webm, m4v, flv, 3gp, ts, vob, wmv, mpeg, mpg, m2ts, ogv`

音频 ➜ 转写：
`wav, mp3, aac, ogg, flac, m4a, wma, webm (audio-only), opus`

非 WAV 音频可在转写前可选转换为单声道 16kHz WAV，以获得更一致的结果：
可添加 `--auto-convert-wav`（CLI），或由 Whisper 原生解码处理。

若想简化 SRT 时间戳（去掉毫秒），添加 `--simple-srt-time`。

## 分阶段运行

仅提取音频：
```bash
python -m meeting_summary.extract_audio path/to/meeting.mp4 -o output --samplerate 16000
```

对已有音频进行转写：
```bash
python -m meeting_summary.transcribe path/to/meeting.wav -o output -w turbo -l en
python -m meeting_summary.transcribe path/to/audio.mp3 -o output -w turbo -l en --auto-convert-wav
```

对已有转写进行总结（可选分块与额外提示）：
```bash
python -m meeting_summary.summarize path/to/meeting.transcript.txt -o output -m qwen3:30b-a3b -c 6000 -p "Highlight risks"
```

当 `-c/--context-length > 0` 时，脚本会按上下文窗口大小将转写分块；对每块分别总结，再合并为一个带小节标题的 Markdown 文件。

## Web 服务（Flask）

启动 Web UI：
```bash
python -m meeting_summary.web
```

访问：http://localhost:8000/

根路径默认为英文界面。可通过 `?lang=zh|en`、Cookie 或 `Accept-Language` 选择语言。

主要 API：
- POST `/api/video-to-audio` —— 上传视频，返回 `{audio_id, download_url}`
- GET `/api/download/audio/<audio_id>` —— 下载提取的 WAV
- GET `/api/download/transcript/<audio_id>` —— 下载转写（如有）
- GET `/api/download/srt/<audio_id>` —— 下载 SRT（如有）
- POST `/api/audio-to-transcript` —— 上传 WAV 或使用 `audio_id`；返回 `{transcript}`
- POST `/api/summarize` —— JSON 包含 `transcript`，可选 `ollama_model`、`context_length`、`extra_prompt`；返回 `{summary}`
- POST `/api/pipeline` —— 同步流水线；返回 `{audio_id, download_url, transcript, summary}`
- POST `/api/pipeline/start` —— 启动异步流水线；返回 `{job_id}`
- GET `/api/pipeline/events/<job_id>` —— 通过 SSE 订阅进度事件（`info/step/ok/error/done`）
- GET `/api/pipeline/result/<job_id>` —— 轮询最终结果/状态（`pending|error|done`）

SSE 示例：
```bash
curl -N http://localhost:8000/api/pipeline/events/<job_id>
```

注意：
- 上传文件与生成的产物保存在 `output/`（上传位于 `output/uploads/`）。
- 若在代理之后使用 SSE，请确保关闭缓冲（如设置 `X-Accel-Buffering: no`）。
- 生产部署请添加鉴权、限流与任务清理等。

## 提示词小技巧
- `--extra-prompt` 保持简洁、聚焦，通常能获得更稳定的总结质量。
- 若遇到上下文窗口限制或输出被截断，请启用分块。
- 生成的 Markdown 可用于 CI 后处理或导入笔记系统；格式相对稳定。

## 开发
- 可选使用 Ruff 进行格式化/静态检查：`python -m ruff check .` 和 `python -m ruff format .`
- `scripts/` 中的辅助脚本展示了如何以编程方式编排流水线。
- 欢迎贡献：欢迎提交 Issue 或 PR 改进项目。
