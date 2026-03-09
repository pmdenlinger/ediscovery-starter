#!/usr/bin/env python3
"""
Generate a richer synthetic dataset for ediscovery-starter.

Creates .eml and .json messages with:
- Custodians and multiple domains (business + counsel)
- Privilege-like content (attorney/client keywords, counsel domains)
- PII (emails + US-style phone numbers)
- Duplicates (exact same normalized text) and near-duplicates (minor changes)
- Multilingual bodies (English, Chinese, French)
- Attachment stubs (files created under attachments/)
- A manifest.csv for quick review

Usage examples:
  python scripts/generate_synthetic_data.py
  python scripts/generate_synthetic_data.py --out 00-setup/sample-data --count 40 --eml 28 --json 12 --dup-rate 0.15 --near-dup-rate 0.20

Then run:
  python run_pipeline.py --input 00-setup/sample-data --output out
  python 04-exports/export-relativity.py --input-csv out/review_set.csv --natives out/natives --text out/text --outdir out/relativity
"""

from __future__ import annotations
import argparse
import csv
import os
import random
import string
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import List, Dict, Tuple

# ------------ Configuration Seeds (deterministic for reproducibility) ------------
RANDOM_SEED = 42

CUSTODIANS = [
    ("Alice Johnson", "alice"),
    ("Bob Smith", "bob"),
    ("Carol Chen", "carol"),
    ("Dave Patel", "dave"),
    ("Eve Martin", "eve"),
]

BUSINESS_DOMAINS = ["example.com", "contoso.com", "fabrikam.com"]
COUNSEL_DOMAINS = ["outsidecounsel.com", "lawfirm.co", "counsel.example"]

PRIV_KEYWORDS = [
    "attorney-client",
    "privileged",
    "work product",
    "confidential legal",
    "legal advice",
    "solicitor-client",
]
PRIV_SUBJECT_TOKENS = [
    "Privileged",
    "Attorney-Client",
    "Work Product",
    "Confidential",
    "Counsel Review",
]

EN_SENTENCES = [
    "Please see the attached draft and let me know your thoughts.",
    "We will review this with the team tomorrow morning.",
    "Looping in Legal for advice on next steps.",
    "Can we get outside counsel to review the agreement?",
    "Call me at (714) 555-2121 if you have questions.",
    "The budget needs to be finalized by next Tuesday.",
]
CN_SENTENCES = [
    "请看附件草稿并提出意见。",
    "我们明天上午和团队一起评审。",
    "把法务团队抄送，征求下一步建议。",
    "需要外部律师审阅这份协议。",
    "如有问题请拨打 +1-714-555-1212 联系我。",
]
FR_SENTENCES = [
    "Veuillez consulter le projet ci-joint et me faire part de vos commentaires.",
    "Nous l’examinerons avec l’équipe demain matin.",
    "J’ajoute le service juridique pour avis.",
    "Pouvons-nous demander au conseil externe d’examiner l’accord ?",
    "Appelez-moi au 714-555-3434 si besoin.",
]

LANG_POOLS = {
    "en": EN_SENTENCES,
    "zh": CN_SENTENCES,
    "fr": FR_SENTENCES,
}

LANG_WEIGHTS_DEFAULT = {
    "en": 0.7,
    "zh": 0.2,
    "fr": 0.1,
}

# ------------------------------ Helpers ------------------------------
def rand_phone() -> str:
    patterns = [
        "(714) 555-2121",
        "714-555-3434",
        "+1-714-555-1212",
        "+1 714 555 6565",
    ]
    return random.choice(patterns)

def rand_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=seconds)

def pick_custodian() -> Tuple[str, str]:
    name, handle = random.choice(CUSTODIANS)
    domain = random.choice(BUSINESS_DOMAINS)
    return name, f"{handle}@{domain}"

def pick_counsel() -> Tuple[str, str]:
    first = random.choice(["Ann", "Ben", "Chloe", "Derek", "Fiona", "Gao", "Hiro"])
    last = random.choice(["Lo", "Ng", "Wang", "Cohen", "Dubois", "Takeda", "Singh"])
    handle = f"{first.lower()}.{last.lower()}"
    domain = random.choice(COUNSEL_DOMAINS)
    return f"{first} {last}", f"{handle}@{domain}"

def make_subject(priv: bool) -> str:
    core = random.choice([
        "Draft agreement review",
        "Budget discussion",
        "Vendor onboarding",
        "Data transfer assessment",
        "Pricing terms",
        "Meeting notes",
        "Contract redlines",
    ])
    if priv:
        token = random.choice(PRIV_SUBJECT_TOKENS)
        return f"{token} - {core}"
    return core

