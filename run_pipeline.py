#!/usr/bin/env python3
"""
End-to-end eDiscovery starter pipeline:
- Ingest (.json, .eml)
- Normalize & extract metadata
- PII detection (emails, phone numbers)
- Privilege heuristics + scoring
- Dedupe (sha256 of normalized text)
- Attachment handling (copy stubs)
- Near-duplicate clustering (shingles + Jaccard)
- Build review set
- Emit audit log + simple exports (text, natives)
"""
from __future__ import annotations
import argparse
import csv
import email
import hashlib
import json
import logging
import re
import shutil
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from utils.audit import AuditLogger
from utils.privilege import privilege_score
from utils.attachments import parse_attachments_from_eml_headers, copy_attachment_stubs
from utils.textsim import cluster_near_duplicates

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ediscovery-pipeline")

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?)\d{3}[\s-]?\d{4})")

def parse_args():
    p = argparse.ArgumentParser(description="Run the eDiscovery starter pipeline.")
    p.add_argument("--input", default="00-setup/sample-data", help="Input directory")
    p.add_argument("--output", default="out", help="Output directory")
    p.add_argument("--operator", default="system", help="Operator/user name for audit")
    p.add_argument("--near-k", type=int, default=5, help="Shingle size for near-dup")
    p.add_argument("--near-threshold", type=float, default=0.85, help="Jaccard threshold for near-dup clustering")
    return p.parse_args()

def main():
    args = parse_args()
    in_dir = Path(args.input)
    out_dir = Path(args.output)
    natives_dir = out_dir / "natives"
    text_dir = out_dir / "text"
    normalized_dir = out_dir / "normalized"
    attach_out_dir = out_dir / "attachments"
    out_dir.mkdir(parents=True, exist_ok=True)
    natives_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    attach_out_dir.mkdir(parents=True, exist_ok=True)

    audit = AuditLogger(out_dir / "audit-log.csv")

    records: List[Dict] = []
    seen_hashes: Dict[str, str] = {}  # content_hash -> file_id
    dedupe_rows: List[List[str]] = []
    pii_rows: List[List[str]] = [["file_id", "emails_found", "phones_found", "count_emails", "count_phones"]]
    priv_rows: List[List[str]] = [["file_id", "terms_matched", "count_terms"]]

    # Keep normalized text per doc for near-dup
    norm_texts: Dict[str, str] = {}

    # Ingest
    for p in in_dir.rglob("*"):
        if p.is_dir():
            continue
        if p.suffix.lower() not in {".json", ".eml"}:
            continue

        file_id = p.stem
        audit.write("INGEST", file_id, args.operator, {"source": str(p), "size": p.stat().st_size})
        logger.info(f"Ingesting {p.name}")

        meta, text, headers_text, attachments_list = extract_with_attachments(p)
        norm_text = normalize_text(text)
        norm_texts[file_id] = norm_text
        content_hash = hashlib.sha256(norm_text.encode("utf-8", errors="ignore")).hexdigest()

        # Dedupe
        duplicate_of: Optional[str] = None
        if content_hash in seen_hashes:
            duplicate_of = seen_hashes[content_hash]
        else:
            seen_hashes[content_hash] = file_id
        dedupe_rows.append([file_id, "duplicate" if duplicate_of else "unique", duplicate_of or ""])

        # PII
        emails_found = EMAIL_RE.findall(text)
        phones_found = PHONE_RE.findall(text)
        pii_rows.append([file_id, ";".join(sorted(set(emails_found))), ";".join(sorted(set(phones_found))), str(len(set(emails_found))), str(len(set(phones_found)))])
        audit.write("PII_DETECT", file_id, args.operator, {"emails": len(set(emails_found)), "phones": len(set(phones_found))})

        # Privilege heuristics + scoring
        matched = _priv_terms_hit(text)
        priv_rows.append([file_id, ";".join(matched), str(len(matched))])
        score, reasons = privilege_score(meta.get("subject", ""), text, meta.get("from",""), meta.get("to",""), meta.get("cc",""))
        audit.write("PRIVILEGE_HEURISTIC", file_id, args.operator, {"terms": len(matched), "score": score})

        # Attachments (copy stubs if listed)
        copied_count, copied_names = (0, [])
        if attachments_list:
            copied_count, copied_names = copy_attachment_stubs(attachments_list, in_dir, attach_out_dir / file_id)
            audit.write("ATTACHMENTS_COPIED", file_id, args.operator, {"count": copied_count})

        # Review set row
        rec = {
            "file_id": file_id,
            "path": str(p),
            "content_hash": content_hash,
            "duplicate_of": duplicate_of or "",
            "from": meta.get("from", ""),
            "to": meta.get("to", ""),
            "cc": meta.get("cc", ""),
            "subject": meta.get("subject", ""),
            "date": meta.get("date", ""),
            "pii_email_count": len(set(emails_found)),
            "pii_phone_count": len(set(phones_found)),
            "privilege_term_count": len(matched),
            "privilege_score": score,
            "privilege_reasons": ";".join(reasons),
            "attachment_count": copied_count,
            "attachment_names": ";".join(copied_names),
            "near_dupe_cluster": "",  # filled after clustering
        }
        records.append(rec)
        audit.write("REVIEW_ADD", file_id, args.operator, {"duplicate_of": duplicate_of or "self"})

        # Writes
        shutil.copy2(p, natives_dir / p.name)
        with open(text_dir / f"{file_id}.txt", "w", encoding="utf-8", errors="ignore") as f:
            f.write(text)
        with open(normalized_dir / f"{file_id}.txt", "w", encoding="utf-8") as f:
            f.write(norm_text)

    # Near-duplicate clustering (only if 2+ docs)
    clusters_csv_rows: List[List[str]] = [["cluster_id", "rep_id", "file_id", "similarity"]]
    if len(norm_texts) >= 2:
        raw_clusters = cluster_near_duplicates(norm_texts, k=args.near_k, threshold=args.near_threshold)
        cluster_id = 1
        doc_to_cluster: Dict[str, str] = {}
        for rep_id, group in raw_clusters:
            cid = f"ND{cluster_id}"
            for fid, sim in group:
                doc_to_cluster[fid] = cid
                clusters_csv_rows.append([cid, rep_id, fid, f"{sim:.3f}"])
            cluster_id += 1

        # annotate review_set records
        for rec in records:
            if rec["file_id"] in doc_to_cluster:
                rec["near_dupe_cluster"] = doc_to_cluster[rec["file_id"]]

    # Save reports
    write_csv(out_dir / "review_set.csv", records)
    write_rows(out_dir / "dedupe_report.csv", [["file_id", "status", "duplicate_of"], *dedupe_rows])
    write_rows(out_dir / "pii_findings.csv", pii_rows)
    write_rows(out_dir / "privilege_flags.csv", priv_rows)
    write_rows(out_dir / "near_dupe_clusters.csv", clusters_csv_rows)

    logger.info(f"Pipeline complete. Output in: {out_dir.resolve()}")

