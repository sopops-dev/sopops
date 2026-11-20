"""Loopback GitHub API backed by real Git objects and atomic ref updates."""

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import tempfile
import threading
from urllib.parse import parse_qs, unquote, urlparse


class GitHubServer:
    def __init__(self, repo, repository="fixture/private", token="test-token"):
        self.repo, self.repository, self.token = Path(repo), repository, token
        self.pulls, self.requests = [], []
        self.fail_pr = 0
        self.before_cas = None
        self.lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.respond()

            def do_POST(self):
                self.respond()

            def respond(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                body = json.loads(body) if body else {}
                with outer.lock:
                    outer.requests.append((self.command, self.path, body))
                    if self.headers.get("Authorization") != f"Bearer {outer.token}":
                        code, value = 401, {}
                    else:
                        try:
                            code, value = outer.route(self.command, self.path, body)
                        except Exception as error:
                            code, value = 500, {"message": str(error)}
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(value).encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def git(self, *args, data=None, env=None):
        import os

        return (
            subprocess.check_output(
                ["git", "-C", str(self.repo), *args],
                input=data,
                env={**os.environ, **(env or {})},
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )

    def pr(self, p):
        def side(branch):
            return {
                "ref": branch,
                "sha": self.git("rev-parse", branch),
                "repo": {"full_name": self.repository},
            }

        return {
            "number": p["number"],
            "html_url": f"https://github.com/{self.repository}/pull/{p['number']}",
            "body": p.get("body", ""),
            "state": p["state"],
            "merged": p.get("merged", False),
            "head": side(p["head"]),
            "base": side(p["base"]),
        }

    def route(self, method, url, body):
        parsed = urlparse(url)
        path, query = unquote(parsed.path), parse_qs(parsed.query)
        prefix = f"/repos/{self.repository}"
        if path == "/graphql":
            change = body["variables"]["input"]["refUpdates"][0]
            if self.before_cas:
                self.before_cas(change)
            try:
                self.git(
                    "update-ref",
                    change["name"],
                    change["afterOid"],
                    change["beforeOid"],
                )
            except subprocess.CalledProcessError:
                return 200, {"errors": [{"message": "expected OID changed"}]}
            return 200, {"data": {"updateRefs": {"clientMutationId": None}}}
        if path == prefix:
            return 200, {"node_id": "test-repository", "default_branch": "main"}
        rel = path.removeprefix(prefix + "/")
        if rel.startswith("branches/"):
            return 200, {
                "commit": {"sha": self.git("rev-parse", rel.removeprefix("branches/"))}
            }
        if rel.startswith("contents/"):
            try:
                content = self.git(
                    "show", query["ref"][0] + ":" + rel.removeprefix("contents/")
                )
                return 200, {
                    "type": "file",
                    "content": base64.b64encode(content.encode()).decode(),
                }
            except subprocess.CalledProcessError:
                return 404, {}
        if rel.startswith("git/ref/"):
            try:
                return 200, {
                    "object": {
                        "sha": self.git(
                            "rev-parse", "refs/" + rel.removeprefix("git/ref/")
                        )
                    }
                }
            except subprocess.CalledProcessError:
                return 404, {}
        if rel.startswith("git/commits/"):
            sha = rel.removeprefix("git/commits/")
            parents = self.git("show", "-s", "--format=%P", sha).split()
            return 200, {
                "sha": sha,
                "tree": {"sha": self.git("rev-parse", sha + "^{tree}")},
                "parents": [{"sha": p} for p in parents],
                "message": self.git("show", "-s", "--format=%B", sha),
            }
        if method == "POST" and rel == "git/blobs":
            content = (
                base64.b64decode(body["content"])
                if body["encoding"] == "base64"
                else body["content"].encode()
            )
            return 201, {"sha": self.git("hash-object", "-w", "--stdin", data=content)}
        if method == "POST" and rel == "git/trees":
            with tempfile.TemporaryDirectory() as temp:
                env = {"GIT_INDEX_FILE": str(Path(temp) / "index")}
                self.git("read-tree", body["base_tree"], env=env)
                for entry in body["tree"]:
                    if entry.get("sha") is None:
                        self.git(
                            "update-index",
                            "--force-remove",
                            "--",
                            entry["path"],
                            env=env,
                        )
                    else:
                        self.git(
                            "update-index",
                            "--add",
                            "--cacheinfo",
                            entry["mode"],
                            entry["sha"],
                            entry["path"],
                            env=env,
                        )
                return 201, {"sha": self.git("write-tree", env=env)}
        if method == "POST" and rel == "git/commits":
            args = ["commit-tree", body["tree"]]
            for parent in body["parents"]:
                args.extend(["-p", parent])
            return 201, {"sha": self.git(*args, data=body["message"].encode())}
        if rel == "pulls":
            if method == "POST":
                if self.fail_pr:
                    self.fail_pr -= 1
                    return 503, {}
                p = {**body, "number": len(self.pulls) + 1, "state": "open"}
                self.pulls.append(p)
                return 201, self.pr(p)
            head = query.get("head", [""])[0].split(":", 1)[-1]
            base = query.get("base", [""])[0]
            return 200, [
                self.pr(p)
                for p in reversed(self.pulls)
                if p["head"] == head and p["base"] == base
            ]
        if rel.startswith("pulls/"):
            return 200, self.pr(self.pulls[int(rel.split("/")[-1]) - 1])
        return 404, {"message": f"unhandled test route {method} {path}"}
