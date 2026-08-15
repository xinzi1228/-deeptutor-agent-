"""Immutable, profile-private dataset snapshots for truthful visualizations."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import re
from typing import Any

from deeptutor.services.file_io import atomic_write_json

_SNAPSHOT_ID_RE = re.compile(r"dataset_[a-f0-9]{20}")


def _canonical_payload(
    *,
    dataset_id: str,
    version: int,
    query: dict[str, Any],
    source: str,
    unit: str,
    source_updated_at: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "version": version,
        "query": query,
        "source": source,
        "unit": unit,
        "source_updated_at": source_updated_at,
        "content": content,
    }


def _sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def freeze_dataset_snapshot(
    profile_root: Path,
    *,
    dataset_id: str,
    version: int,
    query: dict[str, Any],
    source: str,
    unit: str,
    source_updated_at: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    """Freeze a chart dataset and return its server-verifiable reference."""

    dataset_id = str(dataset_id or "").strip()
    source = str(source or "").strip()
    unit = str(unit or "").strip()
    if not dataset_id or not source or not unit:
        raise ValueError("数据集编号、来源和单位不能为空")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError("数据集版本必须是正整数")
    if not isinstance(query, dict) or not isinstance(content, dict):
        raise ValueError("数据集查询和内容必须是对象")

    canonical = _canonical_payload(
        dataset_id=dataset_id,
        version=version,
        query=query,
        source=source,
        unit=unit,
        source_updated_at=str(source_updated_at or ""),
        content=content,
    )
    digest = _sha256(canonical)
    snapshot_id = f"dataset_{digest[:20]}"
    snapshot = {
        "schema_version": 2,
        "snapshot_id": snapshot_id,
        **canonical,
        "dataset_ref": {
            "dataset_id": dataset_id,
            "version": version,
            "query": query,
            "unit": unit,
            "sha256": digest,
        },
    }
    target = (
        Path(profile_root)
        / "artifacts"
        / "visualization_datasets"
        / f"{snapshot_id}.json"
    )
    atomic_write_json(target, snapshot)
    return snapshot


def load_verified_dataset_snapshot(profile_root: Path, snapshot_id: str) -> dict[str, Any]:
    """Load a snapshot from the active profile and reject any altered facts."""

    value = str(snapshot_id or "").strip()
    if not _SNAPSHOT_ID_RE.fullmatch(value):
        raise ValueError("可信数据快照编号不合法")
    path = (
        Path(profile_root)
        / "artifacts"
        / "visualization_datasets"
        / f"{value}.json"
    )
    if not path.exists():
        raise ValueError("找不到该可信数据快照，请重新读取学习数据")
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("可信数据快照无法读取") from exc
    if not isinstance(snapshot, dict):
        raise ValueError("可信数据快照格式不正确")

    dataset_ref = snapshot.get("dataset_ref")
    if not isinstance(dataset_ref, dict):
        raise ValueError("可信数据快照缺少 dataset_ref")
    canonical = _canonical_payload(
        dataset_id=str(snapshot.get("dataset_id") or ""),
        version=snapshot.get("version"),
        query=snapshot.get("query"),
        source=str(snapshot.get("source") or ""),
        unit=str(snapshot.get("unit") or ""),
        source_updated_at=str(snapshot.get("source_updated_at") or ""),
        content=snapshot.get("content"),
    )
    expected = str(dataset_ref.get("sha256") or "")
    actual = _sha256(canonical)
    if not re.fullmatch(r"[a-f0-9]{64}", expected) or not hmac.compare_digest(expected, actual):
        raise ValueError("可信数据快照哈希校验失败，禁止继续生成图表")
    if value != f"dataset_{actual[:20]}":
        raise ValueError("可信数据快照编号与哈希不一致")
    if dataset_ref.get("dataset_id") != canonical["dataset_id"]:
        raise ValueError("可信数据集编号不一致")
    if dataset_ref.get("version") != canonical["version"]:
        raise ValueError("可信数据集版本不一致")
    if dataset_ref.get("query") != canonical["query"]:
        raise ValueError("可信数据集查询不一致")
    if dataset_ref.get("unit") != canonical["unit"]:
        raise ValueError("可信数据集单位不一致")
    return snapshot


__all__ = ["freeze_dataset_snapshot", "load_verified_dataset_snapshot"]
