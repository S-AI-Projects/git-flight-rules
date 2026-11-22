#!/usr/bin/env python3
"""Executable check for README.md > "Possible issues with interactive rebases".

Runs the guide's command sequence in a throwaway repository and asserts the
Git state after each step:

  1. 'noop'      - rebasing a branch onto a branch that is ahead of it
  2. conflicts   - git status, git checkout --theirs, git add, git rebase --continue
  3. abort       - git rebase --abort restores the original branch

Usage:
    python3 tests/guides/test_interactive_rebase_issues.py
    python3 tests/guides/test_interactive_rebase_issues.py --omit-decisive   # must FAIL

Standard library only. Never touches your own Git configuration: it uses a
temporary HOME and GIT_CONFIG_GLOBAL, and deletes the temporary directory.
Exit status is 0 on success and non-zero on any failed command or assertion.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

DATE = "2026-01-01T00:00:00+0000"
# Sequence editor that saves a copy of the todo list and accepts it unchanged.
SAVE_TODO = "import os, shutil, sys; shutil.copy(sys.argv[1], os.environ['TODO_COPY'])"


def git(repo, env, *args, check=True):
    proc = subprocess.run(["git", *args], cwd=repo, env=env, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise AssertionError("git %s failed (exit %d): %s"
                             % (" ".join(args), proc.returncode, proc.stderr.strip()))
    return proc


def rev(repo, env, name):
    return git(repo, env, "rev-parse", "--verify", name).stdout.strip()


def check(facts, name, actual, expected):
    facts.append({"fact": name, "expected": expected, "actual": actual})
    if actual != expected:
        raise AssertionError("%s: expected %r, got %r" % (name, expected, actual))


def make_env(tmp):
    home = tmp / "home"
    home.mkdir()
    (home / "gitconfig").write_text("")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(HOME=str(home), GIT_CONFIG_GLOBAL=str(home / "gitconfig"),
               GIT_CONFIG_NOSYSTEM="1", GIT_EDITOR="true", LC_ALL="C",
               GIT_AUTHOR_DATE=DATE, GIT_COMMITTER_DATE=DATE,
               TODO_COPY=str(tmp / "last-todo.txt"),
               GIT_SEQUENCE_EDITOR='"%s" -c "%s"' % (sys.executable, SAVE_TODO))
    return env


def commit(repo, env, path, text, msg):
    (repo / path).write_text(text)
    git(repo, env, "add", path)
    git(repo, env, "commit", "-q", "-m", msg)
    return rev(repo, env, "HEAD")


def run(omit_decisive=False):
    facts = []
    with tempfile.TemporaryDirectory(prefix="guide-rebase-") as tmpname:
        tmp = Path(tmpname)
        env = make_env(tmp)
        repo = tmp / "demo"
        repo.mkdir()
        git(repo, env, "init", "-q", "-b", "main")
        git(repo, env, "config", "user.name", "Course Student")
        git(repo, env, "config", "user.email", "student@example.invalid")
        a = commit(repo, env, "notes.txt", "alpha\n", "A")
        b = commit(repo, env, "notes.txt", "alpha\nbeta\n", "B")
        git(repo, env, "branch", "topic")
        c = commit(repo, env, "todo.txt", "one\n", "C")
        todo_copy = tmp / "last-todo.txt"

        # 1. noop: topic (B) is behind main (C), so there is nothing to replay.
        git(repo, env, "switch", "-q", "topic")
        git(repo, env, "rebase", "-i", "main")
        seen = [l for l in todo_copy.read_text().splitlines() if l and not l.startswith("#")]
        check(facts, "noop: the rebase todo list is just 'noop'", seen, ["noop"])
        check(facts, "noop: topic fast-forwarded to main (C)", rev(repo, env, "topic"), c)

        # 2. conflicts: both branches change line 2 of notes.txt.
        git(repo, env, "reset", "-q", "--hard", b)              # topic back to B
        t = commit(repo, env, "notes.txt", "alpha\nbeta (topic)\n", "T: topic edit")
        git(repo, env, "switch", "-q", "main")
        d = commit(repo, env, "notes.txt", "alpha\nbeta (main)\n", "D: main edit")
        git(repo, env, "switch", "-q", "topic")
        failed = git(repo, env, "rebase", "-i", "main", check=False)
        check(facts, "conflict: rebase stops with non-zero exit", failed.returncode != 0, True)
        status = git(repo, env, "status").stdout
        check(facts, "conflict: git status reports 'both modified: notes.txt'",
              "both modified:   notes.txt" in status, True)
        if not omit_decisive:
            # Decisive command: during a rebase, --theirs is the commit being replayed.
            git(repo, env, "checkout", "--theirs", "notes.txt")
        git(repo, env, "add", "notes.txt")
        git(repo, env, "rebase", "--continue")
        check(facts, "conflict: --theirs kept the topic (local branch) version",
              (repo / "notes.txt").read_text(), "alpha\nbeta (topic)\n")
        check(facts, "conflict: rebased topic now sits on top of main (D)",
              rev(repo, env, "topic^"), d)
        check(facts, "conflict: no rebase in progress afterwards",
              (repo / ".git" / "rebase-merge").exists(), False)

        # 3. abort: rebuild the conflicting branch and abort instead.
        git(repo, env, "branch", "-f", "topic2", t)
        git(repo, env, "switch", "-q", "topic2")
        git(repo, env, "rebase", "-i", "main", check=False)
        git(repo, env, "rebase", "--abort")
        check(facts, "abort: topic2 is back at its original commit T", rev(repo, env, "topic2"), t)
        check(facts, "abort: working tree and index are clean",
              git(repo, env, "status", "--short").stdout, "")
        check(facts, "main was never rewritten (D on top of C)",
              (rev(repo, env, "main"), rev(repo, env, "main^")), (d, c))
        result = {"tmpdir": tmpname, "facts": facts, "oids": {"A": a, "B": b, "C": c, "D": d, "T": t}}
    return result


if __name__ == "__main__":
    omit = "--omit-decisive" in sys.argv[1:]
    try:
        result = run(omit_decisive=omit)
    except AssertionError as exc:
        print("FAIL:", exc, file=sys.stderr)
        sys.exit(1)
    for f in result["facts"]:
        print("ok -", f["fact"])
    print(json.dumps(result))
