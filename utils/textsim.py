# utils/textsim.py
from __future__ import annotations
from typing import Dict, List, Tuple, Set

def _tokenize(text: str) -> List[str]:
    return [t for t in text.split() if t]

def _shingles(tokens: List[str], k: int = 5) -> Set[Tuple[str, ...]]:
    if len(tokens) < k:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i:i+k]) for i in range(len(tokens) - k + 1)}

def jaccard(a: Set[Tuple[str, ...]], b: Set[Tuple[str, ...]]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def cluster_near_duplicates(
    texts: Dict[str, str],
    k: int = 5,
    threshold: float = 0.85
) -> List[Tuple[str, List[Tuple[str, float]]]]:
    """
    Greedy clustering by Jaccard similarity of k-shingles.
    Returns list of clusters: [(rep_id, [(file_id, sim), ...]), ...] with size >=2
    """
    # Precompute shingles
    shingle_map: Dict[str, Set[Tuple[str, ...]]] = {fid: _shingles(_tokenize(txt), k) for fid, txt in texts.items()}

    unassigned = set(texts.keys())
    clusters: List[Tuple[str, List[Tuple[str, float]]]] = []

    for fid in list(unassigned):
        if fid not in unassigned:
            continue
        base = shingle_map[fid]
        group = [(fid, 1.0)]
        assigned = {fid}
        for other in list(unassigned):
            if other in assigned:
                continue
            sim = jaccard(base, shingle_map[other])
            if sim >= threshold:
                group.append((other, sim))
                assigned.add(other)
        if len(group) >= 2:
            clusters.append((fid, group))
            unassigned -= assigned
        else:
            unassigned.discard(fid)

    return clusters