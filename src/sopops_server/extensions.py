"""Optional hosted-product extensions.

The server has no dependency on a hosted product.  Installations that need one
can expose a ``sopops.extensions`` entry point whose callable receives the
FastAPI app, Store and Jobs objects at startup.  The callable can attach routes
and listeners (session events, and model calls through `sopops_server.ai.tracing`)
without the public server importing a private package by name.

An extension turns on a feature the UI shows only where it's available (Fine tune, on hosted sopops) with
`add_feature(app, "fine_tune")`; `GET /v1/features` lists them.

The Hatchet worker (`sopops worker`), where checks run when Hatchet is on, loads them too (`load_worker`): there the
app is a bare FastAPI that serves nothing, with `app.state.sopops_worker` set, so an extension can skip its routes and
keep what matters in a worker, like its model-call listeners.

Gates and notices let an extension hold a workspace's sessions unchecked and tell its members why:
`add_analysis_gate(fn)` is asked about each session where analysis checks the pause, before any model call, and a reason
it returns holds the session like a pause does (`received`, with that reason); `release_held` queues them again.
`add_notices(fn)` adds banners and dialogs the UI shows across the workspace (`GET /v1/workspaces/{ws}/notices`).
Both run in the server and the worker, so register them wherever the extension loads.
"""

from __future__ import annotations

import logging
import weakref
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Callable, Literal

from fastapi import FastAPI

if TYPE_CHECKING:  # the pipeline asks the gates, and jobs imports the pipeline
    from .jobs import Jobs
    from .store import Store

log = logging.getLogger("sopops.extensions")
ENTRY_POINTS = "sopops.extensions"
Register = Callable[["FastAPI", "Store", "Jobs"], None]


@dataclass
class Notice:
    """Something a workspace's members should see: a banner (`info`, `warning`), or a dialog (`blocking`) that, once
    closed, stays as a warning banner."""

    id: str  # stable: the UI remembers dismissals by it
    level: Literal["info", "warning", "blocking"]
    title: str
    body: str
    action_label: str | None = None
    action_url: str | None = None  # opened in a new tab


Gate = Callable[[str, str], "str | None"]  # (workspace, session) -> why it's held, or None
Notices = Callable[[str], "list[Notice]"]  # workspace -> its notices

_gates: list[Gate] = []
_notices: list[Notices] = []
_jobs: weakref.WeakKeyDictionary[Store, Jobs] = weakref.WeakKeyDictionary()  # the app's, for release_held


def add_analysis_gate(fn: Gate) -> None:
    """Hold sessions unchecked: `fn(workspace_id, session_id)` returns the reason a session is held, or None."""
    _gates.append(fn)


def add_notices(fn: Notices) -> None:
    """Show notices: `fn(workspace_id)` returns the workspace's."""
    _notices.append(fn)


def held(workspace_id: str, session_id: str) -> str | None:
    """The first gate's reason to hold the session, or None. A gate that raises lets it through: a broken extension
    mustn't stop a deployment's checks."""
    for gate in list(_gates):
        try:
            if reason := gate(workspace_id, session_id):
                return reason
        except Exception:
            log.exception("analysis gate %r failed for %s/%s; letting it through", gate, workspace_id, session_id)
    return None


def notices(workspace_id: str) -> list[Notice]:
    """Every provider's notices for the workspace; one that raises is skipped."""
    out: list[Notice] = []
    for fn in list(_notices):
        try:
            out.extend(fn(workspace_id))
        except Exception:
            log.exception("notice provider %r failed for %s", fn, workspace_id)
    return out


def release_held(store: Store, workspace_id: str, reason: str, jobs: Jobs | None = None) -> int:
    """Queue every session in the workspace held with exactly this reason, as resuming a pause does. Returns how many.
    The gate should let them through by now, or they're held again. `jobs`: default, the app's (or a new one)."""
    from .jobs import Jobs

    jobs = jobs or _jobs.get(store) or Jobs(store)
    refs = store.analysis.held_for(workspace_id, reason)
    for ref in refs:
        jobs.process_session(ref)
    return len(refs)


def clear() -> None:
    """Forget every gate and notice provider (tests)."""
    _gates.clear()
    _notices.clear()


def load(app: FastAPI, store: Store, jobs: Jobs) -> None:
    """Load installed optional extensions.

    An extension failing to load must not stop a self-hosted deployment from
    starting.  Hosted deployments should alert on the logged exception.
    """
    app.state.sopops_worker = getattr(app.state, "sopops_worker", False)
    app.state.sopops_features = getattr(app.state, "sopops_features", set())
    _jobs[store] = jobs
    for point in entry_points(group=ENTRY_POINTS):
        try:
            register: Register = point.load()
            register(app, store, jobs)
        except Exception:
            log.exception("couldn't load extension %s", point.name)


def add_feature(app: FastAPI, name: str) -> None:
    """Turn on a feature the open-source server leaves off, e.g. `fine_tune`."""
    app.state.sopops_features.add(name)


def load_worker(store: Store) -> None:
    """Load the extensions in the Hatchet worker, which has no app of its own."""
    from .jobs import Jobs

    app = FastAPI()
    app.state.sopops_worker = True
    load(app, store, Jobs(store, use_hatchet=True))
