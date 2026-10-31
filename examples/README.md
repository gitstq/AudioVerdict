# 📚 Examples

Three runnable scripts. From the repository root, with the package importable:

```bash
pip install -e .                       # once
python3 examples/quickstart.py
```

or without installing:

```bash
PYTHONPATH=src python3 examples/quickstart.py
```

| Script | What it shows | How to run |
|---|---|---|
| [`quickstart.py`](quickstart.py) | The smallest useful library call: synthesise a clip, analyse it, print every field that matters | `python3 examples/quickstart.py [audio]` |
| [`agent_prompt.py`](agent_prompt.py) | The integration pattern AudioVerdict is built for — run the CLI, take the JSON, drop it into an LLM prompt with rules that stop the model from inventing numbers | `python3 examples/agent_prompt.py audio.wav "Is this good enough to ship?"` |
| [`batch_qc.py`](batch_qc.py) | A CI quality gate: sweep a directory, print a pass/fail table, exit non-zero on serious findings | `python3 examples/batch_qc.py ./takes --fail-on high` |

`quickstart.py` and `batch_qc.py` need no input files — they generate their own
test signals. `agent_prompt.py` takes any audio file you point it at.
