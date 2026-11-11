from datetime import UTC, datetime

import pytest

from notes_graphrag.ingestion.topics import assign_automatic_topic, suggested_topic
from notes_graphrag.persistence.workspace import Topic


@pytest.mark.parametrize(
    "title,expected",
    [
        ("M02_TEDBIRLER_YONETMELIK_PART_003", "TEDBIRLER YONETMELIK"),
        ("P03 PAYTR_INFORMATION_SECURITY_POLICY", "PAYTR INFORMATION SECURITY POLICY"),
        ("P03_PAYTR_INFORMATION_SECURITY_POLICY.pdf", "PAYTR INFORMATION SECURITY POLICY"),
        ("M01_5549_KANUN", "5549 KANUN"),
        ("01_kvkk_6698_kanun_bolum_01", "KVKK"),
        ("01_kvkk_6698_kanun_bolum_02.pdf", "KVKK"),
        ("02_kvkk_veri_imha_yonetmeligi_bolum_01", "KVKK"),
        ("03_bddk_5411_bankacilik_kanunu_bolum_10", "BDDK"),
        ("03-bddk-5411-bankacilik-kanunu", "BDDK"),
        ("05_Öğrenme_notları", "Öğrenme"),
        ("Normal bir not başlığı", None),
        ("2026", None),
        ("01_02_03", None),
    ],
)
def test_filename_families(title, expected):
    assert suggested_topic(title) == expected


def test_existing_topic_case_and_multiword_name_are_preserved():
    topics = [Topic("kvkk", "kvkk", "purple"), Topic("is", "İş Kanunu", "blue")]
    assert suggested_topic("02_KVKK_yonetmelik", topics) == "kvkk"
    assert suggested_topic("İş Kanunu açıklamaları", topics) == "İş Kanunu"


def test_manual_unsorted_assignment_is_not_automatically_reversed():
    from notes_graphrag.api.dependencies import build_context
    from notes_graphrag.core.config import Settings

    ctx = build_context(Settings(_env_file=None), demo=True, backend="memory")
    sub = ctx.notes.create("01_kvkk_kanun", "Test note.", "x")
    now = datetime.now(UTC)
    ctx.store.set_note_topic(sub.note.note_id, None, 0, now)
    assert assign_automatic_topic(ctx.store, sub.note.note_id, now) is None
    assert ctx.store.get_note(sub.note.note_id).topic_id is None
