"""Conservative citation-chain coverage, not a semantic truth or relevance classifier."""

from __future__ import annotations

from collections import defaultdict, deque

from notes_graphrag.answering.citations import AnswerOutput
from notes_graphrag.retrieval.evidence import EvidencePack
from notes_graphrag.retrieval.lexical import tokens


def citation_chain_errors(question: str, out: AnswerOutput, pack: EvidencePack) -> list[str]:
    if out.status == "insufficient_evidence":
        return []
    names: dict[str, str] = {}
    by_name: dict[tuple[str, ...], set[str]] = defaultdict(set)
    adjacent: dict[str, list[tuple[str, set[str]]]] = defaultdict(list)
    for claim, eids in pack.claims:
        for eid, name in ((claim.subject_id, claim.subject), (claim.object_id, claim.object)):
            names[eid] = name
            by_name[tuple(tokens(name))].add(eid)
        adjacent[claim.subject_id].append((claim.object_id, set(eids)))
        adjacent[claim.object_id].append((claim.subject_id, set(eids)))

    def mentioned(text: str) -> set[str]:
        padded = " " + " ".join(tokens(text)) + " "
        return {
            next(iter(ids))
            for words, ids in by_name.items()
            if words and len(ids) == 1 and " " + " ".join(words) + " " in padded
        }

    seeds = mentioned(question)
    if not seeds:
        return []
    targets = mentioned(" ".join(s.text for s in out.sentences)) - seeds
    cited = {eid for sentence in out.sentences for eid in sentence.evidence_ids}

    def connected(start: str, end: str, allowed: set[str] | None) -> bool:
        queue = deque([(start, 0)])
        seen = {start}
        while queue:
            current, depth = queue.popleft()
            if current == end:
                return True
            if depth == 2:
                continue
            for neighbor, evidence in adjacent[current]:
                if neighbor not in seen and (allowed is None or evidence & allowed):
                    seen.add(neighbor)
                    queue.append((neighbor, depth + 1))
        return False

    errors = []
    for target in sorted(targets):
        possible = [seed for seed in seeds if connected(seed, target, None)]
        if possible and not any(connected(seed, target, cited) for seed in possible):
            groups = sorted(
                {eid for seed in possible for _, eids in adjacent[seed] for eid in eids}
            )
            errors.append(
                f"Missing cited source-chain link from question entity to {names[target]}; "
                f"question-entity support is in {groups}. Cite a complete supported chain."
            )
    return errors[:5]
