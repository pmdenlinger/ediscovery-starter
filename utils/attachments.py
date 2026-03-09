# utils/attachments.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple

def parse_attachments_from_eml_headers(headers: str) -> List[str]:
    """
    Looks for our synthetic 'X-Attachments: a;b;c' header block in the raw header text.
    Caller provides header string (already joined).
    """
    lines = [h.strip() for h in headers.splitlines()]
    for line in lines:
        if line.lower().startswith("x-attachments:"):
            val = line.split(":", 1)[1].strip()
            if val:
                return [x.strip() for x in val.split(";") if x.strip()]
    return []

def copy_attachment_stubs(attachments: List[str], input_root: Path, dest_dir: Path) -> Tuple[int, List[str]]:
    """
    Copy attachment stub files from <input_root>/attachments/<name> to dest_dir.
    Returns (count, copied_names).
    If files are missing, skip silently (this is a demo).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: List[str] = []
    attach_root = input_root / "attachments"
    for name in attachments:
        src = attach_root / name
        if src.exists():
            target = dest_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            data = src.read_bytes()
            target.write_bytes(data)
            copied.append(name)
    return len(copied), copied