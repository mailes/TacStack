"""Read-only zarr v2 store over one member prefix inside an uncompressed tar.

Contract:
- The tar must be a seekable local file (plain tar, no gzip); random access is
  required because zarr reads individual chunk members on demand.
- Keys are tar member names relative to ``root``; only regular members are
  indexed and tar directory entries are ignored.
- Member order in the tar is irrelevant; discovery relies solely on names.
"""

import tarfile
import threading
from collections.abc import AsyncIterator, Iterable
from pathlib import Path

from zarr.abc.store import (
    ByteRequest,
    OffsetByteRequest,
    RangeByteRequest,
    Store,
    SuffixByteRequest,
)
from zarr.core.buffer import Buffer, BufferPrototype


class TarStore(Store):
    """Expose ``<root>/*`` members of a tar file as zarr store keys."""

    supports_writes: bool = False
    supports_deletes: bool = False
    supports_listing: bool = True

    def __init__(self, tar_path: str | Path, root: str = "") -> None:
        super().__init__(read_only=True)
        self.tar_path = Path(tar_path)
        self.root = root
        self._lock = threading.RLock()
        self._tf: tarfile.TarFile | None = None
        self._members: dict[str, tarfile.TarInfo] = {}

    def _sync_open(self) -> None:
        if self._is_open:
            return
        self._tf = tarfile.open(self.tar_path, "r:")
        self._members = {}
        for member in self._tf:
            if not member.isfile() or not member.name.startswith(self.root):
                continue
            key = member.name[len(self.root) :]
            if key:
                self._members[key] = member
        self._is_open = True

    async def _open(self) -> None:
        self._sync_open()

    def close(self) -> None:
        if not self._is_open:
            return
        super().close()
        with self._lock:
            assert self._tf is not None
            self._tf.close()

    def __str__(self) -> str:
        return f"tar://{self.tar_path}!{self.root}"

    def __repr__(self) -> str:
        return f"TarStore('{self}')"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, TarStore)
            and self.tar_path == other.tar_path
            and self.root == other.root
        )

    def _read(
        self, key: str, byte_range: ByteRequest | None, prototype: BufferPrototype
    ) -> Buffer | None:
        assert self._tf is not None
        member = self._members.get(key)
        if member is None:
            return None
        source = self._tf.extractfile(member)
        if source is None:
            return None
        with source:
            if byte_range is None:
                return prototype.buffer.from_bytes(source.read())
            size = member.size
            if isinstance(byte_range, RangeByteRequest):
                source.seek(byte_range.start)
                end = min(byte_range.end, size)
                return prototype.buffer.from_bytes(source.read(max(0, end - source.tell())))
            if isinstance(byte_range, OffsetByteRequest):
                source.seek(min(byte_range.offset, size))
                return prototype.buffer.from_bytes(source.read())
            if isinstance(byte_range, SuffixByteRequest):
                source.seek(max(0, size - byte_range.suffix))
                return prototype.buffer.from_bytes(source.read())
        raise TypeError(f"Unexpected byte_range: {byte_range!r}")

    async def get(
        self,
        key: str,
        prototype: BufferPrototype,
        byte_range: ByteRequest | None = None,
    ) -> Buffer | None:
        with self._lock:
            self._sync_open()
            return self._read(key, byte_range, prototype)

    async def get_partial_values(
        self,
        prototype: BufferPrototype,
        key_ranges: Iterable[tuple[str, ByteRequest | None]],
    ) -> list[Buffer | None]:
        with self._lock:
            self._sync_open()
            return [self._read(key, byte_range, prototype) for key, byte_range in key_ranges]

    async def exists(self, key: str) -> bool:
        with self._lock:
            self._sync_open()
            return key in self._members

    async def set(self, key: str, value: Buffer) -> None:
        self._check_writable()
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        self._check_writable()
        raise NotImplementedError

    async def clear(self) -> None:
        self._check_writable()
        raise NotImplementedError

    async def list(self) -> AsyncIterator[str]:
        with self._lock:
            self._sync_open()
            keys = sorted(self._members)
        for key in keys:
            yield key

    async def list_prefix(self, prefix: str) -> AsyncIterator[str]:
        async for key in self.list():
            if key.startswith(prefix):
                yield key

    async def list_dir(self, prefix: str) -> AsyncIterator[str]:
        with self._lock:
            self._sync_open()
            prefix = prefix.rstrip("/")
            if prefix:
                names = [
                    key[len(prefix) + 1 :].split("/")[0]
                    for key in self._members
                    if key.startswith(prefix + "/")
                ]
            else:
                names = [key.split("/")[0] for key in self._members]
            children = sorted(set(names) - {""})
        for child in children:
            yield child
