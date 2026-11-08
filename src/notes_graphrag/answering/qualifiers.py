"""Source-limited fallback for explicit certainty/current-use questions."""

import re

from notes_graphrag.answering.citations import AnswerOutput, AnswerSentence
from notes_graphrag.retrieval.evidence import EvidencePack
from notes_graphrag.retrieval.lexical import tokens


def qualified_use_fallback(question: str, pack: EvidencePack) -> AnswerOutput | None:
    q = " ".join(tokens(question))
    english = re.match(r"^(is|does|will|has|can)\b", q) and re.search(
        r"\b(certain|definite|confirmed|currently|now|already)\b", q
    )
    turkish = re.search(r"\b(kesin|halen|halihazırda|şu an)\b", q) and re.search(
        r"\b(mi|mı|mu|mü)\b", q
    )
    if not (english or turkish) or pack.limited_by_budget:
        return None

    def mentions(name: str, text: str) -> bool:
        return " " + " ".join(tokens(name)) + " " in " " + " ".join(tokens(text)) + " "

    matches = [
        (c, ids)
        for c, ids in pack.claims
        if c.predicate == "USES" and mentions(c.subject, question) and mentions(c.object, question)
    ]
    if not matches or len({(c.subject_id, c.object_id) for c, _ in matches}) != 1:
        return None
    if any(
        c.polarity != "POSITIVE" or c.modality not in {"POSSIBLE", "PLANNED"} for c, _ in matches
    ):
        return None
    if len({c.modality for c, _ in matches}) != 1:
        return None
    claim, ids = matches[0]
    represented = {eid for _, eids in matches for eid in eids}
    if any(
        mentions(claim.subject, i.text)
        and mentions(claim.object, i.text)
        and i.evidence_id not in represented
        for i in pack.items
    ):
        return None
    marker = (
        r"\b(may|might|could|possible|belki)\b|\b\w+(?:ebilir|abilir)\w*\b"
        if claim.modality == "POSSIBLE"
        else r"\b(plan\w*|approved|scheduled|kararlaştır\w*)\b"
    )
    if not re.search(marker, claim.evidence_quote, re.I) or len(claim.evidence_quote) > 650:
        return None
    valid_ids = [eid for eid in ids if pack.item(eid) is not None]
    if not any(
        i.note_id == claim.note_id
        and i.revision_id == claim.revision_id
        and claim.evidence_quote in i.text
        for i in pack.items
        if i.evidence_id in valid_ids
    ):
        return None
    label = (
        ("bir olasılık" if claim.modality == "POSSIBLE" else "bir plan")
        if turkish
        else ("a possibility" if claim.modality == "POSSIBLE" else "a plan")
    )
    text = (
        f"Kaynakta {label} belirtiliyor: “{claim.evidence_quote}”"
        if turkish
        else f"The cited source describes {label}: “{claim.evidence_quote}”"
    )
    return AnswerOutput(
        status="partial",
        sentences=[AnswerSentence(text=text, evidence_ids=valid_ids)],
        missing_information=["Kesin/güncel kullanım" if turkish else "Confirmed/current usage"],
    )
