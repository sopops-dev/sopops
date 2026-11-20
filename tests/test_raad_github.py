"""Exercise the real native SDK through the SOP API, not HTTPX mocks."""

import subprocess

import pytest
import raad
from cryptography.fernet import Fernet

from conftest import WS
from raad_github_server import GitHubServer
from sopops_server import github, repo_sync, raad_backend
from sopops_server.errors import Conflict
from sopops_server.orm import RepoConnection


def git(path, *args):
    return (
        subprocess.check_output(
            ["git", "-C", str(path), *args], stderr=subprocess.DEVNULL
        )
        .decode()
        .strip()
    )


@pytest.fixture
def native(client, files, tmp_path, monkeypatch):
    monkeypatch.setenv("SOPOPS_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("SOPOPS_GITHUB_BACKEND", "auto")
    monkeypatch.delenv("SOPOPS_GITHUB_API_URL", raising=False)
    store = client.app.state.store
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "-b", "main")
    git(source, "config", "user.name", "raad demo")
    git(source, "config", "user.email", "demo@example.invalid")
    git(source, "config", "commit.gpgsign", "false")
    git(source, "config", "uploadpack.allowFilter", "true")
    for p, content in {
        **{f"sops/{p}": c for p, c in files.items()},
        "README.md": "unrelated",
        "sops/build/invalid.json": "invalid",
    }.items():
        dest = source / p
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    git(source, "add", ".")
    git(source, "commit", "-qm", "initial")
    server = GitHubServer(source, repository="acme/agents")
    from sopops_server import github_client

    monkeypatch.setattr(github_client, "api_url", lambda: server.url)
    connected = client.post(
        f"{WS}/repo",
        json={"owner": "acme", "repo": "agents", "path": "sops", "token": "test-token"},
    )
    assert connected.status_code == 200, connected.text
    real = raad_backend._repository

    def repository(store, conn):
        # Keep the production cache identity, token callback and options. Only
        # redirect Git/API transports to an isolated local repository/server.
        monkeypatch.setenv("SOPOPS_RAAD_CACHE_DIR", str(tmp_path / "cache"))
        repo = real(store, conn)
        cache = next((tmp_path / "cache").glob("*"))
        objects = next(cache.glob("*")) / "objects.git"
        if not objects.exists():
            objects.mkdir()
            git(objects, "init", "--bare")
            git(objects, "remote", "add", "origin", str(source))
        # Reopen with exactly the same options, including the real callback.
        return raad.Repository(
            "acme/agents",
            root=conn.path,
            branch=conn.base_branch,
            cache_dir=cache,
            token_provider=repo._token_provider,
            excluded_paths=["build"],
            limits={"response_bytes": 64 * 1024 * 1024},
            allow_proposals=True,
            github_api_url=server.url,
        )

    monkeypatch.setattr(raad_backend, "_repository", repository)
    # Any accidental content call through the legacy implementation fails loudly.
    for name in ("read_folder", "commit_files", "branch_head"):
        monkeypatch.setattr(
            github,
            name,
            lambda *a, **kw: pytest.fail("raad workflow called legacy content code"),
        )
    yield store, source, server
    server.close()


def push(source, changes):
    for p, text in changes.items():
        dest = source / "sops" / p
        if text is None:
            dest.unlink()
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
    git(source, "add", ".")
    git(source, "commit", "-qm", "remote change")
    return git(source, "rev-parse", "HEAD")


def test_inspect_import_sync_send_reuse_and_status(client, native, files):
    store, source, server = native
    response = client.get(f"{WS}/repo/project")
    assert response.status_code == 200
    inspected = response.json()
    assert inspected["state"] == "valid"
    response = client.post(f"{WS}/repo/pull", json={})
    assert response.status_code == 200, response.text
    pulled = response.json()
    assert pulled["files"] == len(files)
    assert all(
        not p.startswith("build/") for p in github.read_project(store, "demo")[0]
    )
    # A remote addition syncs into drafts. Replaying an old event reads the current head.
    sha = push(source, {"notes.txt": "from GitHub\n"})
    got = repo_sync.sync(store, "demo", sha=pulled["sha"])
    assert got["sha"] == sha and got["changed"]
    store.edit("demo", {"notes.txt": "edited here\n"})
    response = client.post(f"{WS}/repo/send")
    assert response.status_code == 200, response.text
    sent = response.json()
    assert not sent["updated"] and len(server.pulls) == 1
    conn = github.require(store, "demo")
    assert server.pulls[0]["head"] == f"sopops/{conn.connection_id}/sync"
    assert server.git("show", f"{conn.proposal_head}:README.md") == "unrelated"
    assert (
        server.git("show", f"{conn.proposal_head}:sops/build/invalid.json") == "invalid"
    )
    assert github.pr_status(store, "demo", sent["url"]) == "open"
    store.edit("demo", {"notes.txt": "edited again\n"})
    assert repo_sync.send(store, "demo")["updated"] and len(server.pulls) == 1
    assert (
        server.git(
            "show", f"{github.require(store, 'demo').proposal_head}:sops/notes.txt"
        )
        == "edited again"
    )


