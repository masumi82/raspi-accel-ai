from edge.buffer import OfflineBuffer


def test_add_and_pending(tmp_path):
    buf = OfflineBuffer(str(tmp_path / "b.jsonl"))
    buf.add({"a": 1})
    buf.add({"b": 2})
    assert buf.pending() == [{"a": 1}, {"b": 2}]


def test_flush_all_success_clears(tmp_path):
    path = str(tmp_path / "b.jsonl")
    buf = OfflineBuffer(path)
    buf.add({"a": 1})
    buf.add({"b": 2})
    sent = []
    n = buf.flush(lambda ev: sent.append(ev))
    assert n == 2
    assert sent == [{"a": 1}, {"b": 2}]
    assert buf.pending() == []


def test_flush_stops_on_failure_keeps_remainder(tmp_path):
    path = str(tmp_path / "b.jsonl")
    buf = OfflineBuffer(path)
    buf.add({"a": 1})
    buf.add({"b": 2})
    buf.add({"c": 3})

    def publish(ev):
        if ev == {"b": 2}:
            raise ConnectionError("offline")

    n = buf.flush(publish)
    assert n == 1
    assert buf.pending() == [{"b": 2}, {"c": 3}]


def test_pending_empty_when_no_file(tmp_path):
    buf = OfflineBuffer(str(tmp_path / "missing.jsonl"))
    assert buf.pending() == []
