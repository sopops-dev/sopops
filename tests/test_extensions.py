"""Extensions' gates and notices: a gate holds sessions like a pause (stored, unchecked, no model calls) until
`release_held`, a broken gate lets sessions through, and the notices endpoint lists what providers return."""

import logging

import pytest
import test_checks
from conftest import WS
from test_analysis import model_calls
from test_checks import session

from sopops_server import extensions
from sopops_server.auth.access import ADMIN, SESSION, kind_of
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


def test_settings_sections_list_what_providers_return_first_id_wins_and_skip_one_that_raises(env, caplog):
    assert env.client.get(f"{WS}/settings/sections").json() == {"sections": []}

    def broken(ws):
        raise RuntimeError("down")

    S, R, A = extensions.SettingsSection, extensions.SettingsRow, extensions.SettingsAction
    extensions.add_settings_sections(broken)
    extensions.add_settings_sections(lambda ws: [S(
        id="storage", title="Storage", description=f"For {ws}.", icon="gauge", note="Resets monthly.",
        rows=[R("Region", "us-east-1"), R("Recordings", "40 of 100 GB", used=40, limit=100, note="Counted nightly.")],
        actions=[A("Change", "https://example.com/change", "primary"), A("Details", "https://example.com/details")])])
    extensions.add_settings_sections(lambda ws: [S(id="storage", title="Second"), S(id="about", title="About")])
    with caplog.at_level(logging.ERROR, logger="sopops.extensions"):
        res = env.client.get(f"{WS}/settings/sections")
    assert res.status_code == 200
    assert res.json() == {"sections": [
        {"id": "storage", "title": "Storage", "description": "For demo.", "icon": "gauge", "note": "Resets monthly.",
         "rows": [{"label": "Region", "value": "us-east-1", "used": None, "limit": None, "note": None},
                  {"label": "Recordings", "value": "40 of 100 GB", "used": 40.0, "limit": 100.0, "note": "Counted nightly."}],
         "actions": [{"label": "Change", "url": "https://example.com/change", "kind": "primary"},
                     {"label": "Details", "url": "https://example.com/details", "kind": "secondary"}]},
        {"id": "about", "title": "About", "description": None, "icon": None, "note": None, "rows": [], "actions": []},
    ]}
    assert "settings section provider" in caplog.text


def test_any_member_reads_settings_sections():
    assert kind_of("list_settings_sections") == SESSION


def test_intent_goes_on_with_setup_without_a_provider_and_follows_the_first_url(env, caplog):
    body = {"intent": "dev-year", "next": "/w/demo/setup?step=people&flow=first"}
    assert env.client.post(f"{WS}/intent", json=body).json() == {"url": None}

    def broken(ws, intent, back):
        raise RuntimeError("down")

    seen = []
    extensions.add_signup_intents(broken)
    extensions.add_signup_intents(lambda ws, intent, back: seen.append((ws, intent, back)) or None)
    extensions.add_signup_intents(lambda ws, intent, back: f"https://pay.example.com/{intent}" if intent == "dev-year" else None)
    extensions.add_signup_intents(lambda ws, intent, back: "https://later.example.com")
    with caplog.at_level(logging.ERROR, logger="sopops.extensions"):
        res = env.client.post(f"{WS}/intent", json=body)
    assert res.json() == {"url": "https://pay.example.com/dev-year"}
    assert seen == [("demo", "dev-year", "http://testserver/w/demo/setup?step=people&flow=first")]
    assert "signup intent provider" in caplog.text


@pytest.mark.parametrize("body", [{"intent": "Dev Year"}, {"intent": ""}, {"intent": "dev", "next": "//evil.example.com"},
                                  {"intent": "dev", "next": "https://evil.example.com"}])
def test_intent_rejects_odd_words_and_paths_off_the_app(env, body):
    assert env.client.post(f"{WS}/intent", json=body).status_code == 422


def test_owners_and_admins_follow_intents():
    assert kind_of("follow_intent") == ADMIN