def test_conflicts_invalid_remote_and_lost_write_recovery(native):
    store, source, server = native
    push(source, {"notes.txt": "original\n"})
    github.pull(store, "demo")
    store.edit("demo", {"notes.txt": "local\n"})
    push(source, {"notes.txt": "remote\n"})
    got = repo_sync.sync(store, "demo")
    assert got["conflicts"] == ["notes.txt"]
    assert repo_sync.conflict(store, "demo", "notes.txt")["ours"] == "local\n"
    with pytest.raises(Conflict):
        repo_sync.send(store, "demo")
    repo_sync.resolve(store, "demo", "notes.txt", "mine")
    server.fail_pr = 1
    with pytest.raises(github.GitHubError):
        repo_sync.send(store, "demo")
    pending = github.require(store, "demo")
    assert pending.pending_operation and pending.pending_request
    store.edit("demo", {"notes.txt": "newer local\n"})
    recovered = repo_sync.send(store, "demo")
    assert recovered["url"] and len(server.pulls) == 1
    assert not github.require(store, "demo").pending_operation
    assert (
        next(
            f["content"]
            for f in store.head("demo", content=True)
            if f["path"] == "notes.txt"
        )
        == "newer local\n"
    )
    before = github.require(store, "demo").pulled_sha
    push(source, {"sop.yaml": "invalid: ["})
    assert github.inspect_project(store, "demo")["state"] == "invalid"
    got = repo_sync.sync(store, "demo")
    assert got["error"]
    assert github.require(store, "demo").pulled_sha == before
    assert (
        next(
            f["content"]
            for f in store.head("demo", content=True)
            if f["path"] == "notes.txt"
        )
        == "newer local\n"
    )


def test_concurrent_edit_recomputes_and_reconnect_is_fenced(native, monkeypatch):
    store, source, server = native
    github.pull(store, "demo")
    push(source, {"notes.txt": "remote\n"})
    original = repo_sync._apply
    calls = []

    def edit_before_apply(*args, **kwargs):
        if not calls:
            calls.append(True)
            store.edit("demo", {"other.txt": "local edit during fetch\n"})
        return original(*args, **kwargs)

    monkeypatch.setattr(repo_sync, "_apply", edit_before_apply)
    assert not repo_sync.sync(store, "demo")["error"]
    assert {"notes.txt", "other.txt"} <= {f["path"] for f in store.head("demo")}
    old = github.require(store, "demo")
    ours, token = repo_sync._capture(store, old)
    with store._locked("demo") as db:
        db.get(RepoConnection, "demo").generation = "reconnected"
    with pytest.raises(Conflict):
        original(
            store,
            old,
            token,
            repo_sync.Plan(changes={"notes.txt": "stale"}),
            ours,
            old.pulled_sha,
            None,
        )
    assert github.require(store, "demo").generation == "reconnected"


@pytest.mark.parametrize("state", ["missing", "invalid"])
def test_bootstrap_and_repair_proposals(native, files, state):
    store, source, server = native
    if state == "missing":
        git(source, "rm", "-r", "sops")
        git(source, "commit", "-qm", "remove SOP folder")
    else:
        push(source, {"sop.yaml": "invalid: ["})
    assert github.inspect_project(store, "demo")["state"] == state
    url = github.open_pull_request(
        store, "demo", files, "Set up SOPs", "Ready for review"
    )
    assert url.endswith("/pull/1")
    sha = server.git("rev-parse", server.pulls[0]["head"])
    assert server.git("show", f"{sha}:README.md") == "unrelated"
    assert "version:" in server.git("show", f"{sha}:sops/sop.yaml")
    assert github.require(store, "demo").pulled_sha is None


