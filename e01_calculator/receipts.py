"""Append-only JSONL audit receipt writer (outside the protected boundary)."""

from __future__ import annotations

import json
import os
import threading
import weakref


class ReceiptWriter:
    _registry_guard = threading.Lock()
    _registry = weakref.WeakValueDictionary()

    def __init__(self, path: str):
        self.path = os.path.abspath(os.fspath(path))
        identity = os.path.normcase(self.path)
        with self._registry_guard:
            self._lock = self._registry.setdefault(identity, threading.Lock())
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    def append(self, record: dict) -> None:
        if type(record) is not dict:
            raise ValueError("receipt must be an object")
        line = (json.dumps(record, sort_keys=True, ensure_ascii=True,
                           allow_nan=False) + "\n").encode("utf-8")
        if len(line) > 65536:
            raise ValueError("receipt exceeds 64 KiB")
        with self._lock:
            if os.path.islink(self.path):
                raise OSError("receipt destination must not be a symbolic link")
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a+b") as fh:
                fh.seek(0, os.SEEK_END)
                if fh.tell():
                    fh.seek(-1, os.SEEK_END)
                    if fh.read(1) != b"\n":
                        raise OSError("receipt file has an incomplete trailing record")
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
