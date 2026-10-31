<div align="center">

# 🎧 AudioVerdict

**把任何音訊檔案，變成 AI 代理人讀得懂的證據。**

零依賴 · 全程離線 · 只用 Python 標準函式庫

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![依賴](https://img.shields.io/badge/第三方依賴-0-brightgreen.svg)](#-快速開始)
[![授權](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![測試](https://img.shields.io/badge/測試-53%20通過-brightgreen.svg)](#-貢獻指南)

🌐 **語言**：[English](README.md) · [简体中文](README.zh-CN.md) · **繁體中文**

</div>

---

## 🎉 一、專案介紹

AI 程式設計代理人讀得懂你的原始碼、你的 log、你的堆疊追蹤——但你丟一個音訊檔給它，它就瞎了。它只看到 `interview_take3.m4a`、4.2 MB，然後一句話都說不出來。它不知道這個檔案有沒有削波，不知道兩段錄音是不是被人接在一起，不知道它是否真的如需求所寫「在安靜房間裡錄的」，也不知道那份號稱「48 kHz 無損母帶」的檔案，其實是不是有人把 128 kbps 的 MP3 重新包了一層殼。

**AudioVerdict 補的就是這個洞。** 它在本機把音訊檔讀過一遍，輸出一份結構化、可解釋的證據包：實測的聲學特徵、說人話的聆聽筆記、帶嚴重程度與信心度的竄改線索，還有一張評分卡——可以匯出成 JSON、Markdown、純文字，或是一個自帶樣式的 HTML 頁面。

> **核心思路**：AudioVerdict 不是替人類聽眾去「評價」一段聲音好不好聽，而是用 AI 能推理的語言——數字、嚴重程度、時間區間、證據文字——把聲音「描述」出來，讓代理人自己下判斷。

所有運算都跑在 CPU 上、跑在當前的行程裡，**不依賴任何第三方套件**。沒有 NumPy，沒有 SciPy，沒有 librosa，不用下載模型，不發網路請求，不需要 API Key。`pip install` 完就能在一台斷網的機器上幹活。

### 它的由來

開源專案 [`earshot`](https://github.com/Leonxlnx/earshot)（3.3k+ star）帶紅了「替程式設計代理人裝上耳朵」這個方向。AudioVerdict 順著同一個方向走，但做的是另外一把尺：

| | `earshot` 這一類專案 | **AudioVerdict** |
|---|---|---|
| 輸出型態 | 面向對話的會話式摘要 | 帶型別的證據物件：特徵 + 線索 + 評分卡 + 時間軸 |
| 關注點 | 幫代理人聽見「此刻正在發生什麼」 | 幫代理人審查「這個檔案裡到底有什麼」 |
| 取證能力 | 不是重點 | 一等公民：接合點、轉碼鏈、升頻、容器異常 |
| 技術棧 | 依賴外部音訊函式庫 | 零依賴，DSP 全部手寫 |
| 確定性 | 視實作而定 | 同一檔案 → 同一指紋，每次、每台機器都一致 |

AudioVerdict 是獨立自研的實作，沒有複製任何既有專案的程式碼，只借鑑了產品方向。

---

## ✨ 二、核心特性

### 🔬 完整訊號分析，全部手寫實作
- **基數 2 Cooley–Tukey FFT**、實輸入 FFT、Hann / Hamming / Blackman 窗函數、DCT-II、任意重取樣——手寫，不用 NumPy。
- **響度**：BS.1770-4 K 加權（高架 + 高通雙二階濾波器）、帶閘門的綜合 LUFS、響度範圍。
- **真峰值 dBTP**：4 倍過取樣內插，這項指標才真正預示取樣間削波。
- **頻譜描述子**：質心、擴散度、滾降、平坦度、通量、9 頻段能量分布、頻譜對比度，以及帶「懸崖偵測」的高頻截止點。
- **MFCC**：26 個 Mel 濾波器 → 13 個倒頻譜係數，含 Mel 尺度轉換。
- **基頻**：YIN 演算法（累積均值正規化差 + 拋物線內插），附帶諧波度與有聲比例。
- **節奏**：基於自相關的 BPM 估測，並產生節拍網格。

### 🕵️ 帶證據的取證線索
每一條線索都帶 `code`、`severity`、`confidence`、可選的時間區間，以及一段 `detail` 說明，方便代理人篩選、排序、採取行動：

| 代碼 | 抓的是什麼 |
|---|---|
| `splice_candidates` | 電平或頻譜突然改變，暗示兩段錄音被接在一起 |
| `digital_silence` | 全零靜音段——這是剪接的指紋，不是房間的聲音 |
| `clipping` | 取樣點頂在滿刻度上 |
| `over_compressed` | 波峰因數對這類內容來說過低 |
| `upsampled_source` | 遠低於奈奎斯特頻率的陡峭高頻懸崖——低取樣率來源被重新存成高取樣率 |
| `bandwidth_shortfall` | 陡峭截止點與宣告的取樣率不符 |
| `transcode_into_lossless` | 「無損」容器裡藏著失真編碼的痕跡（例如 MP3 → WAV） |
| `noise_floor_shift` | 底噪在段落之間改變——換了房間，換了一條錄音 |
| `container_anomaly` | 訊框鏈斷裂、Xing/VBRI 標頭錯誤、FLAC 訊框編號非單調、Ogg 頁面順序錯亂 |
| `xing_mismatch` | MP3 宣告的訊框數與實際訊框鏈對不上 |
| `unknown_source_md5` | FLAC 存有原始 PCM 的 MD5——對不上就表示編碼之後音訊被動過 |
| `dc_offset` | 直流偏移，廉價麥克風的老毛病 |
| `no_faststart` | MP4 的 `moov` 排在 `mdat` 後面——漸進式串流會壞掉 |

### 📦 容器取證：六種格式，不需要解碼器
AudioVerdict 直接解析容器結構，所以**一個 100 MB 的檔案，讀幾 KB 就能查完**：

| 格式 | 校驗內容 |
|---|---|
| **WAV**（RIFF） | PCM 8/16/24/32 位元、float32/64、µ-law/A-law、`LIST`/`INFO`、廣播 `bext` |
| **AIFF / AIFF-C** | 80 位元擴充浮點取樣率、`COMM`/`SSND` 布局 |
| **FLAC** | `STREAMINFO`、原始 PCM 的 MD5、Vorbis 註解、完整訊框鏈走訪 |
| **MP3** | 訊框鏈走訪、Xing / Info / VBRI 標頭、VBR 與填充統計、ID3v1/v2 |
| **Ogg** | Vorbis / Opus / Ogg-FLAC 識別、granule 位置、序號、頁面順序連續性 |
| **MP4 / M4A** | 完整 atom 樹走訪、`mvhd`/`mdhd`/`stsd`/`mp4a`、iTunes `ilst` 標籤、faststart 檢查 |

### 🔑 內容指紋
地標雜湊指紋（`AVD-landmark-v1`）：對數頻帶的頻譜峰值兩兩配對成地標，再用 FNV-1a 摘要。兩個檔案**不必完整解碼**就能比對是否近似重複——特別適合回答「這是不是我已經審過的那一條錄音？」

### 🎼 內容分類與描述比對
- 把內容分成 `speech` / `music` / `ambience` / `tone` / `noise` / `silence`，給出機率分布與判定理由。
- 用六條獨立線索（全零靜音、頻譜過度平滑、空氣感缺失、基頻異常穩定、底噪缺失、電平靜止）估測**合成可能性**分數。
- **`--describe`** 可以拿一段自由文字的需求去對照檔案——「低沉男聲獨白」、「溫暖女聲旁白，安靜室內」——然後回報哪些說法與實測數據對不上。詞庫支援中文與英文。

### 📝 自然語言輸出
手工產生的聆聽筆記（繁中 / 簡中 / 英文），涵蓋響度、動態、音色、頻寬、基頻、節奏、底噪與失真。另外還能繪製**波形圖、對數頻譜圖、特徵時間軸 SVG**——純手寫繪製，不用繪圖函式庫，直接內嵌進 HTML 報告。

### 🖥️ 四種報告格式
`json`（對代理人友善）· `markdown`（對程式碼審查友善）· `text`（對終端機友善）· `html`（自包含，無外部資源）

---

## 🚀 三、快速開始

### 環境需求

| 項目 | 需求 |
|---|---|
| Python | **3.8 以上**（已在 3.8 – 3.13 驗證） |
| 執行期依賴 | **無** |
| 作業系統 | Windows、macOS、Linux——純 Python，沒有原生擴充 |
| 選用 | `PATH` 上有 `ffmpeg`——**只有**在需要把壓縮格式（MP3/OGG/M4A/FLAC）解碼成 PCM 時才用得到。沒有它，容器取證與結構分析照常輸出。 |

### 安裝

```bash
# 從儲存庫安裝
git clone https://github.com/gitstq/AudioVerdict.git
cd AudioVerdict
pip install -e .

# 驗證
audioverdict --version
```

也可以什麼都不裝直接跑：

```bash
PYTHONPATH=src python3 -m audioverdict --help
```

> `pip install -e .` 除了抓取 `setuptools` 之外不需要連網，**沒有任何第三方執行期套件**要下載。

### 30 秒上手

```bash
# 產生一段合成音訊並完整分析一遍（自我檢測）
audioverdict selftest

# 分析一個真實檔案
audioverdict analyze interview.m4a

# 輸出 Markdown，並拿需求描述去對照檔案
audioverdict analyze take3.flac --format markdown \
  --describe '低沉男聲獨白，安靜室內錄製' --out report.md

# 只要取證線索，JSON 格式
audioverdict verify evidence.wav --format json

# 這兩個檔案是同一段內容嗎？
audioverdict compare a.wav b.wav

# 掃整個目錄
audioverdict batch ./takes --format json --out takes.json
```

### 當成函式庫用

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

print(render(result, fmt="text", lang="zh"))      # 一屏速覽
print(result.as_dict())                           # 直接拿到 JSON 結構
```

一次呼叫回傳 `AnalysisResult`，裡面有 `container`、`global_features`、`timeline`、`notes`、`segments`、`findings`、`classification`、`scorecard`、`fingerprints` 與 `warnings`。`result.as_dict()` 直接給出 JSON 結構；`render(result, fmt=...)` 會把它渲染成 `json`、`text`、`markdown` 或 `html`。

---

## 📖 四、詳細使用指南

### 4.1 命令列一覽

```
audioverdict <子命令> [選項] <路徑>
```

| 子命令 | 作用 |
|---|---|
| `analyze`（別名 `analyse`） | 單一檔案完整分析 |
| `describe` | 輸出一段自然語言描述 |
| `fingerprint` | 只算內容指紋（快，不整段解碼） |
| `compare` | 依指紋比對兩個檔案 |
| `verify` | 只輸出取證線索 |
| `batch` | 分析目錄下所有音訊檔案 |
| `selftest` | 產生合成音訊並分析——用來驗證安裝沒問題 |

`analyze` / `verify` / `describe` 的通用選項：

| 選項 | 預設值 | 意義 |
|---|---|---|
| `--format` | `text` | `json`、`text`、`markdown`、`html` |
| `--describe TEXT` | – | 用來對照音訊的自由文字需求（中英文皆可） |
| `--out PATH` | 標準輸出 | 把報告寫到檔案 |
| `--window SEC` | `1.0` | 分析窗長度（秒） |
| `--hop SEC` | `0.5` | 窗之間的步進（秒） |
| `--max-windows N` | `400` | 分析窗數量上限（控制長音訊的耗時） |
| `--lang` | `en` | `en` 或 `zh`——筆記與摘要的語言 |

### 4.2 怎麼選輸出格式

```bash
# 給 LLM / 代理人管線：穩定、帶型別、資訊完整
audioverdict analyze take.wav --format json --out take.json

# 給程式碼審查、PR 留言或工單
audioverdict analyze take.wav --format markdown --out take.md

# 給人用瀏覽器打開：自包含、內嵌 SVG、可離線
audioverdict analyze take.wav --format html --out take.html

# 給終端機 / CI log
audioverdict analyze take.wav
```

### 4.3 怎麼讀 JSON

```jsonc
{
  "path": "take.wav",
  "container": { "format": "WAV", "codec": "PCM", "sample_rate": 44100,
                 "channels": 1, "lossy": false, "pcm_decoded": true },
  "global_features": { "loudness_lufs": -18.7, "peak_dbfs": -1.2,
                       "spectral_centroid": 1840.2, "clipping_ratio": 0.0 },
  "timeline": [ /* 每一個窗的特徵，帶 start/end */ ],
  "notes":    [ /* 人讀得懂的聆聽筆記 */ ],
  "segments": [ /* 值得回放的高亮片段 */ ],
  "findings": [
    { "code": "clipping", "severity": "high", "confidence": 0.93,
      "title": "偵測到削波",
      "detail": "2.68% 的取樣點頂在滿刻度。峰值 -0.1 dBFS ……",
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
  "summary": "綜合響度 -18.7 LUFS ……"
}
```

嚴重程度分為 `info` < `low` < `medium` < `high`。先用 `severity` 篩，再看 `confidence`。時間位置放在每一條線索的 `evidence` 物件裡（例如接合的 `points`、全零靜音的 `times`、削波的 `windows`），而不是線索的頂層欄位。

### 4.4 函式庫 API

```python
from audioverdict import analyse_file, read_audio, detect_format, SUPPORTED

# —— 便宜的結構性掃描：不整段解碼 ——
fmt = detect_format("huge_concert.flac")          # 'flac'
audio = read_audio("huge_concert.flac", max_bytes=2_000_000)
print(audio.sample_rate, audio.channels, audio.duration_seconds)

# —— 完整分析 ——
r = analyse_file("huge_concert.flac", window=2.0, hop=1.0, lang="zh")

# —— 指紋 / 近似重複偵測 ——
from audioverdict.analysis.fingerprint import fingerprints, compare
a = fingerprints("take_a.wav")
b = fingerprints("take_b.wav")
print(compare(a, b))   # {"similarity": 0.87, ...}

# —— 把結果渲染成任意格式的字串 ——
from audioverdict.report import render
md = render(r, fmt="markdown", lang="zh")
```

### 4.5 餵給代理人

AudioVerdict 生來就是要被塞進 prompt 裡的。實測最管用的姿勢：

```python
import subprocess

report = subprocess.run(
    ["audioverdict", "analyze", path, "--format", "json"],
    capture_output=True, text=True, check=True).stdout

prompt = f"""
這是使用者剛丟給我們的音訊檔案的實測報告。
把 severity 為 high 的 findings 當成阻塞問題，優先說明。
談響度、頻寬時一律引用 `global_features` 裡的數字，不要自己猜。
解釋問題時引用該條線索的 `evidence` 物件。

{report}

現在回答使用者關於這段音訊的問題。
"""
```

報告具確定性，同一個檔案永遠產出同一份證據——代理人的行為因此可重現、可測試。

### 4.6 格式支援一覽

| 容器 | 副檔名 | 不裝 ffmpeg 能解 PCM | 容器取證 |
|---|---|---|---|
| WAV / RIFF | `.wav`、`.wave` | ✅ | ✅ |
| AIFF / AIFF-C | `.aif`、`.aiff`、`.aifc` | ✅ | ✅ |
| FLAC | `.flac` | ❌（需 ffmpeg） | ✅ |
| MP3 | `.mp3` | ❌（需 ffmpeg） | ✅ |
| Ogg | `.ogg`、`.oga`、`.opus` | ❌（需 ffmpeg） | ✅ |
| MP4 / M4A | `.m4a`、`.mp4` | ❌（需 ffmpeg） | ✅ |

拿不到 PCM 時，AudioVerdict 會安靜降級成**僅容器報告**：格式、編碼、時長、位元率、結構異常與完整性檢查照樣輸出，並在 `warnings` 裡說明跳過了什麼。它不會在解不了的格式上崩潰。

### 4.7 效能提醒

- 內部分析統一重取樣到 **44.1 kHz**。128 kbps 的 MP3 在 16 kHz 附近就斷了，這個懸崖本身就是證據——不能先降取樣把它抹掉。
- `--max-windows`（預設 400）限制長錄音的工作量：按預設窗長與步進大約是前 200 秒。整段訪談就調大，CI 快速檢查就調小。
- 容器解析是惰性且有上限的：`read_audio(..., max_bytes=...)` 只讀檔案開頭。
- 2048 點的純 Python FFT 足夠互動使用；小時級的長音訊建議改用 `verify`（只要線索）或調大 `--hop`。

---

## 💡 五、設計思路與迭代規劃

### 5.1 幾個值得說清楚的決定

**為什麼堅持零依賴？**
一個要拖 200 MB 科學運算棧的音訊工具，進不了 CI 容器，進不了鎖死的公司筆電，也進不了代理人沙箱。這裡每一個演算法——FFT、K 加權、YIN、Mel 濾波器、指紋——都是直接實作的。代價是幾千行 DSP 程式碼，收益是 `pip install` 永不失敗、輸出在任何機器上逐位元組一致。

**為什麼給「證據」而不是「評價」？**
「聽起來悶悶的」對代理人毫無用處。`spectral_centroid 1180 Hz，高頻截止 6.2 kHz，findings: bandwidth_shortfall (high)` 才可行動。AudioVerdict 永遠同時給出量測值、信心度與推理過程，判斷權留給呼叫方。

**為什麼解析容器而不是解碼音訊？**
取證線索大多藏在容器裡。FLAC 存著原始 PCM 的 MD5——和解碼結果對不上，檔案就被改過。MP3 在 Xing 標頭裡宣告訊框數——和訊框鏈對不上，串流就被剪過或接過。這些都不需要解碼好幾 GB 的取樣點。

**為什麼內部分析率定在 44.1 kHz？**
因為轉碼偵測依賴看見編碼器留下的高頻懸崖，一旦先降取樣，懸崖就沒了。就這一個改動，區分了「查不出來」和「這個 48 kHz WAV 其實是 128 kbps 的 MP3」。

**為什麼手寫 SVG？**
這樣 HTML 報告就是零外部請求的單一檔案——能離線打開、能用郵件寄、能歸檔，也能安全地在沙箱預覽裡渲染。

### 5.2 迭代規劃

| 版本 | 主題 | 計畫內容 |
|---|---|---|
| **v1.1** | 更深取證 | ENF（電力網路頻率）分析、從失真指紋反推編碼器家族、重取樣器識別 |
| **v1.2** | 更多格式 | 裸 OBS 訊框的 Opus、WavPack、Monkey's Audio、ADTS AAC、Matroska 音訊 |
| **v1.3** | 提速 | 選用的 NumPy 快速路徑（只在 NumPy 存在時啟用，數值結果完全一致）；批次模式多行程化 |
| **v1.4** | 代理人易用性 | 提供 MCP server，讓代理人能把 `analyse_audio` 當成工具呼叫；母帶前後對比的 `.wav` diff 模式 |
| **v2.0** | 輕量說話人分離 | 說話人輪次切分與逐人響度統計，仍然全程離線 |
| **更遠** | 打包型態 | Windows / macOS / Linux 的單一執行檔版本 |

想法與 PR 都歡迎，見 [🤝 貢獻指南](#-七-貢獻指南)。

---

## 📦 六、打包與部署指南

AudioVerdict 是一個 **Python 函式庫 + 命令列工具**，不是桌面應用程式，因此沒有安裝程式可下載、也沒有平台二進位檔要發布——在要執行它的環境裡從原始碼安裝即可。

### 6.1 裝進專案

```bash
pip install -e .            # 可編輯模式，開發用
pip install .               # 一般安裝
```

兩種方式都會提供兩個命令列進入點：`audioverdict` 與短別名 `avd`。

### 6.2 隔離環境

```bash
# venv（推薦）
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 或者 uv
uv venv && uv pip install -e .

# 或者 conda
conda create -n avd python=3.11 && conda activate avd && pip install -e .
```

### 6.3 建置可散佈的 wheel / sdist

```bash
pip install --upgrade build
python -m build            # -> dist/audioverdict-1.0.0-py3-none-any.whl
```

產出的 wheel 是 `py3-none-any`：純 Python，沒有 ABI 標籤，所有平台、所有 ≥3.8 的解譯器通吃。裝到任何地方都是一句：

```bash
pip install dist/audioverdict-1.0.0-py3-none-any.whl
```

### 6.4 Docker / CI

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
# 選用：只有需要把 MP3/OGG/FLAC/M4A 解碼成 PCM 時才裝
# RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["audioverdict"]
```

```bash
docker build -t audioverdict .
docker run --rm -v "$PWD:/data" audioverdict analyze /data/take.wav --format json
```

### 6.5 嵌進你自己的工具

因為沒有執行期依賴，AudioVerdict 可以直接被內嵌（vendored）：把 `src/audioverdict/` 這個套件目錄複製進你的專案，直接 import。不必改你的 `requirements.txt`，也沒有依賴衝突風險。

```python
# your_package/audio.py
from audioverdict import analyse_file
```

### 6.6 選用：單一執行檔

本專案屬於函式庫 / CLI 類，不作為 Release 產物發布桌面二進位檔；但如果你確實需要在沒裝 Python 的機器上跑，可以自己打一個：

```bash
pip install pyinstaller
pyinstaller --onefile --name audioverdict src/audioverdict/__main__.py
# -> dist/audioverdict
```

### 6.7 環境變數

一個都不需要。AudioVerdict 不讀任何設定，不往你傳入的路徑之外寫任何東西，也不發出任何網路請求。

---

## 🤝 七、貢獻指南

真心歡迎貢獻，尤其是新的容器格式與新的取證檢查。

### 7.1 建環境

```bash
git clone https://github.com/gitstq/AudioVerdict.git
cd AudioVerdict
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt     # 只有一個 pytest
```

### 7.2 跑測試

```bash
pytest                      # 53 個測試
pytest -q                   # 安靜模式
pytest tests/test_dsp.py -v # 單一模組
```

乾淨檢出下 53 個測試全綠。測試自己合成訊號（純音、噪聲、靜音、接合、削波），所以**你不需要準備任何範例音訊**就能跑。

### 7.3 發 PR 之前

```bash
pytest                                  # 必須全綠
python -m audioverdict selftest         # 必須乾淨跑完
```

### 7.4 提交規範

本專案遵循 [Angular / Conventional Commits](https://www.conventionalcommits.org/) 風格：

| 前綴 | 用途 |
|---|---|
| `feat:` | 新能力 |
| `fix:` | 修 bug |
| `docs:` | 只改文件 |
| `refactor:` | 重構，行為不變 |
| `test:` | 只動測試 |
| `chore:` | 工具、打包、CI |

範例：`feat: 新增 WavPack 容器解析`、`fix: 修正 MP4 讀取中 stsd 取樣率偏移`、`docs: 補上繁體中文 README`。

### 7.5 可以從哪裡入手

- **新格式** —— WavPack、APE、ADTS AAC、Matroska 音訊。在 `src/audioverdict/decode/` 裡實作 `read_<格式>()`，到 `decode/__init__.py` 註冊，再補測試。
- **新取證檢查** —— 加到 `src/audioverdict/analysis/forensics.py`。每一條線索都要有 `code`、`severity`、`confidence`，以及一段引用了具體數字的 `detail`。
- **誤報** —— 這是最有價值的 bug 回報。如果 AudioVerdict 把乾淨的音訊判成有問題，請帶上檔案（或一段能重現的合成訊號）與預期結論開 issue。
- **翻譯** —— 筆記與摘要文案在 `src/audioverdict/analysis/notes.py`；詞庫在 `analysis/match.py`，已涵蓋中文與英文。歡迎更多語言。

### 7.6 幾條硬規矩

- **保持零依賴。** 加執行期依賴的 PR 不會合併，除非它是選用的且理由充分。
- **保持確定性。** 同樣輸入永遠得到同樣輸出。
- **壞檔案不許崩。** 降級到僅容器模式，並記一條 warning。

---

## 📄 八、開源授權說明

本專案以 **MIT License** 發布，詳見 [LICENSE](LICENSE)。

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

**使用須知**

- AudioVerdict 量測的是訊號屬性。它**不是**測謊器，也**不是**法律意義上的竄改證明——所有線索都是機率性證據，值得人工複核。
- 一切都在本機跑。你的音訊不會離開你的機器，因為這個專案裡根本沒有網路程式碼。
- 合成可能性評分對「後製很重但完全誠實」的素材（Podcast 後期鏈、老錄音修復）可能誤報。請把它當成「值得再聽一遍」的提示，而不是結論。

---

<div align="center">

**AudioVerdict** —— 讓你的代理人有一雙拿得出依據的耳朵。

🌐 [English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

</div>
