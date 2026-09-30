"""PyFernet: encrypt a source directory into one .enc file and run it from memory."""

from __future__ import annotations

__version__ = "0.2.5"

from pyfernet.encryptor import encrypt_directory
from pyfernet.loader import run_payload

__all__ = [
    "__version__",
    "encrypt_directory",
    "run_payload",
]
