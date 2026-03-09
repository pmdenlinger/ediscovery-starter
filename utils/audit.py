# utils/audit.py
from __future__ import annotations
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

class AuditLogger:
    """
    Lightweight CSV audit logger for eDiscovery processing.
    Fields: timestamp, action, file_id, operator, details
    """
    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_header()

    def _ensure_header(self):
        if not self.log_path.exists():
            with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "action", "file_id", "operator", "details"])

    def write(self, action: str, file_id: str, operator: str = "system", details: Optional[Dict[str, Any]] = None):
        ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        d = details or {}
        with open(self.log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([ts, action, file_id, operator, _dict_to_str(d)])

def _dict_to_str(d: Dict[str, Any]) -> str:
    try:
        items = [f"{k}={v}" for k, v in d.items()]
        return "; ".join(items)
    except Exception:
        return str(d)