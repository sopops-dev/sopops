"""GitHub content operations through raad; credentials and SOP policy stay in sopops."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import TYPE_CHECKING

import raad

from . import github
from .github_client import GitHubError, api_url

if TYPE_CHECKING:
    from .orm import RepoConnection
    from .store import Store


def _repository(store: Store, conn: RepoConnection) -> raad.Repository:
    # A cache belongs to one database/workspace/connection, never to a token or a
    # repository shared across tenants. Host cache permissions protect private data.
    identity = hashlib.sha256(
        f"{store.engine.url.render_as_string(hide_password=True)}:{conn.workspace}:{conn.connection_id}".encode()
    ).hexdigest()
    root = Path(
        os.environ.get("SOPOPS_RAAD_CACHE_DIR", Path.home() / ".cache/sopops/raad")
    )
    cache = root / identity
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache.chmod(0o700)

    def token() -> str:
        current = github.require(store, conn.workspace)
        if current.generation != conn.generation or current.broken:
            raise GitHubError("the repository connection changed; retry", 409)
        return github.credentials(current, store)

    return raad.Repository(
        f"{conn.owner}/{conn.repo}",
        root=conn.path,
        branch=conn.base_branch,
        cache_dir=cache,
        token_provider=token,
        excluded_paths=["build"],
        limits={"response_bytes": 64 * 1024 * 1024},
        allow_proposals=True,
    )


def translate(error: raad.RaadError) -> GitHubError:
    code = error.code
    status = (
        409
        if code in ("conflict", "stale_base")
        else 429
        if code == "rate_limit"
        else 400
        if code
        in (
            "validation",
            "invalid_path",
            "limit",
            "permission_denied",
            "not_found",
            "configuration",
            "unsupported_feature",
        )
        else 502
    )
    translated = GitHubError(str(error), status)
    translated.raad_code = code
    translated.write_rejected = error.write_rejected
    return translated


class Backend:
    def __init__(self, store: Store, conn: RepoConnection):
        self.conn = conn
        self.repo = _repository(store, conn)
        self.candidate = self.repo.inspect_candidate()

    @staticmethod
    def text(files: dict[str, bytes], *, raw: bool = False) -> dict[str, str]:
        try:
            result = {p: data.decode("utf-8") for p, data in files.items()}
        except UnicodeDecodeError:
            raise GitHubError(
                "the connected SOP folder must contain UTF-8 text", 400
            ) from None
        return result if raw else github._as_sop_yaml(result)

    @property
    def sha(self) -> str:
        return self.candidate.commit_sha

    def files(self, *, raw: bool = False) -> dict[str, str]:
        return self.text(self.candidate.files, raw=raw)

    def validated(self, revision: str | None = None) -> tuple[dict[str, str], str]:
        sha = revision or self.sha
        try:
            if revision is not None:
                try:
                    snapshot = self.repo.snapshot(sha)
                except raad.CacheMissError:
                    self.repo.sync(sha, pin=True)
                    snapshot = self.repo.snapshot(sha)
            else:
                self.repo.sync(sha, pin=True)
                snapshot = self.repo.snapshot(sha)
        except raad.RaadError as error:
            raise translate(error) from None
        return self.text(snapshot.files), snapshot.commit_sha

    def propose(
        self,
        files: dict[str, str | None],
        *,
        title: str,
        body: str,
        branch: str,
        operation_id: str,
        expected_head: str | None = None,
        expected_base: str | None = None,
    ) -> raad.ProposalOutcome:
        changes = [
            raad.Delete(p) if content is None else raad.Put(p, content)
            for p, content in sorted(files.items())
        ]
        try:
            return self.repo.upsert_proposal(
                changes,
                expected_base=expected_base or self.sha,
                title=title,
                body=body,
                branch=branch,
                expected_head=expected_head,
                operation_id=operation_id,
            )
        except raad.RaadError as error:
            raise translate(error) from None


def configured() -> bool:
    mode = os.environ.get("SOPOPS_GITHUB_BACKEND", "auto")
    if mode not in ("auto", "legacy"):
        raise GitHubError("SOPOPS_GITHUB_BACKEND must be auto or legacy", 400)
    return mode != "legacy" and api_url() == "https://api.github.com"


def backend(store: Store, conn: RepoConnection) -> Backend | None:
    if not configured():
        return None
    # Preserve the host's credential setup errors (notably missing encryption
    # keys) before the SDK deliberately sanitizes callback failures.
    github.credentials(conn, store)
    try:
        return Backend(store, conn)
    except raad.UnsupportedFeatureError:
        # Only an explicitly unsupported tree layout uses the compatibility path.
        return None
    except raad.RaadError as error:
        raise translate(error) from None
