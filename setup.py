#!/usr/bin/env python3
"""setuptools entry for older pip that does not fully honor pyproject [project].

Keeps name/version/entry points explicit so installs are not UNKNOWN-0.0.0.
"""

from __future__ import annotations

import re
from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"


def _version() -> str:
    init = (SRC / "pyfernet" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init, re.M)
    if not m:
        raise RuntimeError("cannot find __version__ in pyfernet/__init__.py")
    return m.group(1)


setup(
    name="pyfernet-payload",
    version=_version(),
    description=(
        "Encrypt a Python source directory into one .enc file "
        "and run it from memory (Fernet AES, stdlib-only)."
    ),
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="shunyaoyin",
    url="https://github.com/yinshunyao/PyFernet",
    license="MIT",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    package_data={"pyfernet": ["py.typed"]},
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[],
    entry_points={
        "console_scripts": [
            "pyfernet=pyfernet.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Security :: Cryptography",
    ],
)
