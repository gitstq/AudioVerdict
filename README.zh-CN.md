<div align="center">

# 🎧 AudioVerdict

**把任意音频文件，变成 AI 智能体能读懂的证据。**

零依赖 · 纯离线 · 只用 Python 标准库

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![依赖](https://img.shields.io/badge/第三方依赖-0-brightgreen.svg)](#-快速开始)
[![协议](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![测试](https://img.shields.io/badge/测试-53%20通过-brightgreen.svg)](#-贡献指南)

🌐 **语言**：[English](README.md) · **简体中文** · [繁體中文](README.zh-TW.md)

</div>

---

## 🎉 一、项目介绍

AI 编程智能体能读你的源码、读你的日志、读你的堆栈——但你丢给它一个音频文件，它就瞎了。它只看到 `interview_take3.m4a`、4.2 MB，然后什么都说不出来。它不知道这个文件有没有削波，不知道两条录音是不是被人接在了一起，不知道它到底是不是像需求里写的那样"在安静房间里录的"，也不知道那份号称"48 kHz 无损母带"的文件，其实是不是有人把 128 kbps 的 MP3 重新套了个壳。

**AudioVerdict 补的就是这个缺口。** 它在本地把音频文件读一遍，输出一份结构化、可解释的证据包：实测的声学特征、说人话的听感描述、带严重度和置信度的篡改线索，以及一张评分卡——可以导出成 JSON、Markdown、纯文本，或者一个自带样式的 HTML 页面。

> **核心思路**：AudioVerdict 不是替人类听众去"评价"一段声音好不好听，而是用 AI 能推理的语言——数字、严重度、时间区间、证据文本——把声音"描述"出来，让智能体自己下判断。

全部计算跑在 CPU 上、跑在当前进程里，**不依赖任何第三方包**。没有 NumPy，没有 SciPy，没有 librosa，不用下载模型，不发网络请求，不需要 API Key。`pip install` 完就能在一台断网的机器上干活。

### 它从哪里来

开源项目 [`earshot`](https://github.com/Leonxlnx/earshot)（3.3k+ star）带火了"给编程智能体装上耳朵"这个方向。AudioVerdict 顺着同一个方向走，但造的是另一把尺子：

| | `earshot` 一类项目 | **AudioVerdict** |
|---|---|---|
| 输出形态 | 面向对话的会话式摘要 | 带类型的证据对象：特征 + 线索 + 评分卡 + 时间轴 |
| 关注点 | 帮智能体听见"此刻正在发生什么" | 帮智能体审查"这个文件里到底有什么" |
| 取证能力 | 不是重点 | 一等公民：拼接点、转码链、上采样、容器异常 |
| 技术栈 | 依赖外部音频库 | 零依赖，DSP 全部手写 |
| 确定性 | 视实现而定 | 同一文件 → 同一指纹，每次、每台机器都一致 |

AudioVerdict 是独立自研的实现，没有复制任何现有项目的代码，只借鉴了产品方向。

---

## ✨ 二、核心特性

### 🔬 完整信号分析，全部手写实现
- **基 2 Cooley–Tukey FFT**、实输入 FFT、Hann / Hamming / Blackman 窗、DCT-II、任意重采样——手写，不用 NumPy。
- **响度**：BS.1770-4 K 计权（高架 + 高通双二阶滤波器）、带门控的综合 LUFS、响度范围。
- **真峰值 dBTP**：4 倍过采样插值，这项指标才真正预示采样间削波。
- **频谱描述子**：质心、扩展度、滚降、平坦度、通量、9 频段能量分布、频谱对比度、以及带"悬崖检测"的高频截止点。
- **MFCC**：26 个 Mel 滤波器 → 13 个倒谱系数，含 Mel 标度换算。
- **基频**：YIN 算法（累积均值归一化差 + 抛物线插值），附带谐波度与有声比例。
- **节奏**：基于自相关的 BPM 估计，并生成节拍网格。

### 🕵️ 带证据的取证线索
每条线索都带 `code`、`severity`、`confidence`、可选的时间区间和一段 `detail` 说明，方便智能体筛选、排序、采取行动：

| 代码 | 抓的是什么 |
|---|---|
| `splice_candidates` | 电平或频谱突变，暗示两条录音被接在一起 |
| `digital_silence` | 全零静音段——这是剪辑的指纹，不是房间的声音 |
| `clipping` | 样本顶在满刻度上 |
| `over_compressed` | 波峰因数对这类内容而言过低 |
| `upsampled_source` | 远低于奈奎斯特频率的陡峭高频悬崖——低采样率源被重新存成高采样率 |
| `bandwidth_shortfall` | 陡峭截止点与声明的采样率不符 |
| `transcode_into_lossless` | "无损"容器里藏着有损编码痕迹（比如 MP3 → WAV） |
| `noise_floor_shift` | 底噪在段落间发生变化——换了房间，换了条录音 |
| `container_anomaly` | 帧链断裂、Xing/VBRI 头错误、FLAC 帧号非单调、Ogg 页序错乱 |
| `xing_mismatch` | MP3 声明的帧数与实际帧链对不上 |
| `unknown_source_md5` | FLAC 存有原始 PCM 的 MD5——对不上就说明编码之后音频被改过 |
| `dc_offset` | 直流偏置，廉价麦克风的老毛病 |
| `no_faststart` | MP4 的 `moov` 排在 `mdat` 后面——渐进式播放会失败 |

### 📦 容器取证：六种格式，无需解码器
AudioVerdict 直接解析容器结构，所以**一个 100 MB 的文件，读几千字节就能查完**：

| 格式 | 校验内容 |
|---|---|
| **WAV**（RIFF） | PCM 8/16/24/32 位、float32/64、µ-law/A-law、`LIST`/`INFO`、广播 `bext` |
| **AIFF / AIFF-C** | 80 位扩展浮点采样率、`COMM`/`SSND` 布局 |
| **FLAC** | `STREAMINFO`、原始 PCM 的 MD5、Vorbis 注释、完整帧链遍历 |
| **MP3** | 帧链遍历、Xing / Info / VBRI 头、VBR 与填充统计、ID3v1/v2 |
| **Ogg** | Vorbis / Opus / Ogg-FLAC 识别、颗粒位置、序列号、页序连续性 |
| **MP4 / M4A** | 完整 atom 树遍历、`mvhd`/`mdhd`/`stsd`/`mp4a`、iTunes `ilst` 标签、faststart 检查 |

### 🔑 内容指纹
地标哈希指纹（`AVD-landmark-v1`）：对数频带的频谱峰值两两配对成地标，再用 FNV-1a 摘要。两个文件可以**不必完整解码**就比对是否近似重复——特别适合回答"这是不是我已经审过的那条录音？"

### 🎼 内容分类与描述校验
- 把内容分成 `speech` / `music` / `ambience` / `tone` / `noise` / `silence`，给出概率分布和判定理由。
- 用六条独立线索（全零静音、频谱过度平滑、空气感缺失、基频异常稳定、底噪缺失、电平静止）估计**合成可能性**分数。
- **`--describe`** 可以拿一段自由文本的需求去对照文件——"低沉男声独白"、"温暖女声旁白，安静室内"——然后报告哪些说法和实测数据对不上。词库支持中英文。

### 📝 自然语言输出
手工生成的听感笔记（中 / 英），覆盖响度、动态、音色、带宽、基频、节奏、底噪和失真。另外还能渲染**波形图、对数频谱图、特征时间轴 SVG**——纯手写绘制，不用绘图库，直接内联进 HTML 报告。

### 🖥️ 四种报告格式
`json`（对智能体友好）· `markdown`（对评审友好）· `text`（对终端友好）· `html`（自包含，无外部资源）

---

## 🚀 三、快速开始

### 环境要求

| 项目 | 要求 |
|---|---|
| Python | **3.8 及以上**（已在 3.8 – 3.13 验证） |
| 运行时依赖 | **无** |
| 操作系统 | Windows、macOS、Linux——纯 Python，无原生扩展 |
| 可选项 | `PATH` 上有 `ffmpeg`——**仅**在需要把压缩格式（MP3/OGG/M4A/FLAC）解码成 PCM 时才用得上。没有它，容器取证和结构性分析照常输出。 |

### 安装

```bash
# 从仓库安装
git clone https://github.com/gitstq/AudioVerdict.git
cd AudioVerdict
pip install -e .

# 验证
audioverdict --version
```

也可以什么都不装直接跑：

```bash
PYTHONPATH=src python3 -m audioverdict --help
```

> `pip install -e .` 除了拉取 `setuptools` 之外不需要联网，**没有任何第三方运行时包**要下载。

### 30 秒上手

```bash
# 生成一段合成音频并完整分析一遍（自检）
audioverdict selftest

# 分析一个真实文件
audioverdict analyze interview.m4a

# 输出 Markdown，并拿需求描述去对照文件
audioverdict analyze take3.flac --format markdown \
  --describe '低沉男声独白，安静室内录制' --out report.md

# 只要取证线索，JSON 格式
audioverdict verify evidence.wav --format json

# 这两个文件是同一段内容吗？
audioverdict compare a.wav b.wav

# 扫整个目录
audioverdict batch ./takes --format json --out takes.json
```

### 当成库用

```python
from audioverdict import analyse_file
from audioverdict.report import render

result = analyse_file("interview.m4a")

print(result.classification["label"])             # 'speech'
print(result.scorecard["overall"])                # 82.4
print(result.global_features.loudness_lufs)       # -18.7

for f in result.findings:
    if f.severity == "high":
        print(f.code, f.confidence, f.detail, f.evidence)

print(render(result, fmt="text", lang="zh"))      # 一屏速览
print(result.as_dict())                           # JSON 结构直接拿
```

一次调用返回 `AnalysisResult`，里面有 `container`、`global_features`、`timeline`、`notes`、`segments`、`findings`、`classification`、`scorecard`、`fingerprints` 和 `warnings`。`result.as_dict()` 直接给出 JSON 结构；`render(result, fmt=...)` 把它渲染成 `json`、`text`、`markdown` 或 `html`。

---

## 📖 四、详细使用指南

### 4.1 命令行一览

```
audioverdict <子命令> [选项] <路径>
```

| 子命令 | 作用 |
|---|---|
| `analyze`（别名 `analyse`） | 单文件完整分析 |
| `describe` | 输出一段自然语言描述 |
| `fingerprint` | 只算内容指纹（快，不整段解码） |
| `compare` | 按指纹比对两个文件 |
| `verify` | 只输出取证线索 |
| `batch` | 分析目录下所有音频文件 |
| `selftest` | 生成合成音频并分析——用来验证安装没问题 |

`analyze` / `verify` / `describe` 的通用选项：

| 选项 | 默认值 | 含义 |
|---|---|---|
| `--format` | `text` | `json`、`text`、`markdown`、`html` |
| `--describe TEXT` | – | 用来对照音频的自由文本需求（中英文均可） |
| `--out PATH` | 标准输出 | 把报告写到文件 |
| `--window SEC` | `1.0` | 分析窗长（秒） |
| `--hop SEC` | `0.5` | 窗之间跳距（秒） |
| `--max-windows N` | `400` | 分析窗数量上限（控制长音频耗时） |
| `--lang` | `en` | `en` 或 `zh`——笔记与摘要的语言 |

### 4.2 怎么选输出格式

```bash
# 给 LLM / 智能体流水线：稳定、带类型、信息完整
audioverdict analyze take.wav --format json --out take.json

# 给代码评审、PR 评论或工单
audioverdict analyze take.wav --format markdown --out take.md

# 给人用浏览器打开：自包含、内联 SVG、可离线
audioverdict analyze take.wav --format html --out take.html

# 给终端 / CI 日志
audioverdict analyze take.wav
```

### 4.3 怎么读 JSON

```jsonc
{
  "path": "take.wav",
  "container": { "format": "WAV", "codec": "PCM", "sample_rate": 44100,
                 "channels": 1, "lossy": false, "pcm_decoded": true },
  "global_features": { "loudness_lufs": -18.7, "peak_dbfs": -1.2,
                       "spectral_centroid": 1840.2, "clipping_ratio": 0.0 },
  "timeline": [ /* 每个窗的特征，带 start/end */ ],
  "notes":    [ /* 人能读的听感笔记 */ ],
  "segments": [ /* 值得回听的高亮片段 */ ],
  "findings": [
    { "code": "clipping", "severity": "high", "confidence": 0.93,
      "title": "检测到削波",
      "detail": "2.68% 的样本顶在满刻度。峰值 -0.1 dBFS ……",
      "evidence": { "clipping_ratio": 0.0268, "crest_factor": 1.93,
                    "windows": [12.0, 12.5, 13.0, 13.5, 14.0, 14.5] } }
  ],
  "classification": { "label": "speech", "confidence": 0.81,
                      "probabilities": { "speech": 0.81, "music": 0.12 },
                      "reasons": ["……"], "voiced_ratio": 0.74 },
  "scorecard": {
    "overall": 82.4, "grade": "B",
    "quality":       { "score": 71.0, "notes": [] },
    "authenticity":  { "score": 90.5, "probability": 0.08,
                       "verdict": "likely recorded", "cues": [] },
    "usability":     { "score": 88.0, "decoded": true, "duration": 62.5 },
    "tempo":         { "bpm": 96.0, "confidence": 0.62, "beats": [0.02, ……] },
    "content":       { "label": "speech", "confidence": 0.81, "……": "……" },
    "headline": "B (82.4/100) - speech, likely recorded"
  },
  "fingerprints": [ { "algo": "AVD-landmark-v1", "value": "……" } ],
  "warnings": [],
  "summary": "综合响度 -18.7 LUFS ……"
}
```

严重度分 `info` < `low` < `medium` < `high`。先按 `severity` 过滤，再看 `confidence`。时间位置放在每条线索的 `evidence` 对象里（比如拼接的 `points`、全零静音的 `times`、削波的 `windows`），而不是线索的顶层字段。

### 4.4 库接口

```python
from audioverdict import analyse_file, read_audio, detect_format, SUPPORTED

# —— 廉价的结构性扫描：不整段解码 ——
fmt = detect_format("huge_concert.flac")          # 'flac'
audio = read_audio("huge_concert.flac", max_bytes=2_000_000)
print(audio.sample_rate, audio.channels, audio.duration_seconds)

# —— 完整分析 ——
r = analyse_file("huge_concert.flac", window=2.0, hop=1.0, lang="zh")

# —— 指纹 / 近似重复检测 ——
from audioverdict.analysis.fingerprint import fingerprints, compare
a = fingerprints("take_a.wav")
b = fingerprints("take_b.wav")
print(compare(a, b))   # {"similarity": 0.87, ...}

# —— 把结果渲染成任意格式的字符串 ——
from audioverdict.report import render
md = render(r, fmt="markdown", lang="zh")
```

### 4.5 喂给智能体

AudioVerdict 生来就是要被塞进 prompt 里的。实践下来最管用的姿势：

```python
import subprocess

report = subprocess.run(
    ["audioverdict", "analyze", path, "--format", "json"],
    capture_output=True, text=True, check=True).stdout

prompt = f"""
这是用户刚丢给我们的音频文件的实测报告。
把 severity 为 high 的 findings 当作阻塞问题，优先说明。
谈响度、带宽时一律引用 `global_features` 里的数字，不要自己猜。
解释问题时引用该条线索的 `evidence` 对象。

{report}

现在回答用户关于这段音频的问题。
"""
```

报告是确定性的，同一个文件永远产出同一份证据——智能体的行为因此可复现、可测试。

### 4.6 格式支持一览

| 容器 | 扩展名 | 不装 ffmpeg 能解 PCM | 容器取证 |
|---|---|---|---|
| WAV / RIFF | `.wav`、`.wave` | ✅ | ✅ |
| AIFF / AIFF-C | `.aif`、`.aiff`、`.aifc` | ✅ | ✅ |
| FLAC | `.flac` | ❌（需 ffmpeg） | ✅ |
| MP3 | `.mp3` | ❌（需 ffmpeg） | ✅ |
| Ogg | `.ogg`、`.oga`、`.opus` | ❌（需 ffmpeg） | ✅ |
| MP4 / M4A | `.m4a`、`.mp4` | ❌（需 ffmpeg） | ✅ |

拿不到 PCM 时，AudioVerdict 会静默降级为**仅容器报告**：格式、编码、时长、码率、结构异常与完整性检查照样输出，并在 `warnings` 里说明跳过了什么。它不会在解不了的格式上崩掉。

### 4.7 性能提示

- 内部分析统一重采样到 **44.1 kHz**。128 kbps 的 MP3 在 16 kHz 附近就断了，这个悬崖本身就是证据——不能先降采样把它抹掉。
- `--max-windows`（默认 400）限制长录音的工作量：按默认窗长跳距大约是前 200 秒。整段访谈就调大，CI 快速检查就调小。
- 容器解析是惰性且有上限的：`read_audio(..., max_bytes=...)` 只读文件头部。
- 2048 点的纯 Python FFT 足够交互式使用；小时级长音频建议用 `verify`（只要线索）或调大 `--hop`。

---

## 💡 五、设计思路与迭代规划

### 5.1 几个值得说清楚的决定

**为什么坚持零依赖？**
一个要拖 200 MB 科学计算栈的音频工具，进不了 CI 容器，进不了锁死的企业笔记本，也进不了智能体沙箱。这里每一个算法——FFT、K 计权、YIN、Mel 滤波器、指纹——都是直接实现的。代价是几千行 DSP 代码，收益是 `pip install` 永不失败、输出在任何机器上逐字节一致。

**为什么给"证据"而不是"评价"？**
"听起来发闷"对智能体毫无用处。`spectral_centroid 1180 Hz，高频截止 6.2 kHz，findings: bandwidth_shortfall (high)` 才可执行。AudioVerdict 永远同时给出测量值、置信度和推理过程，判断权留给调用方。

**为什么解析容器而不是解码音频？**
取证线索大多藏在容器里。FLAC 存着原始 PCM 的 MD5——和解码结果对不上，文件就被改过。MP3 在 Xing 头里声明帧数——和帧链对不上，流就被剪过或接过。这些都不需要解码几个 GB 的样本。

**为什么内部分析率定在 44.1 kHz？**
因为转码检测依赖看到编码器留下的高频悬崖，一旦先降采样，悬崖就没了。就这一个改动，区分了"查不出来"和"这个 48 kHz WAV 其实是 128 kbps 的 MP3"。

**为什么手写 SVG？**
这样 HTML 报告就是零外部请求的单文件——能离线打开、能邮件发送、能归档，也能安全地在沙箱预览里渲染。

### 5.2 迭代规划

| 版本 | 主题 | 计划内容 |
|---|---|---|
| **v1.1** | 更深取证 | ENF（电网频率）分析、从失真指纹反推编码器族、重采样器识别 |
| **v1.2** | 更多格式 | 裸 OBS 帧的 Opus、WavPack、Monkey's Audio、ADTS AAC、Matroska 音频 |
| **v1.3** | 提速 | 可选的 NumPy 快路径（仅在 NumPy 存在时启用，数值结果完全一致）；批量模式多进程化 |
| **v1.4** | 智能体易用性 | 提供 MCP server，让智能体能把 `analyse_audio` 当工具调用；母带前后对比的 `.wav` diff 模式 |
| **v2.0** | 轻量说话人分离 | 说话人轮次切分与逐人响度统计，仍然全程离线 |
| **更远** | 打包形态 | Windows / macOS / Linux 的单文件可执行版本 |

想法和 PR 都欢迎，见 [🤝 贡献指南](#-七-贡献指南)。

---

## 📦 六、打包与部署指南

AudioVerdict 是一个 **Python 库 + 命令行工具**，不是桌面应用，因此没有安装包可下载、也没有平台二进制要发布——在要运行它的环境里从源码安装即可。

### 6.1 装进项目

```bash
pip install -e .            # 可编辑模式，开发用
pip install .               # 常规安装
```

两种方式都会提供两个命令行入口：`audioverdict` 和短别名 `avd`。

### 6.2 隔离环境

```bash
# venv（推荐）
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 或者 uv
uv venv && uv pip install -e .

# 或者 conda
conda create -n avd python=3.11 && conda activate avd && pip install -e .
```

### 6.3 构建可分发的 wheel / sdist

```bash
pip install --upgrade build
python -m build            # -> dist/audioverdict-1.0.0-py3-none-any.whl
```

产出的 wheel 是 `py3-none-any`：纯 Python，无 ABI 标签，所有平台、所有 ≥3.8 的解释器通吃。装到任何地方都是一句：

```bash
pip install dist/audioverdict-1.0.0-py3-none-any.whl
```

### 6.4 Docker / CI

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
# 可选：只有需要把 MP3/OGG/FLAC/M4A 解码成 PCM 时才装
# RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["audioverdict"]
```

```bash
docker build -t audioverdict .
docker run --rm -v "$PWD:/data" audioverdict analyze /data/take.wav --format json
```

### 6.5 嵌进你自己的工具

因为没有运行时依赖，AudioVerdict 可以直接被内联 vendored：把 `src/audioverdict/` 这个包目录拷进你的项目，直接 import。改不动你的 `requirements.txt`，也没有依赖冲突风险。

```python
# your_package/audio.py
from audioverdict import analyse_file
```

### 6.6 可选：单文件可执行程序

本项目属于库/CLI 类，不作为 Release 产物发布桌面二进制；但如果你确实需要在没装 Python 的机器上跑，可以自己打一个：

```bash
pip install pyinstaller
pyinstaller --onefile --name audioverdict src/audioverdict/__main__.py
# -> dist/audioverdict
```

### 6.7 环境变量

一个都不需要。AudioVerdict 不读任何配置，不往你传入的路径之外写任何东西，也不发起任何网络请求。

---

## 🤝 七、贡献指南

真心欢迎 contributions，尤其是新容器格式和新的取证检查。

### 7.1 搭环境

```bash
git clone https://github.com/gitstq/AudioVerdict.git
cd AudioVerdict
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt     # 只有一个 pytest
```

### 7.2 跑测试

```bash
pytest                      # 53 个测试
pytest -q                   # 安静模式
pytest tests/test_dsp.py -v # 单个模块
```

干净检出下 53 个测试全绿。测试自己合成信号（纯音、噪声、静音、拼接、削波），所以**你不需要准备任何示例音频**就能跑。

### 7.3 提 PR 之前

```bash
pytest                                  # 必须全绿
python -m audioverdict selftest         # 必须干净跑完
```

### 7.4 提交规范

本项目遵循 [Angular / Conventional Commits](https://www.conventionalcommits.org/) 风格：

| 前缀 | 用途 |
|---|---|
| `feat:` | 新能力 |
| `fix:` | 修 bug |
| `docs:` | 只改文档 |
| `refactor:` | 重构，行为不变 |
| `test:` | 只动测试 |
| `chore:` | 工具、打包、CI |

示例：`feat: 新增 WavPack 容器解析`、`fix: 修正 MP4 读取中 stsd 采样率偏移`、`docs: 补充中文 README`。

### 7.5 可以从哪里入手

- **新格式** —— WavPack、APE、ADTS AAC、Matroska 音频。在 `src/audioverdict/decode/` 里实现 `read_<格式>()`，到 `decode/__init__.py` 注册，再补测试。
- **新取证检查** —— 加到 `src/audioverdict/analysis/forensics.py`。每条线索都要有 `code`、`severity`、`confidence`，以及一段引用了具体数字的 `detail`。
- **误报** —— 这是最有价值的 bug 报告。如果 AudioVerdict 把干净的音频判出问题，请带上文件（或一段能复现的合成信号）和预期结论开 issue。
- **翻译** —— 笔记与摘要文案在 `src/audioverdict/analysis/notes.py`；词库在 `analysis/match.py`，已覆盖中文与英文。欢迎更多语言。

### 7.6 几条硬规矩

- **保持零依赖。** 加运行时依赖的 PR 不会合，除非它是可选的且理由充分。
- **保持确定性。** 同样输入永远得到同样输出。
- **坏文件不许崩。** 降级到仅容器模式，并记一条 warning。

---

## 📄 八、开源协议说明

本项目以 **MIT License** 发布，详见 [LICENSE](LICENSE)。

```
Copyright (c) 2026 gitstq

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**使用须知**

- AudioVerdict 测量的是信号属性。它**不是**测谎仪，也**不是**法律意义上的篡改证明——所有线索都是概率性证据，值得人工复核。
- 一切都在本地跑。你的音频不会离开你的机器，因为这个项目里压根没有网络代码。
- 合成可能性评分对"处理很重但完全诚实"的素材（播客后期链、修复老录音）可能误报。请把它当成"值得再听一遍"的提示，而不是结论。

---

<div align="center">

**AudioVerdict** —— 让你的智能体有一双能拿出依据的耳朵。

🌐 [English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

</div>
