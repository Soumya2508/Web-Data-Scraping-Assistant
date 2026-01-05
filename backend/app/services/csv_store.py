from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings


@dataclass
class CsvExport:
    export_id: str
    file_path: Path


def ensure_exports_dir() -> Path:
    base = Path(settings.exports_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base


def write_records_to_csv(records: list[dict[str, Any]]) -> CsvExport:
    export_id = uuid.uuid4().hex[:8]
    exports_dir = ensure_exports_dir()
    file_path = exports_dir / f"{export_id}.csv"

    df = pd.DataFrame.from_records(records)
    df.to_csv(file_path, index=False)

    return CsvExport(export_id=export_id, file_path=file_path)
