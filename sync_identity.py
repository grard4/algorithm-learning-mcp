"""Stable identity for one Codex rollout shard, independent of its folder."""
from pathlib import Path


def source_key(path):
    name=Path(path).name
    if name.endswith('.zst'):
        name=name[:-4]
    if name.endswith('.jsonl'):
        name=name[:-6]
    if not name:
        raise ValueError('empty rollout source key')
    return name.casefold()
