"""Extensions' gates and notices: a gate holds sessions like a pause (stored, unchecked, no model calls) until
`release_held`, a broken gate lets sessions through, and the notices endpoint lists what providers return."""

import logging

import pytest
import test_checks
from conftest import WS
from test_analysis import model_calls
from test_checks import session

from sopops_server import extensions
from sopops_server.auth.access import SESSION, kind_of
from sopops_server.pipeline.types import SessionRef

env = test_checks.env  # the checks' workspace, with fake models
OVER = "Held by the extension."


@pytest.fixture(autouse=True)
def clean():
    extensions.clear()
    yield
    extensions.clear()


def test_a_gate_holds_sessions_and_release_held_checks_them(env):
    gate = {"on": True, "asked": []}

    def hold(ws, sid):
        gate["asked"].append((ws, sid))
        return OVER if gate["on"] else None

    extensions.add_analysis_gate(hold)
    s = env.send(session("held"))
    assert s["status"] == "received" and s["status_reason"] == OVER and s["checks"] == []
    assert len(s["turns"]) == 8  # the transcript is there
    assert model_calls(env) == []
    assert gate["asked"] == [("demo", s["id"])]

    assert extensions.release_held(env.store, "demo", OVER) == 1  # still held: the gate decides again
    assert env.client.get(f"{WS}/sessions/{s['id']}").json()["status_reason"] == OVER

    gate["on"] = False
    assert extensions.release_held(env.store, "demo", OVER) == 1
    s = env.client.get(f"{WS}/sessions/{s['id']}").json()
    assert s["status"] == "checked" and model_calls(env)
    assert extensions.release_held(env.store, "demo", OVER) == 0


def test_release_held_queues_only_sessions_held_for_that_reason(env):
    reasons = {"a": "Reason A.", "b": "Reason B."}
    held: dict[str, str] = {}
    extensions.add_analysis_gate(lambda ws, sid: held.get(sid))
    a, b = env.send(session("a")), env.send(session("b"))  # checked: nothing held yet
    assert a["status"] == b["status"] == "checked"
    held.update({a["id"]: reasons["a"], b["id"]: reasons["b"]})
    for sid in held:  # processed again: held this time
        rev = env.store.sessions.load("demo", sid).payload_hash
        env.client.app.state.jobs.process_session(SessionRef(workspace_id="demo", session_id=sid, revision=rev))
    assert env.client.get(f"{WS}/sessions/{a['id']}").json()["status_reason"] == reasons["a"]

    held.pop(a["id"])
    assert extensions.release_held(env.store, "demo", reasons["a"]) == 1
    assert env.client.get(f"{WS}/sessions/{a['id']}").json()["status"] == "checked"
    b2 = env.client.get(f"{WS}/sessions/{b['id']}").json()
    assert b2["status"] == "received" and b2["status_reason"] == reasons["b"]
    assert extensions.release_held(env.store, "other-ws", reasons["b"]) == 0


def test_a_gate_that_raises_lets_the_session_through(env, caplog):
    def broken(ws, sid):
        raise RuntimeError("the extension is down")

    extensions.add_analysis_gate(broken)
    with caplog.at_level(logging.ERROR, logger="sopops.extensions"):
        s = env.send(session("through"))
    assert s["status"] == "checked" and model_calls(env)
    assert "analysis gate" in caplog.text


def test_a_paused_workspace_holds_before_any_gate(env):
    asked = []
    extensions.add_analysis_gate(lambda ws, sid: asked.append(sid) or OVER)
    env.client.put(f"{WS}/analysis", json={"paused": True})
    s = env.send(session("paused"))
    assert s["status_reason"] == "Analysis is paused." and asked == []


def test_notices_list_what_providers_return_and_skip_one_that_raises(env, caplog):
    assert env.client.get(f"{WS}/notices").json() == {"notices": []}

    def broken(ws):
        raise RuntimeError("down")

    extensions.add_notices(broken)
    extensions.add_notices(lambda ws: [extensions.Notice(id=f"{ws}-1", level="warning", title="Heads up", body="Something.",
                                                         action_label="More", action_url="https://example.com")])
    extensions.add_notices(lambda ws: [extensions.Notice(id="b", level="blocking", title="Stop", body="Look.")])
    with caplog.at_level(logging.ERROR, logger="sopops.extensions"):
        res = env.client.get(f"{WS}/notices")
    assert res.status_code == 200
    assert res.json() == {"notices": [
        {"id": "demo-1", "level": "warning", "title": "Heads up", "body": "Something.", "action_label": "More", "action_url": "https://example.com"},
        {"id": "b", "level": "blocking", "title": "Stop", "body": "Look.", "action_label": None, "action_url": None},
    ]}
    assert "notice provider" in caplog.text


def test_any_member_reads_notices():
    assert kind_of("list_notices") == SESSION
