"""What a source can do, in the words a user reads. Connectors fill this in; erm/assist.py reads it."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceProfile:
    source_name: str
    finds: str
    clear_example: str
    unclear_example: str
    lookup_example: str
    comes_out: str
    cannot_do: tuple[str, ...]
