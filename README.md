## Virtual Environment Setup

The dependancy tool `uv` [uv documentation here](https://docs.astral.sh/uv/getting-started/)
is used to control the python virtual environment. This can be installed with

```
pip install uv
```

Once it has completed you can then run `uv sync` to install everything.

The script can then be run by using `uv run egse.py` or by configuring vscode to use the
newly created virtual environment.