def test_human_branch_edit_and_noop_preserve_open_pr(native):
    store, source, server = native
    github.pull(store, "demo")
    store.edit("demo", {"notes.txt": "local\n"})
    first = repo_sync.send(store, "demo")
    store.edit("demo", {"notes.txt": None})
    posts = sum(method == "POST" for method, _, _ in server.requests)
    with pytest.raises(Conflict):
        repo_sync.send(store, "demo")
    assert sum(method == "POST" for method, _, _ in server.requests) == posts
    assert github.require(store, "demo").sync_pr_url == first["url"]
    conn = github.require(store, "demo")
    human = server.git(
        "commit-tree",
        server.git("rev-parse", conn.proposal_head + "^{tree}"),
        "-p",
        conn.proposal_head,
        data=b"human edit",
    )
    server.git("update-ref", f"refs/heads/sopops/{conn.connection_id}/sync", human)
    store.edit("demo", {"notes.txt": "new local\n"})
    with pytest.raises(github.GitHubError) as error:
        repo_sync.send(store, "demo")
    assert error.value.status == 409
    assert server.git("rev-parse", f"sopops/{conn.connection_id}/sync") == human
    assert github.require(store, "demo").sync_pr_url == first["url"]


def test_backend_selection_is_explicit(native, monkeypatch):
    store, _, _ = native
    conn = github.require(store, "demo")
    monkeypatch.setenv("SOPOPS_GITHUB_BACKEND", "legacy")
    assert raad_backend.backend(store, conn) is None
    monkeypatch.setenv("SOPOPS_GITHUB_BACKEND", "auto")
    monkeypatch.setenv("SOPOPS_GITHUB_API_URL", "https://enterprise.example/api/v3")
    assert raad_backend.backend(store, conn) is None
    monkeypatch.delenv("SOPOPS_GITHUB_API_URL")

    def unsupported(*args):
        raise raad.UnsupportedFeatureError("submodule")

    monkeypatch.setattr(raad_backend, "Backend", unsupported)
    assert raad_backend.backend(store, conn) is None

    def denied(*args):
        raise raad.PermissionDeniedError("token denied")

    monkeypatch.setattr(raad_backend, "Backend", denied)
    with pytest.raises(github.GitHubError):
        raad_backend.backend(store, conn)


def test_send_after_merge_recovers_the_new_pr(native):
    store, source, server = native
    github.pull(store, "demo")
    store.edit("demo", {"notes.txt": "first\n"})
    first = repo_sync.send(store, "demo")
    conn = github.require(store, "demo")
    git(source, "merge", "--ff-only", conn.proposal_head)
    server.pulls[0].update(state="closed", merged=True)
    assert repo_sync.follow_pr(store, "demo", force=True) == "merged"
    store.edit("demo", {"notes.txt": "second\n"})
    server.fail_pr = 1
    with pytest.raises(github.GitHubError):
        repo_sync.send(store, "demo")
    recovered = repo_sync.send(store, "demo")
    assert recovered["url"] != first["url"]
    assert len(server.pulls) == 2
    assert github.require(store, "demo").sync_pr_state == "open"


def test_stale_base_rejection_can_be_retried_with_fresh_sync(native, monkeypatch):
    store, source, server = native
    github.pull(store, "demo")
    store.edit("demo", {"notes.txt": "local\n"})
    original = raad_backend.Backend.propose
    moved = []

    def advance_before_write(self, *args, **kwargs):
        if not moved:
            moved.append(push(source, {"other.txt": "new remote file\n"}))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(raad_backend.Backend, "propose", advance_before_write)
    with pytest.raises(Conflict):
        repo_sync.send(store, "demo")
    assert not github.require(store, "demo").pending_operation
    assert not server.pulls
    assert repo_sync.send(store, "demo")["url"]
    assert github.require(store, "demo").pulled_sha == moved[0]


def test_invalid_draft_request_can_be_fixed_and_sent(native):
    store, source, server = native
    github.pull(store, "demo")
    store.edit("demo", {"extra.json": "invalid"})
    with pytest.raises(github.GitHubError) as rejected:
        repo_sync.send(store, "demo")
    assert rejected.value.status == 400
    assert not github.require(store, "demo").pending_operation
    assert not server.pulls
    store.edit("demo", {"extra.json": "{}"})
    assert repo_sync.send(store, "demo")["url"]
