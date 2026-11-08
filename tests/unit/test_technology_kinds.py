import pytest

from notes_graphrag.answering.technology_kinds import known_technology_kind


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Ruby programlama dilini kullanıyor.", "PROGRAMMING_LANGUAGE"),
        ("uses TypeScript.", "PROGRAMMING_LANGUAGE"),
        ("Uses PostgreSQL.", "DATABASE"),
        ("Neo4j kullanıyor.", "DATABASE"),
        ("Project Ruby uses SQLite.", "DATABASE"),
        ("Project PostgreSQL is a project.", None),
        ("Python, not PostgreSQL.", None),
        ("Rubyland and SQLitely.", None),
        ("an unregistered tool", None),
    ],
)
def test_catalogue_is_bounded_and_does_not_classify_project_names_or_mixed_values(text, expected):
    assert known_technology_kind(text) == expected
