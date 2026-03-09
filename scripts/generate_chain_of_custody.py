#!/usr/bin/env python3
"""
Generate a Chain-of-Custody PDF from the pipeline's audit log and summary CSVs.

Inputs (default: out/):
- audit-log.csv
- review_set.csv
- dedupe_report.csv
- pii_findings.csv
- privilege_flags.csv

Output:
- out/chain-of-custody.pdf
"""
from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

def read_dicts(p: Path) -> List[Dict[str, str]]:
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def main(out_root: Path):
    audit = read_dicts(out_root / "audit-log.csv")
    review = read_dicts(out_root / "review_set.csv")
    dedupe = read_dicts(out_root / "dedupe_report.csv")
    pii = read_dicts(out_root / "pii_findings.csv")
    priv = read_dicts(out_root / "privilege_flags.csv")

    # Summaries
    actions = {}
    for r in audit:
        actions[r["action"]] = actions.get(r["action"], 0) + 1
    first_ts = audit[0]["timestamp"] if audit else ""
    last_ts  = audit[-1]["timestamp"] if audit else ""
    operators = sorted({r["operator"] for r in audit}) if audit else []
    total_docs = len(review)

    unique = sum(1 for r in dedupe if r.get("status") == "unique")
    dups   = sum(1 for r in dedupe if r.get("status") == "duplicate")

    total_pii_emails = sum(int(r.get("count_emails", "0") or 0) for r in pii)
    total_pii_phones = sum(int(r.get("count_phones", "0") or 0) for r in pii)
    total_priv_hits  = sum(int(r.get("count_terms", "0") or 0) for r in priv)

    # Build PDF
    pdf_path = out_root / "chain-of-custody.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=LETTER, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>Chain of Custody Report</b>", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z", styles["Normal"]))
    story.append(Paragraph(f"Processing window: {first_ts} → {last_ts}", styles["Normal"]))
    story.append(Paragraph(f"Operators: {', '.join(operators) if operators else 'N/A'}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Summary table
    data = [
        ["Metric", "Value"],
        ["Total items in review set", str(total_docs)],
        ["Unique items", str(unique)],
        ["Exact duplicates", str(dups)],
        ["PII email hits (sum of counts)", str(total_pii_emails)],
        ["PII phone hits (sum of counts)", str(total_pii_phones)],
        ["Privilege keyword hits (sum of counts)", str(total_priv_hits)],
    ]
    tbl = Table(data, hAlign="LEFT", colWidths=[220, 280])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (-1,-1), "LEFT"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 12))

    # Actions table
    if actions:
        data2 = [["Action", "Count"]] + [[k, str(v)] for k,v in sorted(actions.items())]
        tbl2 = Table(data2, hAlign="LEFT", colWidths=[220, 280])
        tbl2.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ]))
        story.append(Paragraph("<b>Audit Actions</b>", styles["Heading2"]))
        story.append(tbl2)
        story.append(Spacer(1, 12))

    story.append(Paragraph(
        "Defensibility Notes: Processing steps are deterministic and audited. "
        "Normalization, deduplication (hash-based), PII detection, privilege heuristics, and exports are reproducible. "
        "This report is a non-legal, technical summary for eDiscovery support.",
        styles["Italic"]
    ))

    doc.build(story)
    print(f"Chain-of-custody PDF written to: {pdf_path}")

if __name__ == "__main__":
    main(Path("out"))