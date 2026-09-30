# Publishing to PyPI (`pyfernet-payload`)

[中文](PUBLISH.zh-CN.md)

> The name `pyfernet` is already taken on PyPI. This project publishes as **`pyfernet-payload`**.  
> After install, the CLI and import remain: `pyfernet` / `import pyfernet`.

## Pre-flight

1. Keep `version` in `pyproject.toml` in sync with `pyfernet.__version__`.
2. Editable install and smoke-test:

```bash
cd PyFernet
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip setuptools wheel
python3 -m pip install -e .   # or: python3 -m pip install .
pip install build twine

pyfernet --version
pyfernet encrypt examples/demo_train -o dist/train_payload.enc -e train.py --password-env PYFERNET_PASSWORD
PYFERNET_PASSWORD=... pyfernet run dist/train_payload.enc --password-env PYFERNET_PASSWORD
```

3. Confirm README examples match the CLI.

## Build

```bash
rm -rf build/ dist/*.whl dist/*.tar.gz src/*.egg-info *.egg-info

python -m build
```

Artifacts under `dist/`:

- `pyfernet_payload-0.2.5-py3-none-any.whl`
- `pyfernet_payload-0.2.5.tar.gz`

## Upload to TestPyPI (recommended first)

1. Register at https://test.pypi.org/ and create an API token.
2. Configure `~/.pypirc` (do **not** commit it):

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR_PROD_TOKEN

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR_TEST_TOKEN
```

3. Upload and try install:

```bash
twine upload --repository testpypi dist/*

pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ pyfernet-payload
```

## Upload to PyPI

```bash
twine upload dist/*
# or
twine upload --repository pypi dist/*
```

Install:

```bash
pip install pyfernet-payload
```

## Version bump

Update both places for each release:

1. `src/pyfernet/__init__.py` → `__version__` (also used by `setup.py`)
2. `pyproject.toml` → `[project].version`

Use semver: `0.1.0` → `0.1.1` (fix) / `0.2.0` (feature).

## Client usage (after publish)

Install the package and upload the ciphertext—no need to copy `loader.py`:

```bash
pip install pyfernet-payload
pyfernet run train_payload.enc
```

## Config checklist

| Item | Where | Notes |
|---|---|---|
| Dist name | `pyproject.toml` `name` | `pyfernet-payload` |
| Import name | `src/pyfernet/` | `import pyfernet` |
| CLI | `[project.scripts]` | `pyfernet = pyfernet.cli:main` |
| Version | `pyproject.toml` + `__init__.py` | keep in sync |
| License | `LICENSE` + `license` | MIT |
| Python | `requires-python` | `>=3.10` |
| Deps | `dependencies` | empty (stdlib only) |
| Repo URL | `[project.urls]` | adjust if needed |
| Author | `authors` | adjust if needed |
| Docs | `README.md` / `README.zh-CN.md` | EN for PyPI, ZH mirror |