def make_body(lang: str, include_priv: bool, include_phone: bool, include_counsel_ref: bool) -> str:
    pool = LANG_POOLS[lang]
    sents = random.sample(pool, k=min(3, len(pool)))
    extra = []
    if include_priv:
        extra.append(f"This may contain {random.choice(PRIV_KEYWORDS)} material.")
    if include_phone:
        extra.append(f"Call me at {rand_phone()}.")
    if include_counsel_ref:
        extra.append("Escalating to outside counsel for legal advice.")
    # Always include an email somewhere for PII hit
    extra.append(f"Contact: {random.choice(['alice','bob','carol','dave','eve'])}@{random.choice(BUSINESS_DOMAINS)}")
    return " ".join(sents + extra)

def normalize_for_dedupe(text: str) -> str:
    # Must match pipeline logic: strip -> collapse whitespace -> lowercase
    return " ".join(text.strip().split()).lower()

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

# ------------------------------ Writers ------------------------------
def write_eml(path: Path, from_name_email: Tuple[str, str], to_list: List[str], cc_list: List[str],
              subject: str, dt: datetime, body: str, attachments: List[str]):
    headers = []
    headers.append(f"From: {from_name_email[0]} <{from_name_email[1]}>")
    headers.append(f"To: {', '.join(to_list)}")
    if cc_list:
        headers.append(f"Cc: {', '.join(cc_list)}")
    headers.append(f"Subject: {subject}")
    headers.append(f"Date: {format_datetime(dt.astimezone(timezone.utc))}")
    headers.append("Content-Type: text/plain; charset=utf-8")
    if attachments:
        headers.append(f"X-Attachments: {';'.join(attachments)}")
    content = "\n".join(headers) + "\n\n" + body + "\n"
    path.write_text(content, encoding="utf-8")

def write_json(path: Path, from_addr: str, to_list: List[str], cc_list: List[str],
               subject: str, dt: datetime, body: str, attachments: List[str]):
    import json
    obj = {
        "from": from_addr,
        "to": to_list,
        "cc": cc_list,
        "subject": subject,
        "date": dt.astimezone(timezone.utc).isoformat(),
        "body": body,
        "attachments": attachments,
    }
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

