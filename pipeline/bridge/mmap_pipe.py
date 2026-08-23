# -*- coding: utf-8 -*-
"""
pipeline.bridge.mmap_pipe — anonymous mmap ring buffer.

Binary layout
-------------
    [0  : 24]  header : write_pos (int64) | read_pos (int64) | capacity (int64)
    [24 : ...]  slots  : capacity × slot_size bytes

Each slot:
    [0:2]  length prefix (uint16, big-endian) — number of payload bytes
    [2:slot_size]  payload (null-padded to slot_size-2 bytes)

Concurrency
-----------
A single threading.Condition serialises all put/get calls.  Both sides
block on the Condition when the buffer is full (put) or empty (get), and
notify_all() after every state change so waiters re-check the predicate.

Usage
-----
    pipe = MmapPipe(capacity=256)
    pipe.put(b"hello")           # blocks if full
    data = pipe.get(timeout=5.0) # None on timeout
    pipe.close()
"""
from __future__ import annotations

import fcntl
import mmap
import os
import struct
import threading
import time
from pathlib import Path
from typing import Optional, Union

# ── layout constants ───────────────────────────────────────────────────────────
_HEADER_FMT: str = ">qqq"          # big-endian signed int64 × 3
_HEADER_SIZE: int = struct.calcsize(_HEADER_FMT)  # 24 bytes
_LENGTH_FMT: str = ">H"            # big-endian uint16 slot-length prefix
_LENGTH_SIZE: int = struct.calcsize(_LENGTH_FMT)  # 2 bytes

_DEFAULT_CAPACITY: int = 256       # slots
_DEFAULT_SLOT_SIZE: int = 512      # bytes per slot (max payload: 510 bytes)


