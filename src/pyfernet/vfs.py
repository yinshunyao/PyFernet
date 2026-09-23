"""内存 VFS：包内文件不落盘，Path/open/import 从内存读。"""

from __future__ import annotations

import builtins
import importlib.abc
import importlib.machinery
import importlib.util
import io
import os
import sys
from pathlib import Path
from typing import Callable


class PayloadVFS:
    """root 下仅有空目录；文件内容在 mapping（相对 posix 路径 → bytes）。"""

    def __init__(self, root: Path, mapping: dict[str, bytes]):
        self.root = root.resolve()
        self.rel_files = {k.replace("\\", "/"): v for k, v in mapping.items()}
        self.abs_files: dict[str, bytes] = {}
        for rel, data in self.rel_files.items():
            abs_p = (self.root / rel).resolve()
            self.abs_files[str(abs_p)] = data
            self.abs_files[abs_p.as_posix()] = data

        self._orig_open = builtins.open
        self._orig_path_open = Path.open
        self._orig_read_text = Path.read_text
        self._orig_read_bytes = Path.read_bytes
        self._orig_is_file = Path.is_file
        self._orig_exists = Path.exists
        self._orig_os_path_isfile = os.path.isfile
        self._orig_os_path_exists = os.path.exists
        self._orig_spec_from_file_location = importlib.util.spec_from_file_location
        self._path_hook: Callable | None = None
        self._installed = False

    def _norm_key(self, path: str | Path) -> str | None:
        try:
            p = Path(path)
            if not p.is_absolute():
                p = Path.cwd() / p
            key = str(p.resolve())
        except Exception:
            key = str(path)
        if key in self.abs_files:
            return key
        try:
            alt = Path(path)
            key2 = str((self.root / alt).resolve()) if not alt.is_absolute() else str(alt.resolve())
            if key2 in self.abs_files:
                return key2
        except Exception:
            pass
        return None

    def has(self, path: str | Path) -> bool:
        return self._norm_key(path) is not None

    def read_bytes(self, path: str | Path) -> bytes:
        key = self._norm_key(path)
        if key is None:
            raise FileNotFoundError(path)
        return self.abs_files[key]

    def managed_dir(self, path: str | Path) -> bool:
        try:
            Path(path).resolve().relative_to(self.root)
            return True
        except Exception:
            return False

    def ensure_dir_tree(self) -> None:
        """只创建空目录，不写任何文件内容。"""
        self.root.mkdir(parents=True, exist_ok=True)
        for rel in self.rel_files:
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)

    def install(self) -> None:
        if self._installed:
            return
        vfs = self

        def open_hook(file, mode="r", *args, **kwargs):
            if isinstance(file, (str, os.PathLike)) and vfs.has(file):
                data = vfs.read_bytes(file)
                if "b" in mode:
                    return io.BytesIO(data)
                enc = kwargs.get("encoding") or "utf-8"
                return io.StringIO(data.decode(enc))
            return vfs._orig_open(file, mode, *args, **kwargs)

        def path_open(self: Path, mode="r", *args, **kwargs):
            if vfs.has(self):
                return open_hook(self, mode, *args, **kwargs)
            return vfs._orig_path_open(self, mode, *args, **kwargs)

        def path_read_text(self: Path, encoding="utf-8", errors="strict"):
            if vfs.has(self):
                return vfs.read_bytes(self).decode(encoding, errors)
            return vfs._orig_read_text(self, encoding=encoding, errors=errors)

        def path_read_bytes(self: Path):
            if vfs.has(self):
                return vfs.read_bytes(self)
            return vfs._orig_read_bytes(self)

        def path_is_file(self: Path):
            if vfs.has(self):
                return True
            return vfs._orig_is_file(self)

        def path_exists(self: Path):
            if vfs.has(self):
                return True
            return vfs._orig_exists(self)

        def os_isfile(path):
            if vfs.has(path):
                return True
            return vfs._orig_os_path_isfile(path)

        def os_exists(path):
            if vfs.has(path):
                return True
            return vfs._orig_os_path_exists(path)

        def spec_from_file_location(name, location, *args, **kwargs):
            if location is not None and vfs.has(location):
                loc = str(Path(location).resolve())
                source = vfs.read_bytes(location)
                is_pkg = loc.endswith(f"{os.sep}__init__.py") or loc.endswith("/__init__.py")
                loader = _VfsSourceLoader(name, loc, source, is_package=is_pkg)
                spec = importlib.machinery.ModuleSpec(
                    name, loader, origin=loc, is_package=is_pkg
                )
                if is_pkg:
                    spec.submodule_search_locations = [str(Path(loc).parent)]
                return spec
            return vfs._orig_spec_from_file_location(name, location, *args, **kwargs)

        def path_hook(entry):
            if vfs.managed_dir(entry):
                return _VfsPathFinder(vfs, str(Path(entry).resolve()))
            raise ImportError("not a pyfernet vfs path")

        builtins.open = open_hook  # type: ignore[assignment]
        Path.open = path_open  # type: ignore[method-assign, assignment]
        Path.read_text = path_read_text  # type: ignore[method-assign, assignment]
        Path.read_bytes = path_read_bytes  # type: ignore[method-assign, assignment]
        Path.is_file = path_is_file  # type: ignore[method-assign, assignment]
        Path.exists = path_exists  # type: ignore[method-assign, assignment]
        os.path.isfile = os_isfile  # type: ignore[assignment]
        os.path.exists = os_exists  # type: ignore[assignment]
        importlib.util.spec_from_file_location = spec_from_file_location  # type: ignore[assignment]

        self._path_hook = path_hook
        sys.path_hooks.insert(0, path_hook)
        sys.path_importer_cache.clear()
        importlib.invalidate_caches()
        self._installed = True

    def uninstall(self) -> None:
        if not self._installed:
            return
        builtins.open = self._orig_open  # type: ignore[assignment]
        Path.open = self._orig_path_open  # type: ignore[method-assign, assignment]
        Path.read_text = self._orig_read_text  # type: ignore[method-assign, assignment]
        Path.read_bytes = self._orig_read_bytes  # type: ignore[method-assign, assignment]
        Path.is_file = self._orig_is_file  # type: ignore[method-assign, assignment]
        Path.exists = self._orig_exists  # type: ignore[method-assign, assignment]
        os.path.isfile = self._orig_os_path_isfile  # type: ignore[assignment]
        os.path.exists = self._orig_os_path_exists  # type: ignore[assignment]
        importlib.util.spec_from_file_location = self._orig_spec_from_file_location  # type: ignore[assignment]
        if self._path_hook is not None:
            try:
                sys.path_hooks.remove(self._path_hook)
            except ValueError:
                pass
        sys.path_importer_cache.clear()
        importlib.invalidate_caches()
        self._installed = False