# ------------------------------ Generator ------------------------------
def generate_dataset(
    out_dir: Path,
    count: int = 40,
    eml_count: int = 28,
    json_count: int = 12,
    dup_rate: float = 0.15,
    near_dup_rate: float = 0.20,
    lang_weights: Dict[str, float] = None,
):
    random.seed(RANDOM_SEED)
    ensure_dir(out_dir)
    attach_dir = out_dir / "attachments"
    ensure_dir(attach_dir)

    if lang_weights is None:
        lang_weights = LANG_WEIGHTS_DEFAULT

    # Pre-create some attachment stubs
    attachment_pool = []
    for i in range(1, 11):
        fname = f"ATT-{i:03d}-draft.txt"
        (attach_dir / fname).write_text(f"Placeholder attachment #{i}\n", encoding="utf-8")
        attachment_pool.append(fname)

    start = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 3, 1, 18, 0, 0, tzinfo=timezone.utc)

    # Adjust EML/JSON split to match total requested
    total = eml_count + json_count
    if total != count:
        eml_count = min(count, eml_count)
        json_count = count - eml_count

    # --- Plan duplicates and near-duplicates ---
    indices = list(range(count))
    random.shuffle(indices)
    dup_docs = int(round(count * dup_rate))
    near_dup_docs = int(round(count * near_dup_rate))

    # Create duplicate clusters as pairs (and possibly one trio if odd)
    dup_indices = indices[:dup_docs]
    remainder = indices[dup_docs:]

    dup_clusters: List[List[int]] = []
    i = 0
    while i + 1 < len(dup_indices):
        dup_clusters.append([dup_indices[i], dup_indices[i + 1]])
        i += 2
    if i < len(dup_indices):  # odd leftover -> make a trio with the last pair (or create a single trio if none)
        if dup_clusters:
            dup_clusters[-1].append(dup_indices[i])
        else:
            # If only one dup index, convert to a trio with two more from remainder (fallback)
            extras = remainder[:2]
            remainder = remainder[2:]
            dup_clusters.append([dup_indices[i], *extras])

    # Choose near-duplicate indices from the remainder (exclude anything already in dup clusters)
    used_in_dups = set(j for cluster in dup_clusters for j in cluster)
    available = [j for j in remainder if j not in used_in_dups]
    random.shuffle(available)
    near_dup_indices = set(available[:near_dup_docs])

    # Helper to pick language by weights
    def pick_lang() -> str:
        return random.choices(list(lang_weights.keys()), weights=list(lang_weights.values()))[0]

    # Build canonical text for each duplicate cluster
    cluster_body_texts: List[str] = []
    for _ in dup_clusters:
        lang = pick_lang()
        # Force privilege & counsel references to make it interesting and stable
        canonical = make_body(lang, include_priv=True, include_phone=True, include_counsel_ref=True)
        # Use *exact same string* across the cluster to guarantee a matching normalized hash
        # (normalize_text==lower/collapse whitespace is applied downstream)
        cluster_body_texts.append(canonical)

    # Map each index -> planned body text (enforced for duplicates/near-duplicates)
    body_plan: Dict[int, str] = {}

    # Assign exact duplicate bodies
    for cluster, body in zip(dup_clusters, cluster_body_texts):
        for idx in cluster:
            body_plan[idx] = body

    # Assign near-duplicates: small tweaks on top of freshly generated bodies
    for idx in near_dup_indices:
        lang = pick_lang()
        base = make_body(
            lang,
            include_priv=(random.random() < 0.5),
            include_phone=(random.random() < 0.5),
            include_counsel_ref=(random.random() < 0.4),
        )
        tweak = random.choice([" Updated.", " (v2)", " — minor edit", " + note"])
        body_plan[idx] = base + tweak

    # Prepare manifest
    manifest_rows = [[
        "file_name", "type", "custodian_from", "to", "cc", "subject", "date",
        "lang", "is_duplicate", "is_near_duplicate", "attachments"
    ]]

    # Generate messages
    for i in range(count):
        is_eml = i < eml_count

        # Parties and recipients
        from_name, from_email = pick_custodian()
        recipients = []
        if random.random() < 0.7:
            rec_handle = random.choice(["ops", "sales", "finance", "legal", "hr", "it"])
            recipients.append(f"{rec_handle}@{random.choice(BUSINESS_DOMAINS)}")
        cc_list = []
        if random.random() < 0.4:
            c_name, c_email = pick_counsel()
            cc_list.append(c_email)

        include_priv = (random.random() < 0.5) or bool(cc_list)
        include_phone = (random.random() < 0.5)
        include_counsel_ref = bool(cc_list)

        lang = pick_lang()
        subject = make_subject(include_priv)
        dt = rand_date(start, end)

        # Body selection (respect the plan for dup/near-dup)
        if i in body_plan:
            body = body_plan[i]
        else:
            body = make_body(lang, include_priv, include_phone, include_counsel_ref)

        # Attachments
        attachments = []
        if random.random() < 0.35:
            k = random.randint(1, 2)
            attachments = random.sample(attachment_pool, k=k)

        # Write files
        if is_eml:
            fname = f"mail-{i+1:04d}.eml"
            write_eml(out_dir / fname, (from_name, from_email), recipients or [from_email],
                      cc_list, subject, dt, body, attachments)
            manifest_rows.append([fname, "eml", from_email, ";".join(recipients), ";".join(cc_list),
                                  subject, dt.isoformat(), lang,
                                  str(i in used_in_dups), str(i in near_dup_indices), ";".join(attachments)])
        else:
            fname = f"mail-{i+1:04d}.json"
            write_json(out_dir / fname, from_email, recipients or [from_email], cc_list,
                       subject, dt, body, attachments)
            manifest_rows.append([fname, "json", from_email, ";".join(recipients), ";".join(cc_list),
                                  subject, dt.isoformat(), lang,
                                  str(i in used_in_dups), str(i in near_dup_indices), ";".join(attachments)])

    # Write manifest + dataset README
    with open(out_dir / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(manifest_rows)

    (out_dir / "README.md").write_text(
        "# Synthetic Sample Data\n\n"
        "- Generated by `scripts/generate_synthetic_data.py`\n"
        "- Contains EML and JSON items with:\n"
        "  - Privilege-like content and counsel recipients\n"
        "  - PII (emails + US phone numbers)\n"
        "  - **Exact duplicate clusters** and **near-duplicates**\n"
        "  - Multilingual bodies (EN/中文/FR)\n"
        "  - Attachment stubs in `attachments/`\n"
        "- See `manifest.csv` for a quick index of the dataset.\n",
        encoding="utf-8"
    )

    print(f"[generator] Planned duplicate clusters: {len(dup_clusters)} "
          f"({sum(len(c) for c in dup_clusters)} docs total).")
    print(f"[generator] Planned near-duplicates: {len(near_dup_indices)} docs.")

def parse_args():
    p = argparse.ArgumentParser(description="Generate rich synthetic data for ediscovery-starter.")
    p.add_argument("--out", default="00-setup/sample-data", help="Output directory for generated files")
    p.add_argument("--count", type=int, default=40, help="Total number of documents to generate")
    p.add_argument("--eml", type=int, default=28, help="How many EML messages (rest will be JSON)")
    p.add_argument("--json", type=int, default=12, help="How many JSON messages (if count mismatches, this will be adjusted)")
    p.add_argument("--dup-rate", type=float, default=0.15, help="Fraction of exact duplicates (same normalized body)")
    p.add_argument("--near-dup-rate", type=float, default=0.20, help="Fraction of near duplicates (minor variations)")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    out_dir = Path(args.out)
    generate_dataset(
        out_dir=out_dir,
        count=args.count,
        eml_count=args.eml,
        json_count=args.json,
        dup_rate=args.dup_rate,
        near_dup_rate=args.near_dup_rate,
    )
    print(f"Synthetic dataset generated in: {out_dir.resolve()}")