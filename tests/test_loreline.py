import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.request
from http.server import HTTPServer

from loreline import cli, gitutil
from loreline.chat import import_chat
from loreline.explain import Explainer
from loreline.github import GitHub, linked_issues
from loreline.mcp import handle
from loreline.repo import Repo, extract_pr
from loreline.server import make_handler
from loreline.watch import MARKER, install_hooks, uninstall_hooks

ENV = {**os.environ, "GIT_AUTHOR_NAME": "Ada", "GIT_AUTHOR_EMAIL": "ada@example.com",
       "GIT_COMMITTER_NAME": "Ada", "GIT_COMMITTER_EMAIL": "ada@example.com",
       "LORELINE_LLM_PROVIDER": "none", "GITHUB_TOKEN": "", "GH_TOKEN": ""}


def sh(cwd, *args, env=None):
    return subprocess.run(["git", *args], cwd=cwd, env=env or ENV, check=True, capture_output=True, text=True).stdout


def write(root, path, text):
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as fh:
        fh.write(text)


class RepoTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.update({"LORELINE_LLM_PROVIDER": "none", "XDG_CONFIG_HOME": tempfile.mkdtemp()})
        cls.root = tempfile.mkdtemp()
        r = cls.root
        sh(r, "init", "-q", "-b", "main")
        write(r, "app/upload.py", "def upload(f):\n    return send(f)\n")
        sh(r, "add", ".")
        sh(r, "commit", "-q", "-m", "Add uploader")
        sh(r, "checkout", "-q", "-b", "retry")
        write(r, "app/upload.py", "def upload(f):\n    for _ in range(3):  # S3 drops ~1% of PUTs\n        if send(f):\n            return True\n")
        sh(r, "commit", "-q", "-am", "Retry uploads three times\n\nS3 occasionally returns 503 under load; see incident notes.")
        sh(r, "checkout", "-q", "main")
        sh(r, "merge", "-q", "--no-ff", "retry", "-m", "Merge pull request #42 from ada/retry\n\nRetry flaky uploads")
        write(r, "README.md", "# demo\n")
        sh(r, "add", ".")
        sh(r, "commit", "-q", "-m", "Add readme (#43)")
        cls.repo = Repo(r, offline=True, quiet=True)
        cls.repo.index()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)


class TestParsing(unittest.TestCase):
    def test_extract_pr(self):
        self.assertEqual(extract_pr("Merge pull request #12 from a/b"), 12)
        self.assertEqual(extract_pr("Fix bug (#981)"), 981)
        self.assertEqual(extract_pr("Plain commit"), None)
        self.assertEqual(extract_pr("x", "See merge request group/proj!77"), 77)

    def test_parse_target(self):
        self.assertEqual(cli.parse_target("a/b.py:12"), ("a/b.py", 12, None))
        self.assertEqual(cli.parse_target("a/b.py:10-20"), ("a/b.py", 10, None))
        self.assertEqual(cli.parse_target("a/b.py:main"), ("a/b.py", None, "main"))
        self.assertEqual(cli.parse_target("a/b.py"), ("a/b.py", None, None))

    def test_linked_issues(self):
        self.assertEqual(linked_issues("Fixes #3, closes #7 and refs #3"), [3, 7])

    def test_github_slug(self):
        self.assertEqual(gitutil.github_slug("git@github.com:o/r.git"), ("o", "r"))
        self.assertEqual(gitutil.github_slug("https://github.com/o/r"), ("o", "r"))
        self.assertIsNone(gitutil.github_slug("https://gitlab.com/o/r"))