class _VfsSourceLoader(importlib.abc.Loader):
    def __init__(self, name: str, path: str, source: bytes, is_package: bool = False):
        self.name = name
        self.path = path
        self.source = source
        self.is_package = is_package

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = self.path
        if self.is_package:
            module.__path__ = [str(Path(self.path).parent)]
            module.__package__ = self.name
        else:
            parent, _, _ = self.name.rpartition(".")
            module.__package__ = parent
        code = compile(self.source, self.path, "exec")
        exec(code, module.__dict__)

    def get_filename(self, fullname):
        return self.path

    def is_package(self, fullname):
        return self.is_package

    def get_data(self, path):
        with open(path, "rb") as f:
            return f.read()


class _VfsPathFinder(importlib.abc.PathEntryFinder):
    """行为对齐 importlib.machinery.FileFinder：只用 fullname 最后一段。"""

    def __init__(self, vfs: PayloadVFS, path_entry: str):
        self.vfs = vfs
        self.path_entry = path_entry

    def find_spec(self, fullname, target=None):
        base = Path(self.path_entry)
        # 与 FileFinder 一致：path 已是包目录或 sys.path 项时，只找 tail
        tail = fullname.rpartition(".")[2]
        file_cand = base / f"{tail}.py"
        pkg_cand = base / tail / "__init__.py"

        if self.vfs.has(pkg_cand):
            origin = str(pkg_cand.resolve())
            source = self.vfs.read_bytes(pkg_cand)
            loader = _VfsSourceLoader(fullname, origin, source, is_package=True)
            spec = importlib.machinery.ModuleSpec(
                fullname, loader, origin=origin, is_package=True
            )
            spec.submodule_search_locations = [str(pkg_cand.parent.resolve())]
            return spec

        if self.vfs.has(file_cand):
            origin = str(file_cand.resolve())
            source = self.vfs.read_bytes(file_cand)
            loader = _VfsSourceLoader(fullname, origin, source, is_package=False)
            return importlib.machinery.ModuleSpec(
                fullname, loader, origin=origin, is_package=False
            )

        return None
