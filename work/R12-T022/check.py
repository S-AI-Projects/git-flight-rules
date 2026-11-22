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
DESCRIPTION = "State transitions for 'I want to start a local repository' (git init)"


def scenario(rec, tmp):
    env = isolated_env(tmp / "home")  # its gitconfig sets init.defaultBranch=main
    rec.inputs["config"] = "temporary GIT_CONFIG_GLOBAL with init.defaultBranch = main"
    rec.inputs["commands"] = [
        "mkdir my-folder && printf 'alpha\\n' > my-folder/notes.txt",
        "(my-folder) $ git init",
        "fixture repository: git init  # re-run inside an existing repository",
    ]

    # --- Transition 1: plain folder -> new repository -----------------------
    folder = tmp / "my-folder"
    write(folder / "notes.txt", "alpha\n")
    g = Git(folder, env)
    # GIT_CEILING_DIRECTORIES stops Git from finding a repository above tmp/.
    outside = g.run("rev-parse", "--git-dir", check=False,
                    env=dict(env, GIT_CEILING_DIRECTORIES=str(tmp)))
    rec.expect("before: my-folder is not a Git repository",
               outside.returncode != 0, True)

    g.run("init", "-q")
    rec.expect("after: .git directory exists", (folder / ".git").is_dir(), True)
    rec.expect("after: HEAD is a symbolic ref to refs/heads/main",
               g.out("symbolic-ref", "HEAD"), "refs/heads/main")
    unborn = g.run("rev-parse", "--verify", "-q", "HEAD", check=False)
    rec.expect("after: HEAD is unborn (rev-parse --verify HEAD fails, no commit yet)",
               unborn.returncode != 0, True)
    rec.expect("after: no branch refs exist yet", g.refs(), {})
    rec.expect("after: the index is empty", g.index(), "")
    rec.expect("after: working tree untouched, notes.txt is untracked",
               (g.status(), (folder / "notes.txt").read_text()),
               ("?? notes.txt", "alpha\n"))

    # --- Transition 2: git init inside an existing repository ---------------
    g2, oids = make_fixture(tmp / "demo", env)
    before = {
        "head": g2.out("symbolic-ref", "HEAD"),
        "head_oid": g2.oid("HEAD"),
        "refs": g2.refs(),
        "index": g2.index(),
        "status": g2.status(),
        "parents": g2.out("rev-list", "--parents", "main"),
    }
    reinit = g2.run("init")
    rec.expect("re-init reports 'Reinitialized existing' repository",
               "Reinitialized existing" in reinit.stdout, True)
    after = {
        "head": g2.out("symbolic-ref", "HEAD"),
        "head_oid": g2.oid("HEAD"),
        "refs": g2.refs(),
        "index": g2.index(),
        "status": g2.status(),
        "parents": g2.out("rev-list", "--parents", "main"),
    }
    rec.expect("re-init: refs unchanged (main=C, topic=B)",
               (after["refs"]["refs/heads/main"], after["refs"]["refs/heads/topic"]),
               (oids["C"], oids["B"]))
    rec.expect("re-init: HEAD, index, status and ancestry identical", after, before)


if __name__ == "__main__":
    main(scenario, DESCRIPTION)