class TestIndexAndWhy(RepoTestCase):
    def test_index_counts(self):
        st = self.repo.store.stats()
        self.assertGreaterEqual(st["commits"], 4)
        row = self.repo.store.db.execute("SELECT pr FROM commits WHERE subject='Add readme (#43)'").fetchone()
        self.assertEqual(row["pr"], 43)

    def test_incremental_index(self):
        write(self.root, "NOTES.md", "n\n")
        sh(self.root, "add", ".")
        sh(self.root, "commit", "-q", "-m", "notes")
        res = self.repo.index()
        self.assertEqual(res["new_commits"], 1)
        self.assertEqual(self.repo.index()["new_commits"], 0)

    def test_why_line_finds_commit_and_pr_via_merge(self):
        ev = Explainer(self.repo).why("app/upload.py", 2)
        self.assertIn("range(3)", ev["target"]["text"])
        origin = ev["origin"]
        self.assertEqual(origin["subject"], "Retry uploads three times")
        self.assertEqual(origin["pr"]["number"], 42)  # discovered offline from the merge commit
        self.assertIn("503", Explainer(self.repo).evidence_text(ev))

    def test_why_symbol_and_file(self):
        ex = Explainer(self.repo)
        ev = ex.why("app/upload.py", symbol="upload")
        self.assertEqual(ev["target"]["line"], 1)
        self.assertTrue(ev["commits"])
        ev = ex.why("app/upload.py")
        self.assertEqual(ev["file"]["created"]["subject"], "Add uploader")

    def test_emails_redacted_from_llm_evidence(self):
        ev = Explainer(self.repo).why("app/upload.py", 2)
        ev["commits"][0]["body"] += " contact ada@example.com"
        self.assertNotIn("ada@example.com", Explainer(self.repo).evidence_text(ev))

    def test_ask_search(self):
        res = Explainer(self.repo).ask("why do we retry uploads?")
        self.assertTrue(any("Retry" in s["title"] for s in res["sources"]))
        self.assertIsNone(res["answer"])

    def test_map(self):
        m = Explainer(self.repo).build_map(use_llm=False)
        paths = {e["path"] for e in m["files"]}
        self.assertIn("app/upload.py", paths)

    def test_cli_why_json(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(["-C", self.root, "--offline", "why", "app/upload.py:2", "--json", "--no-llm"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["evidence"]["origin"]["pr"]["number"], 42)


class TestChat(RepoTestCase):
    def test_import_text_links(self):
        sha = self.repo.store.db.execute("SELECT sha FROM commits WHERE subject LIKE 'Retry%'").fetchone()[0]
        path = os.path.join(tempfile.mkdtemp(), "chat.txt")
        with open(path, "w") as fh:
            fh.write(f"2024-01-01 10:00 bob: S3 is flaky, retry in {sha[:8]}\n"
                     "2024-01-01 10:01 ada: agreed, PR #42 has it, touches app/upload.py\n")
        res = import_chat(self.repo, path)
        self.assertEqual(res, {"messages": 2, "linked": 2})
        ev = Explainer(self.repo).why("app/upload.py", 2)
        self.assertTrue(ev["origin"]["chat"])
        self.assertTrue(ev["origin"]["pr"]["chat"])
        self.assertTrue(ev["file"]["chat"])

    def test_import_slack(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "eng"))
        with open(os.path.join(d, "eng", "2024-01-01.json"), "w") as fh:
            json.dump([{"user": "U1", "text": "merging #42 now", "ts": "1704100000.0001"}], fh)
        with open(os.path.join(d, "users.json"), "w") as fh:
            json.dump([{"id": "U1", "real_name": "Bob"}], fh)
        self.assertEqual(import_chat(self.repo, d)["linked"], 1)


class TestGitHubEnrichment(RepoTestCase):
    def test_fetch_pr_with_fake_api(self):
        repo = Repo(self.root, quiet=True)
        gh = GitHub("o", "r", "t")
        responses = {
            "/pulls/42": {"number": 42, "title": "Retry flaky uploads", "body": "Fixes #7. S3 503s.",
                          "user": {"login": "ada"}, "html_url": "https://github.com/o/r/pull/42", "state": "closed"},
            "/issues/42/comments?per_page=100": [{"id": 1, "user": {"login": "bob"}, "body": "Why 3?", "created_at": "x"}],
            "/pulls/42/comments?per_page=100": [],
            "/pulls/42/reviews?per_page=100": [{"id": 2, "user": {"login": "cy"}, "body": "3 matches SDK default",
                                                "state": "APPROVED"}],
            "/issues/7": {"number": 7, "title": "Uploads fail randomly", "body": "503 from S3", "user": {"login": "dee"}},
        }
        gh._get = lambda path: responses.get(path)
        repo.__dict__["github"] = gh
        self.assertTrue(repo.fetch_pr(42))
        repo.store.commit()
        ev = Explainer(repo).why("app/upload.py", 2)
        pr = ev["origin"]["pr"]
        self.assertEqual(pr["title"], "Retry flaky uploads")
        self.assertEqual(pr["issues"][0]["title"], "Uploads fail randomly")
        self.assertEqual({m["author"] for m in pr["discussion"]}, {"bob", "cy"})


class TestHooks(RepoTestCase):
    def test_install_uninstall(self):
        install_hooks(self.repo)
        hook = os.path.join(self.repo.git_dir, "hooks", "post-commit")
        self.assertIn(MARKER, open(hook).read())
        install_hooks(self.repo)  # idempotent
        self.assertEqual(open(hook).read().count(MARKER), 1)
        uninstall_hooks(self.repo)
        self.assertFalse(os.path.exists(hook))


class TestMCPAndServer(RepoTestCase):
    def test_mcp(self):
        ex = Explainer(self.repo)
        init = handle(self.repo, ex, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "loreline")
        tools = handle(self.repo, ex, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(len(tools["result"]["tools"]), 2)
        res = handle(self.repo, ex, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                     "params": {"name": "loreline_why", "arguments": {"path": "app/upload.py", "line": 2}}})
        self.assertIn("Retry uploads three times", res["result"]["content"][0]["text"])
        self.assertIsNone(handle(self.repo, ex, {"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_http_api(self):
        httpd = HTTPServer(("127.0.0.1", 0), make_handler(self.repo))
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        base = f"http://127.0.0.1:{httpd.server_port}"
        try:
            files = json.load(urllib.request.urlopen(base + "/api/files"))
            self.assertIn("app/upload.py", files)
            why = json.load(urllib.request.urlopen(base + "/api/why?path=app/upload.py&line=2"))
            self.assertEqual(why["evidence"]["origin"]["pr"]["number"], 42)
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(base + "/api/file?path=../../etc/passwd")
            self.assertEqual(cm.exception.code, 404)
            html = urllib.request.urlopen(base + "/").read().decode()
            self.assertIn("loreline", html)
        finally:
            httpd.shutdown()


if __name__ == "__main__":
    unittest.main()
