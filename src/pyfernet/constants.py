"""Shared payload format constants."""

from __future__ import annotations

MAGIC = b"PYFE1\0"
SALT_LEN = 16
KDF_ITERATIONS = 390_000
MANIFEST_NAME = "_pyfernet_manifest.json"

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
}
SKIP_SUFFIXES = {".pyc", ".pyo", ".enc"}
ALLOW_SUFFIXES = {
    ".py",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".cfg",
    ".ini",
    ".txt",
    ".md",
}
ALLOW_NAMES = {"LICENSE", "NOTICE"}