# ── public class ───────────────────────────────────────────────────────────────
class MmapPipe:
    """
    Anonymous mmap ring buffer for inter-thread message passing.

    Parameters
    ----------
    capacity  : number of message slots (default 256)
    slot_size : bytes per slot including the 2-byte length prefix (default 512)
    """

    def __init__(
        self,
        capacity: int = _DEFAULT_CAPACITY,
        slot_size: int = _DEFAULT_SLOT_SIZE,
    ) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")
        max_payload = slot_size - _LENGTH_SIZE
        if max_payload < 1:
            raise ValueError(f"slot_size must be > {_LENGTH_SIZE}, got {slot_size}")

        self._capacity = capacity
        self._slot_size = slot_size
        self._max_payload = max_payload

        total = _HEADER_SIZE + capacity * slot_size
        self._buf = mmap.mmap(-1, total)  # anonymous (no backing file)
        # Initialise header: write_pos=0, read_pos=0, capacity=capacity
        struct.pack_into(_HEADER_FMT, self._buf, 0, 0, 0, capacity)

        self._cond = threading.Condition(threading.Lock())

    # ── header helpers ─────────────────────────────────────────────────────────
    def _read_header(self) -> tuple[int, int, int]:
        return struct.unpack_from(_HEADER_FMT, self._buf, 0)  # type: ignore[return-value]

    def _write_header(self, wp: int, rp: int, cap: int) -> None:
        struct.pack_into(_HEADER_FMT, self._buf, 0, wp, rp, cap)

    def _slot_offset(self, pos: int) -> int:
        return _HEADER_SIZE + (pos % self._capacity) * self._slot_size

    # ── public API ─────────────────────────────────────────────────────────────
    def put(self, data: bytes, timeout: Optional[float] = None) -> bool:
        """
        Write *data* into the next available slot.

        Parameters
        ----------
        data    : payload bytes; must fit in slot_size - 2 bytes
        timeout : seconds to wait if the buffer is full; None = wait forever

        Returns
        -------
        True on success, False if the timeout expires before a slot opens.

        Raises
        ------
        ValueError  if len(data) exceeds max_payload
        RuntimeError if the pipe has been closed
        """
        if len(data) > self._max_payload:
            raise ValueError(
                f"payload too large: {len(data)} bytes > max {self._max_payload}"
            )

        deadline = (time.monotonic() + timeout) if timeout is not None else None

        with self._cond:
            while True:
                if self._buf.closed:
                    raise RuntimeError("MmapPipe is closed")
                wp, rp, cap = self._read_header()
                if wp - rp < cap:
                    offset = self._slot_offset(wp)
                    struct.pack_into(_LENGTH_FMT, self._buf, offset, len(data))
                    self._buf[offset + _LENGTH_SIZE : offset + _LENGTH_SIZE + len(data)] = data
                    self._write_header(wp + 1, rp, cap)
                    self._cond.notify_all()
                    return True

                remaining = (
                    (deadline - time.monotonic()) if deadline is not None else None
                )
                if remaining is not None and remaining <= 0:
                    return False
                self._cond.wait(timeout=remaining)

    def get(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """
        Read the next message from the buffer.

        Parameters
        ----------
        timeout : seconds to wait if the buffer is empty; None = wait forever

        Returns
        -------
        bytes on success, None if the timeout expires before a message arrives.

        Raises
        ------
        RuntimeError if the pipe has been closed
        """
        deadline = (time.monotonic() + timeout) if timeout is not None else None

        with self._cond:
            while True:
                if self._buf.closed:
                    raise RuntimeError("MmapPipe is closed")
                wp, rp, cap = self._read_header()
                if wp > rp:
                    offset = self._slot_offset(rp)
                    (length,) = struct.unpack_from(_LENGTH_FMT, self._buf, offset)
                    data = bytes(
                        self._buf[offset + _LENGTH_SIZE : offset + _LENGTH_SIZE + length]
                    )
                    self._write_header(wp, rp + 1, cap)
                    self._cond.notify_all()
                    return data

                remaining = (
                    (deadline - time.monotonic()) if deadline is not None else None
                )
                if remaining is not None and remaining <= 0:
                    return None
                self._cond.wait(timeout=remaining)

    def qsize(self) -> int:
        """Return the number of messages currently in the buffer."""
        with self._cond:
            wp, rp, _ = self._read_header()
            return wp - rp

    def __len__(self) -> int:
        return self.qsize()

    def close(self) -> None:
        """Release the underlying mmap.  Any blocked put/get will raise RuntimeError."""
        with self._cond:
            if not self._buf.closed:
                self._buf.close()
            self._cond.notify_all()

    def __repr__(self) -> str:
        try:
            n = self.qsize()
        except Exception:
            n = -1
        return (
            f"MmapPipe(capacity={self._capacity}, slot_size={self._slot_size}, "
            f"qsize={n})"
        )


# ── file-backed cross-process pipe ─────────────────────────────────────────────

_POLL_SLEEP: float = 0.01  # seconds between lock retries when the ring is full/empty


class SharedMmapPipe:
    """
    File-backed mmap ring with the same binary layout as MmapPipe.

    Two processes open the same path.  fcntl.flock serialises put/get;
    waiters poll (Condition is in-process only).

    Parameters
    ----------
    path      : backing file (created when ``create=True``)
    capacity  : slot count (default 64)
    slot_size : bytes per slot including the 2-byte length prefix (default 2048)
    create    : if True, create/truncate to the layout size and init the header
    """

    def __init__(
        self,
        path: Union[str, Path],
        capacity: int = 64,
        slot_size: int = 2048,
        *,
        create: bool = True,
    ) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")
        max_payload = slot_size - _LENGTH_SIZE
        if max_payload < 1:
            raise ValueError(f"slot_size must be > {_LENGTH_SIZE}, got {slot_size}")
        if max_payload > 65535:
            raise ValueError("slot_size - 2 must fit in uint16")

        self._path = Path(path)
        self._capacity = capacity
        self._slot_size = slot_size
        self._max_payload = max_payload
        self._total = _HEADER_SIZE + capacity * slot_size

        self._path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        self._lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)

        if create:
            self._ensure_file()
        elif not self._path.exists() or self._path.stat().st_size < self._total:
            os.close(self._lock_fd)
            raise FileNotFoundError(f"SharedMmapPipe backing file missing: {self._path}")

        self._fd = os.open(str(self._path), os.O_RDWR)
        self._buf = mmap.mmap(self._fd, self._total)
        if create:
            self._init_header_if_empty()

    def _ensure_file(self) -> None:
        if self._path.exists() and self._path.stat().st_size == self._total:
            return
        fd = os.open(str(self._path), os.O_CREAT | os.O_RDWR, 0o644)
        try:
            os.ftruncate(fd, self._total)
        finally:
            os.close(fd)

    def _init_header_if_empty(self) -> None:
        fcntl.flock(self._lock_fd, fcntl.LOCK_EX)
        try:
            wp, rp, cap = struct.unpack_from(_HEADER_FMT, self._buf, 0)
            if cap != self._capacity:
                struct.pack_into(_HEADER_FMT, self._buf, 0, 0, 0, self._capacity)
                self._buf.flush()
        finally:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)

    def _read_header(self) -> tuple[int, int, int]:
        return struct.unpack_from(_HEADER_FMT, self._buf, 0)  # type: ignore[return-value]

    def _write_header(self, wp: int, rp: int, cap: int) -> None:
        struct.pack_into(_HEADER_FMT, self._buf, 0, wp, rp, cap)
        self._buf.flush()

    def _slot_offset(self, pos: int) -> int:
        return _HEADER_SIZE + (pos % self._capacity) * self._slot_size

    def put(self, data: bytes, timeout: Optional[float] = None) -> bool:
        if len(data) > self._max_payload:
            raise ValueError(
                f"payload too large: {len(data)} bytes > max {self._max_payload}"
            )
        deadline = (time.monotonic() + timeout) if timeout is not None else None
        while True:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_EX)
            except OSError as exc:
                raise RuntimeError("SharedMmapPipe is closed") from exc
            try:
                if self._buf.closed:
                    raise RuntimeError("SharedMmapPipe is closed")
                wp, rp, cap = self._read_header()
                if wp - rp < cap:
                    offset = self._slot_offset(wp)
                    struct.pack_into(_LENGTH_FMT, self._buf, offset, len(data))
                    self._buf[offset + _LENGTH_SIZE : offset + _LENGTH_SIZE + len(data)] = data
                    self._write_header(wp + 1, rp, cap)
                    return True
            finally:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)

            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(_POLL_SLEEP)

    def get(self, timeout: Optional[float] = None) -> Optional[bytes]:
        deadline = (time.monotonic() + timeout) if timeout is not None else None
        while True:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_EX)
            except OSError as exc:
                raise RuntimeError("SharedMmapPipe is closed") from exc
            try:
                if self._buf.closed:
                    raise RuntimeError("SharedMmapPipe is closed")
                wp, rp, cap = self._read_header()
                if wp > rp:
                    offset = self._slot_offset(rp)
                    (length,) = struct.unpack_from(_LENGTH_FMT, self._buf, offset)
                    data = bytes(
                        self._buf[offset + _LENGTH_SIZE : offset + _LENGTH_SIZE + length]
                    )
                    self._write_header(wp, rp + 1, cap)
                    return data
            finally:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)

            if deadline is not None and time.monotonic() >= deadline:
                return None
            time.sleep(_POLL_SLEEP)

    def qsize(self) -> int:
        fcntl.flock(self._lock_fd, fcntl.LOCK_EX)
        try:
            wp, rp, _ = self._read_header()
            return wp - rp
        finally:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)

    def __len__(self) -> int:
        return self.qsize()

    def close(self) -> None:
        fcntl.flock(self._lock_fd, fcntl.LOCK_EX)
        try:
            if not self._buf.closed:
                self._buf.close()
            try:
                os.close(self._fd)
            except OSError:
                pass
        finally:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            try:
                os.close(self._lock_fd)
            except OSError:
                pass

    def __repr__(self) -> str:
        try:
            n = self.qsize()
        except Exception:
            n = -1
        return (
            f"SharedMmapPipe(path={str(self._path)!r}, capacity={self._capacity}, "
            f"slot_size={self._slot_size}, qsize={n})"
        )
