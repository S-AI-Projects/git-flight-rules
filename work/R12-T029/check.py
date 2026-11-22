#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Shared harness: isolated Git environment, the course fixture, and a tiny
# expectation recorder that saves inputs, expected-vs-actual results and tool
# versions next to this script (results.json).  Standard library only.
# ---------------------------------------------------------------------------
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.name
FIXED_DATE = "2026-01-01T00:00:00+0000"
AUTHOR_NAME = "Course Student"
AUTHOR_EMAIL = "student@example.invalid"

FIXTURE_STEPS = [
    "git init -b main",
    "git config user.name 'Course Student'",
    "git config user.email student@example.invalid",
    "printf 'alpha\\n' > notes.txt && git add notes.txt && git commit -m A",
    "printf 'beta\\n' >> notes.txt && git commit -am B",
    "git branch topic            # topic -> B",
    "printf 'one\\n' > todo.txt && git add todo.txt && git commit -m C",
]


def isolated_env(home):
    """Environment that never reads or writes the user's own Git config."""
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    gcfg = home / "gitconfig"
    if not gcfg.exists():
        gcfg.write_text("[init]\n\tdefaultBranch = main\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / "xdg"),
        GIT_CONFIG_GLOBAL=str(gcfg),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME=AUTHOR_NAME,
        GIT_AUTHOR_EMAIL=AUTHOR_EMAIL,
        GIT_COMMITTER_NAME=AUTHOR_NAME,
        GIT_COMMITTER_EMAIL=AUTHOR_EMAIL,
        GIT_AUTHOR_DATE=FIXED_DATE,
        GIT_COMMITTER_DATE=FIXED_DATE,
        GIT_EDITOR="true",
        GIT_PAGER="cat",
        GIT_TERMINAL_PROMPT="0",
        LC_ALL="C",
        LANG="C",
    )
    return env


class Git:
    def __init__(self, cwd, env):
        self.cwd = Path(cwd)
        self.env = env

    def run(self, *args, check=True, input=None, env=None):
        """Run git; with check=True a non-zero exit raises with stderr shown."""
        proc = subprocess.run(
            ["git", *args],
            cwd=self.cwd,
            env=env or self.env,
            input=input,
            text=True,
            capture_output=True,
        )
        if check and proc.returncode != 0:
            raise AssertionError(
                "git %s failed (exit %d)\nstdout: %s\nstderr: %s"
                % (" ".join(args), proc.returncode, proc.stdout, proc.stderr)
            )
        return proc

    def out(self, *args, **kw):
        return self.run(*args, **kw).stdout.rstrip("\n")

    def oid(self, rev):
        return self.out("rev-parse", "--verify", rev)

    def refs(self):
        text = self.out("for-each-ref", "--format=%(refname) %(objectname)")
        return dict(line.split(" ", 1) for line in text.splitlines() if line)

    def index(self):
        return self.out("ls-files", "-s")

    def status(self):
        return self.out("status", "--short", "--untracked-files=all")


def make_fixture(path, env):
    """Course fixture: main = A-B-C, topic = B. Returns (Git, {A,B,C} oids)."""
    path = Path(path)
    path.mkdir(parents=True)
    g = Git(path, env)
    g.run("init", "-q", "-b", "main")
    g.run("config", "user.name", AUTHOR_NAME)
    g.run("config", "user.email", AUTHOR_EMAIL)
    (path / "notes.txt").write_text("alpha\n")
    g.run("add", "notes.txt")
    g.run("commit", "-q", "-m", "A")
    a = g.oid("HEAD")
    with open(path / "notes.txt", "a") as fh:
        fh.write("beta\n")
    g.run("commit", "-q", "-am", "B")
    b = g.oid("HEAD")
    g.run("branch", "topic")
    (path / "todo.txt").write_text("one\n")
    g.run("add", "todo.txt")
    g.run("commit", "-q", "-m", "C")
    c = g.oid("HEAD")
    return g, {"A": a, "B": b, "C": c}


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class Recorder:
    def __init__(self):
        self.facts = []
        self.inputs = {"fixture": FIXTURE_STEPS}

    def expect(self, name, actual, expected):
        ok = actual == expected
        self.facts.append(
            {"fact": name, "expected": expected, "actual": actual, "ok": ok}
        )
        mark = "PASS" if ok else "FAIL"
        print("[%s] %s" % (mark, name))
        if not ok:
            raise AssertionError(
                "%s\n  expected: %r\n  actual:   %r" % (name, expected, actual)
            )

    def truthy(self, name, value):
        self.expect(name, bool(value), True)


def versions():
    git = subprocess.run(["git", "--version"], capture_output=True, text=True)
    return {
        "git": git.stdout.strip(),
        "python": platform.python_version(),
        "platform": platform.platform(),
    }