def write_csv(path: Path, dict_rows: List[Dict]):
    # Always write with headers (even if 0 rows) for consistency
    header = [
        "file_id","path","content_hash","duplicate_of","from","to","cc","subject","date",
        "pii_email_count","pii_phone_count","privilege_term_count","privilege_score","privilege_reasons",
        "attachment_count","attachment_names","near_dupe_cluster"
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for r in dict_rows:
            writer.writerow(r)

def write_rows(path: Path, rows: List[List[str]]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for r in rows:
            writer.writerow(r)

def extract_with_attachments(path: Path) -> Tuple[Dict[str, str], str, str, List[str]]:
    """
    Extracts metadata + text + headers and discovers attachment names.
    JSON expected keys: from, to, cc, subject, date, body, attachments (list of names)
    EML: parse stdlib; attachments via 'X-Attachments' header (synthetic)
    """
    if path.suffix.lower() == ".json":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            obj = json.load(f)
        meta = {
            "from": obj.get("from", ""),
            "to": _list_to_str(obj.get("to")),
            "cc": _list_to_str(obj.get("cc")),
            "subject": obj.get("subject", ""),
            "date": obj.get("date", ""),
        }
        body = obj.get("body", "")
        atts = obj.get("attachments", []) or []
        return meta, str(body), "", [str(a) for a in atts]
    elif path.suffix.lower() == ".eml":
        with open(path, "rb") as f:
            msg = BytesParser(policy=policy.default).parse(f)
        meta = {
            "from": msg.get("From", ""),
            "to": msg.get("To", ""),
            "cc": msg.get("Cc", ""),
            "subject": msg.get("Subject", ""),
            "date": msg.get("Date", ""),
        }
        body = _get_email_body(msg)
        headers_text = _headers_to_text(msg)
        atts = parse_attachments_from_eml_headers(headers_text)
        return meta, body, headers_text, atts
    else:
        return {}, "", "", []

def _get_email_body(msg: email.message.EmailMessage) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                parts.append(part.get_content())
        return "\n".join([str(p) for p in parts])
    else:
        return str(msg.get_content())

def _headers_to_text(msg: email.message.EmailMessage) -> str:
    lines = []
    for k, v in msg.items():
        lines.append(f"{k}: {v}")
    return "\n".join(lines)

def _list_to_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return "; ".join([str(x) for x in v])
    return str(v)

def normalize_text(text: str) -> str:
    """
    Defensibility note:
    Normalization is deterministic and documented.
    Steps: strip, collapse whitespace, lowercase.
    """
    return " ".join((text or "").strip().split()).lower()

def _priv_terms_hit(text: str) -> List[str]:
    terms = [
        "attorney-client", "attorney client", "privileged", "confidential legal",
        "work product", "legal advice", "counsel", "outside counsel", "solicitor-client"
    ]
    t = (text or "").lower()
    return [x for x in terms if x in t]

if __name__ == "__main__":
    main()