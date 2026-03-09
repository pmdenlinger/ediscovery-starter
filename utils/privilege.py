# utils/privilege.py
from __future__ import annotations
import re
from typing import Dict, List, Tuple

COUNSEL_DOMAIN_HINTS = {
    "outsidecounsel.com", "lawfirm.co", "counsel.example"
}

# Weighted keyword dictionary (lowercase)
KEYWORD_WEIGHTS: Dict[str, int] = {
    "attorney-client": 30,
    "work product": 25,
    "legal advice": 20,
    "solicitor-client": 20,
    "privileged": 15,
    "outside counsel": 15,
    "confidential legal": 10,
    "counsel": 10,
}

SUBJECT_TOKENS = [
    "privileged", "attorney-client", "work product", "confidential", "counsel review"
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")

def _domains_from_fields(*fields: str) -> List[str]:
    doms: List[str] = []
    for f in fields:
        for m in EMAIL_RE.findall(f or ""):
            doms.append(m.lower())
    return doms

def privilege_score(subject: str, body_text: str, from_f: str, to_f: str, cc_f: str) -> Tuple[int, List[str]]:
    """
    Returns (score 0..100, reasons[])
    Heuristic-only, for triage—not a legal determination.
    """
    score = 0
    reasons: List[str] = []

    # Keyword weights in body (case-insensitive, simple substring)
    text_l = (body_text or "").lower()
    for k, w in KEYWORD_WEIGHTS.items():
        if k in text_l:
            score += w
            reasons.append(f"keyword:{k}+{w}")

    # Subject token boost
    subj_l = (subject or "").lower()
    for token in SUBJECT_TOKENS:
        if token in subj_l:
            score += 10
            reasons.append(f"subject:{token}+10")
            break  # avoid stacking multiple tokens from subject

    # Counsel domain proximity (any To/Cc/From includes known counsel domains)
    doms = set(_domains_from_fields(from_f or "", to_f or "", cc_f or ""))
    if any(any(hint in d for hint in COUNSEL_DOMAIN_HINTS) for d in doms):
        score += 15
        reasons.append("counsel_domain+15")

    # Cc includes counsel? add an extra nudge (modeling triage behavior)
    if cc_f and any(h in cc_f.lower() for h in COUNSEL_DOMAIN_HINTS):
        score += 5
        reasons.append("cc_counsel+5")

    # Cap at 100
    score = min(score, 100)
    return score, reasons