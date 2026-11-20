# Contributor instructions

Read [CONTRIBUTING.md](CONTRIBUTING.md) and the relevant guide before editing. Keep implementation plans and roadmaps in the conversation, not this public repository.

## GitHub integration

- `raad_backend.py` supplies GitHub.com content through the in-process Rust-backed Python SDK. Keep Git, validation, cache and proposal provider logic in raad; keep SOP compilation and application policy here.
- sopops owns encrypted PATs, GitHub App tokens, OAuth, webhook verification, drafts, conflicts and explicit publication. Never log credentials or include them in cache identities.
- Use one private persistent cache per database/workspace/connection. Docker uses `/data/raad`; the host override is `SOPOPS_RAAD_CACHE_DIR`. Exclude `build/`. A mount isn't a Git download isolation boundary.
- Inspect raw candidates for onboarding and repair; don't activate invalid files or advance a sync base after failure. Read bulk validated snapshots for ordinary syncs and retain merge bases until their replacement is committed.
- Apply drafts, conflicts and the new base atomically after comparing connection generation and draft/conflict revisions. Retry a concurrent draft edit once. Reconnection invalidates older operations.
- Send from the exact reconciled source SHA. Persist the operation ID and exact request before a write, recover an uncertain outcome first, and use the stored machine head for atomic proposal updates. Never overwrite human changes or close an open PR on a no-op.
- Keep compatibility for an existing open legacy `sopops/sync` PR, explicit legacy mode, nondefault API endpoints and explicitly unsupported trees. No fallback after auth, validation, limits, network failures or conflicts.
- raad is pinned to an exact companion Git commit. Don't publish or bump either repository to a minor release as part of integration work. Default to patch increments in `0.1.x` for raad.

Run the backend suite on SQLite and PostgreSQL, including `tests/test_raad_github.py` with the real native SDK. Use a real SOP binary; do not count a skipped suite as success. Test without customer data, model keys or real GitHub writes. Update human/API docs with behavior changes and verify the OpenAPI schema stays stable when API shapes are unchanged.

See [GitHub API behavior](docs/api/github.md), [configuration](docs/configuration.md), and [verification](CONTRIBUTING.md#github-sync-checks).
