"""Relationship-first output never bypasses source, identity or ontology validation."""

import json

from notes_graphrag.ingestion.extraction import anchor_unique_evidence, validate_extraction

TEXT = "Derya Project Maple'da çalışıyor."


def relation(name="Project Maple", local_id="p"):
    return {
        "quote": TEXT,
        "predicate": "WORKS_ON",
        "modality": "ASSERTED",
        "polarity": "POSITIVE",
        "subject": {"local_id": "a", "kind": "Person", "name": "Derya"},
        "object": {"local_id": local_id, "kind": "Project", "name": name},
        "temporal_text": None,
    }


def validate(data, text=TEXT):
    raw = anchor_unique_evidence(json.dumps(data), text)
    return validate_extraction(
        raw, revision_id="r", revision_text=text, chunk_start=0, chunk_text=text
    )


def test_relation_first_output_retains_qualifiers_and_source_offsets():
    r = relation()
    r["modality"] = "POSSIBLE"
    out = validate({"relations": [r]})
    assert out.ok and len(out.claims) == 1
    c = out.claims[0]
    assert c.object.name == "Project Maple" and c.modality == "POSSIBLE"
    assert TEXT[c.evidence_start : c.evidence_end] == TEXT


def test_reused_id_with_different_identity_and_mixed_root_are_rejected():
    assert not validate({"relations": [relation(), relation(local_id="a")]}).ok
    assert not validate({"relations": [relation()], "entities": [], "claims": []}).ok


def test_same_name_with_distinct_local_ids_is_not_merged_by_wire_conversion():
    out = validate({"relations": [relation(local_id="p1"), relation(local_id="p2")]})
    assert out.ok and out.claims[0].object.local_id != out.claims[1].object.local_id


def test_invalid_relationship_or_fabricated_quote_is_not_silently_dropped():
    for key, value in (("predicate", "WORKS_AT"), ("quote", "Derya leads Project Maple.")):
        r = relation()
        r[key] = value
        assert not validate({"relations": [r]}).ok
    assert validate({"relations": []}).ok


def test_source_unambiguously_prefixed_project_name_is_required():
    out = validate({"relations": [relation(name="Maple")]})
    assert not out.ok and "Project Maple" in out.errors[0]
    # A separate bare occurrence could refer to a different project. Never guess a merge.
    out = validate({"relations": [relation(name="Maple")]}, TEXT + " Maple is also mentioned.")
    assert out.ok
