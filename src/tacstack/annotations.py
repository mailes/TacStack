"""Lightweight tactile annotation marks stored as a Parquet file.

Schema ``tacstack.annotations.v1`` (one row per mark):
- ``source`` / ``task`` / ``episode`` / ``stream``: what was annotated
- ``frame_index``: episode-relative frame number; ``oxt_frame_index``: the
  absolute frame index in the source array (matches
  ``metadata["oxt_frame_index"]`` and the Rerun ``frame_index`` timeline);
  ``timestamp_ns``: the observation's adapter timestamp
- ``mark``: ``C`` (contact) / ``S`` (slip) / ``U`` (unstable grasp)
- ``user`` / ``created_ns`` / ``schema_version``: provenance

The file is an append-only log: adding a mark rewrites the Parquet file with
all previous rows plus the new one, and ``AnnotationLog`` reloads existing
marks on open so marking and replay can interleave. Requires the optional
``annotate`` extra (``uv sync --extra annotate``); pyarrow is imported lazily
so the rest of the package never needs it.
"""

import time
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
MARK_CODES = ("C", "S", "U")
MARK_LABELS = {"C": "contact", "S": "slip", "U": "unstable_grasp"}
_MARK_ALIASES = {label.upper(): code for code, label in MARK_LABELS.items()}


def normalize_mark(mark: str) -> str:
    """Map a user-supplied mark (``C``, ``slip``, ...) to its code."""
    candidate = mark.strip().upper()
    if candidate in _MARK_ALIASES:
        return _MARK_ALIASES[candidate]
    if candidate in MARK_CODES:
        return candidate
    raise ValueError(
        f"unknown mark {mark!r}; expected one of {', '.join(MARK_CODES)} "
        f"({', '.join(MARK_LABELS[code] for code in MARK_CODES)})"
    )


def _require_positive_int(name: str, value: Any) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative Python integer")


@dataclass(frozen=True)
class TactileMark:
    """One annotation mark on one frame of one tactile stream."""

    source: str
    task: str
    episode: int
    stream: str
    frame_index: int
    oxt_frame_index: int
    timestamp_ns: int
    mark: str
    user: str
    created_ns: int
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not all(x.strip() for x in (self.source, self.task, self.stream, self.user)):
            raise ValueError("source, task, stream and user must not be empty")
        _require_positive_int("episode", self.episode)
        _require_positive_int("frame_index", self.frame_index)
        _require_positive_int("oxt_frame_index", self.oxt_frame_index)
        _require_positive_int("timestamp_ns", self.timestamp_ns)
        _require_positive_int("created_ns", self.created_ns)
        if self.mark not in MARK_CODES:
            raise ValueError(f"mark must be one of {', '.join(MARK_CODES)}, got {self.mark!r}")

    @property
    def label(self) -> str:
        """Human-readable label for the mark ("contact" / "slip" / ...)."""
        return MARK_LABELS[self.mark]


def now_ns() -> int:
    """Current wall-clock time as epoch nanoseconds."""
    return time.time_ns()


class AnnotationLog:
    """Append-only mark log backed by one Parquet file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._marks: list[TactileMark] = []
        if self._path.exists():
            self._marks = self._read()

    def add(self, mark: TactileMark) -> TactileMark:
        """Append one mark and persist the whole log."""
        self._marks.append(mark)
        self._write()
        return mark

    def marks(self) -> tuple[TactileMark, ...]:
        """All marks in insertion order (file order for reloaded marks)."""
        return tuple(self._marks)

    def __len__(self) -> int:
        return len(self._marks)

    def _require_pyarrow(self) -> Any:
        try:
            import pyarrow.parquet as pq
        except ImportError as error:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                f"pyarrow is not installed; run: uv sync --extra annotate ({error})"
            ) from error
        return pq

    def _read(self) -> list[TactileMark]:
        pq = self._require_pyarrow()
        rows = pq.read_table(self._path).to_pylist()
        names = {f.name for f in fields(TactileMark)}
        return [TactileMark(**{k: v for k, v in row.items() if k in names}) for row in rows]

    def _write(self) -> None:
        pq = self._require_pyarrow()
        import pyarrow as pa

        rows = [vars(mark) for mark in self._marks]
        table = pa.Table.from_pylist(rows)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, self._path)
