from datetime import UTC, datetime, timedelta

from notes_graphrag.persistence.memory import MemoryStore
from notes_graphrag.persistence.models import GATE_IDLE, GATE_RECOVERING
from notes_graphrag.providers.gate import InferenceGate


def test_idle_worker_can_recover_expired_holder_without_an_interactive_request():
    now = datetime.now(UTC)
    store = MemoryStore()
    calls = []
    gate = InferenceGate(store, "lm", clock=lambda: now, probe=lambda: calls.append("probe"))
    assert store.gate_try_acquire("lm", "dead", "dead-token", now - timedelta(seconds=2), 1)
    assert not gate.try_recover()  # fence expired owner first
    assert store.gate_status("lm").state == GATE_RECOVERING
    assert gate.try_recover()
    assert store.gate_status("lm").state == GATE_IDLE
    assert calls == ["probe"]


def test_proactive_recovery_never_probes_a_fresh_busy_holder():
    now = datetime.now(UTC)
    store = MemoryStore()
    calls = []
    gate = InferenceGate(store, "lm", clock=lambda: now, probe=lambda: calls.append("probe"))
    assert store.gate_try_acquire("lm", "active", "token", now, 60)
    assert not gate.try_recover()
    assert calls == []
    assert store.gate_status("lm").owner_id == "active"
