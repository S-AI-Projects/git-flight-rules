import os
import subprocess
import sys
import tempfile


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, check=True,
                       capture_output=True, text=True)
    return r.stdout.strip()


def write(cwd, name, text, mode="w"):
    with open(os.path.join(cwd, name), mode) as f:
        f.write(text)


def run_once(d):
    git(d, "init", "-b", "main")
    git(d, "config", "user.name", "Course Student")
    git(d, "config", "user.email", "student@example.invalid")

    write(d, "notes.txt", "alpha\n")
    git(d, "add", "notes.txt")
    git(d, "commit", "-m", "A")

    write(d, "notes.txt", "beta\n", "a")
    git(d, "commit", "-am", "B")
    b = git(d, "rev-parse", "HEAD")

    write(d, "todo.txt", "one\n")
    git(d, "add", "todo.txt")
    git(d, "commit", "-m", "C")
    c = git(d, "rev-parse", "HEAD")

    git(d, "branch", "topic", b)
    git(d, "switch", "-c", "feature", "topic")
    write(d, "extra.txt", "extra\n")
    git(d, "add", "extra.txt")
    git(d, "commit", "-m", "D")
    d_old = git(d, "rev-parse", "HEAD")

    assert git(d, "rev-parse", "HEAD~1") == b

    git(d, "rebase", "--onto", "main", "topic", "feature")

    d_new = git(d, "rev-parse", "HEAD")
    log = git(d, "log", "--oneline", "--graph", "--all")
    status = git(d, "status")

    assert git(d, "rev-parse", "HEAD~1") == c
    assert git(d, "rev-parse", "main") == c
    assert git(d, "rev-parse", "topic") == b
    assert d_new != d_old
    assert open(os.path.join(d, "notes.txt")).read() == "alpha\nbeta\n"
    assert open(os.path.join(d, "todo.txt")).read() == "one\n"
    assert open(os.path.join(d, "extra.txt")).read() == "extra\n"
    assert "nothing to commit, working tree clean" in status
    return log, status


def main():
    out = os.path.dirname(os.path.abspath(__file__))
    results = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as d:
            results.append(run_once(d))
    with open(os.path.join(out, "evidence.txt"), "w") as f:
        f.write("git: " + subprocess.run(["git", "--version"], capture_output=True, text=True).stdout)
        f.write("python: " + sys.version + "\n")
        f.write("expected: D sits on top of C; main=C; topic=B\n")
        f.write("actual log:\n" + results[0][0] + "\n\nactual status:\n" + results[0][1] + "\n")
    print("ALL CHECKS PASSED")


main()
