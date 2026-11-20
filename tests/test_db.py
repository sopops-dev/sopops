"""The schema: Alembic migrations, databases from before Alembic, and the UI's catch-all route."""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from conftest import SOP_BIN, WS
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from sopops_server import Sop, Store, create_app
from sopops_server.db import INITIAL, alembic_config, current_revision, upgrade
from sopops_server.orm import metadata


def test_migrations_match_the_models(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    upgrade(engine)
    assert current_revision(engine) == ScriptDirectory.from_config(alembic_config()).get_current_head()  # one head
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), metadata) == []
    upgrade(engine)  # again: nothing to do


def test_a_database_from_before_alembic_is_stamped_and_kept(tmp_path, files):
    url = f"sqlite:///{tmp_path / 'old.db'}"
    engine = create_engine(url)
    cfg = alembic_config()
    with engine.begin() as conn:  # the tables as sopops made them before Alembic: the initial revision's, unstamped
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, INITIAL)
        conn.execute(text("DROP TABLE alembic_version"))
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO workspaces (workspace, current_release) VALUES ('demo', NULL)"))
    assert "alembic_version" not in inspect(engine).get_table_names()

    client = TestClient(create_app(Store(url, Sop(SOP_BIN))))
    assert current_revision(engine) == ScriptDirectory.from_config(alembic_config()).get_current_head()  # one head
    assert client.get("/v1/workspaces").json() == [{"workspace": "demo", "current_release": None}]
    assert client.put(f"{WS}/files", json={"files": files}).status_code == 200


def test_ui_routes_fall_back_to_the_app_and_api_404s_stay_json(client):
    page = client.get("/w/demo/agents/tonys-pizza")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    missing = client.get("/v1/nothing-here")
    assert missing.status_code == 404 and missing.json() == {"detail": "Not Found"}
    assert client.get("/v1/workspaces").status_code == 200
    assert client.get("/openapi.json").json()["paths"]["/v1/workspaces"]["get"]["operationId"] == "list_workspaces"


def test_existing_repo_connections_get_raad_identities(client):
    from sqlmodel import Session
    from sopops_server import github
    from sopops_server.orm import RepoConnection
    from conftest import downgrade

    store = client.app.state.store
    for ws in ("first", "second"):
        with store._locked(ws) as db:
            db.add(RepoConnection(workspace=ws, owner="acme", repo="agents", base_branch="main", path="sops", auth="token",
                                  ciphertext="encrypted-test-token", hint="token", pulled_sha="a" * 40,
                                  sync_pr_url="https://github.com/acme/agents/pull/1", sync_pr_state="open",
                                  created_at=github._now(), updated_at=github._now()))
    downgrade(store.engine, "0045")
    upgrade(store.engine)
    with Session(store.engine) as db:
        rows = [db.get(RepoConnection, ws) for ws in ("first", "second")]
        assert len({row.connection_id for row in rows}) == 2
        assert len({row.generation for row in rows}) == 2
        for row in rows:
            assert len(row.connection_id) == len(row.generation) == 32
            assert row.pulled_sha == "a" * 40 and row.sync_pr_state == "open"
            assert row.ciphertext == "encrypted-test-token"
            assert row.proposal_head is row.pending_operation is row.pending_request is None
