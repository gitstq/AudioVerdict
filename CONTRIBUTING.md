# 🤝 Contributing to AudioVerdict

Thanks for considering a contribution. This document covers the workflow, the
commit convention and the two rules that are not negotiable.

🌐 [English](#english) · [简体中文](#简体中文) · [繁體中文](#繁體中文)

---

## English

### Set up

```bash
git clone https://github.com/gitstq/AudioVerdict.git
cd AudioVerdict
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt     # pytest only
```

### Run the tests

```bash
pytest            # 53 tests, all must pass
pytest -q
pytest tests/test_decode.py -v
```

The suite synthesises its own signals (tones, noise, silence, splices, clipped
audio), so you need no sample files.

### Before opening a pull request

```bash
pytest                           # green
python -m audioverdict selftest  # completes cleanly
```

### Commit convention

Angular / [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|---|---|
| `feat:` | New capability |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `refactor:` | Restructuring, no behaviour change |
| `test:` | Tests only |
| `chore:` | Tooling, packaging, CI |

Example: `feat: add WavPack container parser`

### Where to help

- **New formats** — WavPack, APE, ADTS AAC, Matroska audio. Implement
  `read_<fmt>()` in `src/audioverdict/decode/`, register it in
  `decode/__init__.py`, add tests to `tests/test_decode.py`.
- **New forensic checks** — add to `src/audioverdict/analysis/forensics.py`.
  Every finding needs `code`, `severity`, `confidence`, and a `detail` string
  that cites the numbers it used.
- **False positives** — the most valuable bug report there is. Include the file
  (or a synthetic reproduction) and the expected verdict.
- **Translations** — notes live in `src/audioverdict/analysis/notes.py`; the
  description-matching lexicon lives in `analysis/match.py`.

### Ground rules

1. **Zero runtime dependencies.** A PR that adds one will not be merged unless
   it is optional and clearly justified. The whole point of this project is
   that `pip install` cannot fail.
2. **Deterministic output.** Same input → same output, on every machine.
3. **Never crash on a bad file.** Degrade to container-only and record a
   warning in `result.warnings`.
4. **Pure standard library.** Python 3.8 syntax only — no walrus-free
   assumptions, no `match` statements, no 3.9+ typing generics on builtins.

### Reporting issues

Please include: the file format, the exact command you ran, the output you got,
and the output you expected. A synthetic reproduction is worth ten bug reports.

---

## 简体中文

### 搭建环境

```bash
git clone https://github.com/gitstq/AudioVerdict.git
cd AudioVerdict
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt     # 只有一个 pytest
```

### 跑测试

```bash
pytest            # 53 个测试，必须全绿
pytest -q
pytest tests/test_decode.py -v
```

测试会自己合成信号（纯音、噪声、静音、拼接、削波），不需要准备示例音频。

### 提 PR 之前

```bash
pytest                           # 全绿
python -m audioverdict selftest  # 干净跑完
```

### 提交规范

Angular / [Conventional Commits](https://www.conventionalcommits.org/)：

| 前缀 | 用途 |
|---|---|
| `feat:` | 新能力 |
| `fix:` | 修 bug |
| `docs:` | 只改文档 |
| `refactor:` | 重构，行为不变 |
| `test:` | 只动测试 |
| `chore:` | 工具、打包、CI |

示例：`feat: 新增 WavPack 容器解析`

### 可以从哪里入手

- **新格式** —— WavPack、APE、ADTS AAC、Matroska 音频。在
  `src/audioverdict/decode/` 里实现 `read_<格式>()`，到 `decode/__init__.py`
  注册，再往 `tests/test_decode.py` 补测试。
- **新取证检查** —— 加到 `src/audioverdict/analysis/forensics.py`。每条线索
  都要有 `code`、`severity`、`confidence`，以及一段引用了具体数字的 `detail`。
- **误报** —— 最有价值的 bug 报告。请带上文件（或一段能复现的合成信号）与
  预期结论。
- **翻译** —— 笔记文案在 `src/audioverdict/analysis/notes.py`；描述对照词库
  在 `analysis/match.py`。

### 硬规矩

1. **零运行时依赖。** 加依赖的 PR 不会合，除非它是可选的且理由充分。这个
   项目的立身之本就是 `pip install` 永不失败。
2. **输出确定性。** 同样输入永远得到同样输出，任何机器上都是。
3. **坏文件不许崩。** 降级到仅容器模式，并在 `result.warnings` 里记一条。
4. **只用标准库。** 只用 Python 3.8 语法——不能用 `match` 语句，不能在
   内建类型上用 3.9+ 的泛型写法。

### 提 issue

请附上：文件格式、你跑的确切命令、实际输出、期望输出。一段能复现的合成
信号，抵得上十份描述含糊的报告。

---

## 繁體中文

### 建置環境

```bash
git clone https://github.com/gitstq/AudioVerdict.git
cd AudioVerdict
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt     # 只有一個 pytest
```

### 跑測試

```bash
pytest            # 53 個測試，必須全綠
pytest -q
pytest tests/test_decode.py -v
```

測試會自行合成訊號（純音、噪聲、靜音、接合、削波），不必準備範例音訊。

### 發 PR 之前

```bash
pytest                           # 全綠
python -m audioverdict selftest  # 乾淨跑完
```

### 提交規範

Angular / [Conventional Commits](https://www.conventionalcommits.org/)：

| 前綴 | 用途 |
|---|---|
| `feat:` | 新能力 |
| `fix:` | 修 bug |
| `docs:` | 只改文件 |
| `refactor:` | 重構，行為不變 |
| `test:` | 只動測試 |
| `chore:` | 工具、打包、CI |

範例：`feat: 新增 WavPack 容器解析`

### 可以從哪裡入手

- **新格式** —— WavPack、APE、ADTS AAC、Matroska 音訊。在
  `src/audioverdict/decode/` 裡實作 `read_<格式>()`，到 `decode/__init__.py`
  註冊，再往 `tests/test_decode.py` 補測試。
- **新取證檢查** —— 加到 `src/audioverdict/analysis/forensics.py`。每一條線索
  都要有 `code`、`severity`、`confidence`，以及一段引用了具體數字的 `detail`。
- **誤報** —— 最有價值的 bug 回報。請帶上檔案（或一段能重現的合成訊號）與
  預期結論。
- **翻譯** —— 筆記文案在 `src/audioverdict/analysis/notes.py`；描述對照詞庫
  在 `analysis/match.py`。

### 硬規矩

1. **零執行期依賴。** 加依賴的 PR 不會合併，除非它是選用的且理由充分。這個
   專案的立身之本就是 `pip install` 永不失敗。
2. **輸出確定性。** 同樣輸入永遠得到同樣輸出，任何機器上都是。
3. **壞檔案不許崩。** 降級到僅容器模式，並在 `result.warnings` 裡記一條。
4. **只用標準函式庫。** 只用 Python 3.8 語法——不能用 `match` 語句，不能在
   內建型別上用 3.9+ 的泛型寫法。

### 發 issue

請附上：檔案格式、你跑的確切指令、實際輸出、期望輸出。一段能重現的合成
訊號，抵得上十份描述含糊的回報。
