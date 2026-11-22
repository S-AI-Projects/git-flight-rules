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
DESCRIPTION = "Reproducible example for 'To stage part of tracked files' (git add -u <pathspec>)"


def run_once(rec, root, label):
    env = isolated_env(root / "home")
    g, oids = make_fixture(root / "demo", env)
    repo = g.cwd
    # Documented extra state (no hidden setup): one tracked edit, untracked files.
    with open(repo / "notes.txt", "a") as fh:
        fh.write("gamma\n")
    write(repo / "draft.txt", "draft\n")
    write(repo / "src" / "new.txt", "x\n")
    before = g.status()

    # Command 1 from the guide. The shell expands *.txt to
    # "draft.txt notes.txt todo.txt"; -u silently skips untracked draft.txt.
    names = sorted(p.name for p in repo.glob("*.txt"))
    g.run("add", "-u", *names)
    after_txt = g.status()
    # Command 2 from the guide: src/ only holds an untracked file.
    g.run("add", "-u", "src/")
    after_src = g.status()

    snapshot = {
        "refs": g.refs(),
        "head": g.out("symbolic-ref", "HEAD"),
        "index": g.index(),
        "files": {
            p.relative_to(repo).as_posix(): p.read_text()
            for p in sorted(repo.rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(repo).parts
        },
        "status_before": before,
        "status_after_txt": after_txt,
        "status_after_src": after_src,
        "log": g.out("log", "--format=%s", "main"),
        "staged_diff": g.out("diff", "--cached", "--name-status"),
    }
    rec.inputs.setdefault("runs", []).append({"label": label, "dir": str(root)})
    return g, oids, snapshot


def scenario(rec, tmp):
    rec.inputs["commands"] = [
        "printf 'gamma\\n' >> notes.txt",
        "printf 'draft\\n' > draft.txt",
        "mkdir src && printf 'x\\n' > src/new.txt",
        "git add -u *.txt",
        "git add -u src/",
    ]
    g1, oids, s1 = run_once(rec, tmp / "run1", "first temporary directory")
    g2, _, s2 = run_once(rec, tmp / "run2", "second temporary directory")

    rec.expect("status before staging", s1["status_before"],
               " M notes.txt\n?? draft.txt\n?? src/new.txt")
    rec.expect("git add -u *.txt stages only the tracked .txt edit",
               s1["status_after_txt"], "M  notes.txt\n?? draft.txt\n?? src/new.txt")
    rec.expect("git add -u src/ adds nothing (src/ holds only untracked files)",
               s1["status_after_src"], s1["status_after_txt"])
    rec.expect("index contains exactly the tracked files",
               [l.split("\t")[1] for l in s1["index"].splitlines()],
               ["notes.txt", "todo.txt"])
    rec.expect("staged notes.txt blob equals the edited working-tree file",
               g1.out("show", ":notes.txt"), "alpha\nbeta\ngamma")
    rec.expect("no ref moved: main still at C, topic still at B",
               (s1["refs"]["refs/heads/main"], s1["refs"]["refs/heads/topic"]),
               (oids["C"], oids["B"]))
    rec.expect("history is unchanged (C, B, A)", s1["log"], "C\nB\nA")
    rec.expect("run 1 and run 2 produce identical refs", s1["refs"], s2["refs"])
    rec.expect("run 1 and run 2 produce identical index state", s1["index"], s2["index"])
    rec.expect("run 1 and run 2 produce identical file contents", s1["files"], s2["files"])
    rec.expect("run 1 and run 2 produce identical status output",
               (s1["status_after_txt"], s1["status_after_src"]),
               (s2["status_after_txt"], s2["status_after_src"]))


if __name__ == "__main__":
    main(scenario, DESCRIPTION)