def main(scenario, description, save=True):
    """Run scenario(rec, tmp) in a fresh temp dir, save results.json, set exit code."""
    rec = Recorder()
    status, error = "pass", None
    print("%s: %s" % (TASK, description))
    try:
        with tempfile.TemporaryDirectory(prefix=TASK + "-") as tmp:
            scenario(rec, Path(tmp))
    except Exception as exc:  # any failure -> non-zero exit
        status, error = "fail", "%s: %s" % (type(exc).__name__, exc)
        print("ERROR:", error, file=sys.stderr)
    if len([f for f in rec.facts if f["ok"]]) < 3 and status == "pass":
        status, error = "fail", "fewer than three state facts were asserted"
    if save:
        result = {
            "task": TASK,
            "description": description,
            "status": status,
            "error": error,
            "tool_versions": versions(),
            "inputs": rec.inputs,
            "checks": rec.facts,
        }
        (HERE / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print("%s: %s (%d facts checked)" % (TASK, status.upper(), len(rec.facts)))
    sys.exit(0 if status == "pass" else 1)


# ---------------------------------------------------------------------------
# Task-specific scenario
# ---------------------------------------------------------------------------
DESCRIPTION = "Prerequisites for 'I need to combine commits' (reset --soft main / commit -am / rebase -i main)"

import hashlib

# Local sequence editor for the rebase -i variant: squash every commit after the first.
SQUASH_REST = r'''
import sys
path = sys.argv[1]
out, first = [], True
for line in open(path):
    if line.startswith("pick "):
        if not first:
            line = "squash " + line[5:]
        first = False
    out.append(line)
open(path, "w").writelines(out)
'''


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scenario(rec, tmp):
    env = isolated_env(tmp / "home")
    global_cfg = Path(env["GIT_CONFIG_GLOBAL"])
    global_before = digest(global_cfg)
    g, oids = make_fixture(tmp / "demo", env)
    rec.inputs["commands"] = [
        "git switch topic                       # P1: be on the feature branch",
        "two commits on topic: feature.txt f1, then f2",
        "git merge-base --is-ancestor main topic || git rebase main   # P2",
        "git status --porcelain --untracked-files=no   # P3: must be empty",
        "git config --local user.name/user.email       # P4: identity",
        "git reset --soft main && git commit -am 'New awesome feature'",
        "git config --local core.editor / sequence.editor   # P5 for rebase -i",
        "git rebase -i main",
    ]

    # P1: on the feature branch, with two commits to combine.
    g.run("switch", "-q", "topic")
    commit_file = lambda text, msg: (write(g.cwd / "feature.txt", text),
                                     g.run("add", "feature.txt"), g.run("commit", "-q", "-m", msg))
    commit_file("f1\n", "feature part 1")
    commit_file("f1\nf2\n", "feature part 2")
    rec.expect("P1: current branch is the feature branch, not main",
               g.out("symbolic-ref", "--short", "HEAD"), "topic")

    # P2: main must be an ancestor of the branch ("main is up to date and you branched from it").
    is_anc = g.run("merge-base", "--is-ancestor", "main", "topic", check=False).returncode == 0
    would_stage = g.out("diff", "--name-status", "main", "topic").splitlines()
    rec.expect("P2 violated at first: topic forked at B, main is at C",
               (is_anc, g.out("merge-base", "main", "topic")), (False, oids["B"]))
    rec.expect("why it matters: reset --soft main would also stage deleting main's todo.txt",
               "D\ttodo.txt" in would_stage, True)
    g.run("rebase", "-q", "main")
    rec.expect("P2 satisfied after 'git rebase main'",
               g.run("merge-base", "--is-ancestor", "main", "topic", check=False).returncode, 0)

    # P3: nothing uncommitted in tracked files; untracked files are NOT picked up by -a.
    write(g.cwd / "scratch.txt", "not part of the feature\n")
    rec.expect("P3: no uncommitted changes to tracked files",
               g.out("status", "--porcelain", "--untracked-files=no"), "")

    # P4: identity comes from local config; global config untouched.
    rec.expect("P4: identity is set in the repository's local config",
               (g.out("config", "--local", "user.name"), g.out("config", "--local", "user.email")),
               ("Course Student", "student@example.invalid"))

    tree_before = g.oid("topic^{tree}")
    copy_tip = g.oid("topic")
    g.run("branch", "topic-rebase", copy_tip)

    # Method 1: reset --soft + commit -am.
    g.run("reset", "--soft", "main")
    rec.expect("after reset --soft main: both commits' changes are staged, HEAD = main",
               (g.oid("HEAD"), g.out("diff", "--cached", "--name-only")), (oids["C"], "feature.txt"))
    g.run("commit", "-q", "-am", "New awesome feature")
    rec.expect("method 1: exactly one new commit on top of main",
               (g.out("rev-list", "--count", "main..topic"), g.oid("topic^")), ("1", oids["C"]))
    rec.expect("method 1: combined commit has the same tree as the two original commits",
               g.oid("topic^{tree}"), tree_before)
    rec.expect("method 1: untracked scratch.txt was not committed and is still untracked",
               (g.run("cat-file", "-e", "topic:scratch.txt", check=False).returncode != 0, g.status()),
               (True, "?? scratch.txt"))

    # Method 2: rebase -i main, needing an editor (P5) - configured locally.
    editor = tmp / "squash_rest.py"
    editor.write_text(SQUASH_REST)
    g.run("switch", "-q", "topic-rebase")
    g.run("config", "--local", "core.editor", "true")
    g.run("config", "--local", "sequence.editor", '"%s" "%s"' % (sys.executable, editor))
    env_no_editor = {k: v for k, v in env.items() if k != "GIT_EDITOR"}
    g.run("rebase", "-i", "main", env=env_no_editor)
    rec.expect("method 2: rebase -i main also leaves one commit on top of main with the same tree",
               (g.out("rev-list", "--count", "main..topic-rebase"), g.oid("topic-rebase^"),
                g.oid("topic-rebase^{tree}")), ("1", oids["C"], tree_before))
    rec.expect("P5: editors were configured in local config only",
               (g.out("config", "--local", "core.editor"),
                g.run("config", "--global", "core.editor", check=False).returncode != 0),
               ("true", True))
    rec.expect("global Git configuration file is byte-for-byte unchanged",
               digest(global_cfg), global_before)
    rec.expect("main itself was never moved", g.oid("main"), oids["C"])


if __name__ == "__main__":
    main(scenario, DESCRIPTION)
