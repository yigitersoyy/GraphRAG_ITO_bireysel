import json

from notes_graphrag.ingestion.extraction import (
    anchor_unique_evidence,
    extraction_wire_schema,
    validate_extraction,
)


def output(quote, start=1, end=3):
    return json.dumps(
        {
            "entities": [
                {"local_id": "a", "name": "İpek", "kind": "Person"},
                {"local_id": "p", "name": "Atlas", "kind": "Project"},
            ],
            "claims": [
                {
                    "subject_local_id": "a",
                    "predicate": "WORKS_ON",
                    "object_local_id": "p",
                    "evidence": {"start": start, "end": end, "quote": quote},
                }
            ],
        }
    )


def validate(raw, text, prefix=""):
    return validate_extraction(
        raw, revision_id="r", revision_text=prefix + text, chunk_start=len(prefix), chunk_text=text
    )


def test_unicode_unique_quote_is_anchored_then_checked_in_the_revision():
    text = "İpek Atlas üzerinde çalışıyor."
    raw = output(text)
    assert not validate(raw, text).ok
    fixed = anchor_unique_evidence(raw, text)
    report = validate(fixed, text, prefix="Önceki not. ")
    assert report.ok and len(report.claims) == 1
    claim = report.claims[0]
    assert claim.evidence_start == len("Önceki not. ")
    assert ("Önceki not. " + text)[claim.evidence_start : claim.evidence_end] == text


def test_ambiguous_or_invented_quote_is_never_guessed():
    for text, quote in (
        ("İpek Atlas. İpek Atlas.", "İpek Atlas."),
        ("İpek Atlas üzerinde çalışıyor.", "İpek Atlas'ı yönetiyor."),
    ):
        raw = output(quote)
        assert anchor_unique_evidence(raw, text) == raw
        assert not validate(raw, text).ok


def test_valid_explicit_offsets_disambiguate_repeated_quotes():
    quote = "İpek Atlas."
    text = quote + " " + quote
    raw = output(quote, len(quote) + 1, len(text))
    assert anchor_unique_evidence(raw, text) == raw
    assert validate(raw, text).ok


def test_anchoring_does_not_make_invalid_ontology_valid():
    text = "İpek Atlas üzerinde çalışıyor."
    data = json.loads(output(text))
    data["claims"][0]["predicate"] = "INVENTED"
    assert not validate(anchor_unique_evidence(json.dumps(data), text), text).ok


def test_quote_only_wire_output_gets_source_owned_offsets():
    text = "İpek Atlas üzerinde çalışıyor."
    data = json.loads(output(text))
    data["claims"][0]["evidence"] = {"quote": text}
    raw = json.dumps(data)
    assert not validate(raw, text).ok
    assert validate(anchor_unique_evidence(raw, text), text).ok
    repeated = text + " " + text
    assert not validate(anchor_unique_evidence(raw, repeated), repeated).ok


def test_extraction_wire_schema_does_not_delegate_character_counting_to_the_model():
    schema = extraction_wire_schema()
    assert "schema_version" not in schema["properties"]
    claim = schema["properties"]["relations"]["items"]
    entity = claim["properties"]["subject"]
    assert "mentions" not in entity["properties"]
    assert "NEGATED" in claim["properties"]["polarity"]["enum"]
    assert "USES" in claim["properties"]["predicate"]["enum"]
    assert "quote" in claim["properties"]
    assert "start" not in claim["properties"] and "end" not in claim["properties"]


def test_unknown_legacy_schema_version_is_rejected():
    text = "İpek Atlas üzerinde çalışıyor."
    data = json.loads(output(text))
    data["schema_version"] = "CURRENT_VERSION"
    assert not validate(anchor_unique_evidence(json.dumps(data), text), text).ok


def test_field_guidance_survives_enum_ref_inlining():
    schema = extraction_wire_schema()
    properties = schema["properties"]["relations"]["items"]["properties"]
    assert "POSSIBLE" in properties["modality"]["description"]
    assert "Future time is not negation" in properties["polarity"]["description"]
    assert schema["properties"]["relations"]["minItems"] == 0
