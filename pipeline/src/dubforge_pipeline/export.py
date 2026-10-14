"""Backward-compat re-export: this logic now lives in dubforge_contracts.export
so apps/api (which doesn't depend on dubforge-pipeline) can use it too."""

from dubforge_contracts.export import (
    format_srt_timestamp,
    format_vtt_timestamp,
    segments_to_srt,
    segments_to_vtt,
)

__all__ = [
    "format_srt_timestamp",
    "format_vtt_timestamp",
    "segments_to_srt",
    "segments_to_vtt",
]
