import os
import subprocess
import sys
import tempfile


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, check=True,
                       capture_output=True, text=True)
    return r.stdout.strip()


def write(cwd, name, text, mode="w"):
    path = os.path.join(cwd, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode) as f:
        f.write(text)


def build(d):
    # Step 2 setup:
    # Use a temporary repository with branch main, author Course Student student@example.invalid,
    # and three commits: A creates notes.txt with "alpha\n"; B appends "beta\n";
    # C adds todo.txt with "one\n". Create branch topic at B.
    git(d, "init", "-b", "main")
    git(d, "config", "user.name", "Course Student")
    git(d, "config", "user.email", "student@example.invalid")

    write(d, "notes.txt", "alpha\n")
    git(d, "add", "notes.txt")
    git(d, "commit", "-m", "A")
    a = git(d, "rev-parse", "HEAD")

    write(d, "notes.txt", "beta\n", "a")
    git(d, "commit", "-am", "B")
    b = git(d, "rev-parse", "HEAD")
    git(d, "branch", "topic")

    write(d, "todo.txt", "one\n")
    git(d, "add", "todo.txt")
    git(d, "commit", "-m", "C")
    c = git(d, "rev-parse", "HEAD")

    return a, b, c


def run_once(d):
    a, b, c = build(d)

    # 1. Capture object IDs dynamically
    tree_c = git(d, "rev-parse", "HEAD^{tree}")
    assert git(d, "rev-parse", "main") == c
    assert git(d, "rev-parse", "topic") == b

    # 2. Test command anchors:
    # Anchor 1: git log -- <file>
    log_notes = git(d, "log", "--format=%H %s", "--", "notes.txt")
    assert f"{b} B" in log_notes
    assert f"{a} A" in log_notes
    assert c not in log_notes

    log_todo = git(d, "log", "--format=%H %s", "--", "todo.txt")
    assert f"{c} C" in log_todo
    assert b not in log_todo

    # Anchor 2 & 3: git log -- **/*.txt / git log --name-status -- **/*.txt
    log_all_txt = git(d, "log", "--oneline", "--name-status", "--", "*.txt")
    assert "notes.txt" in log_all_txt
    assert "todo.txt" in log_all_txt

    # 3. Mistake & Recovery:
    # Mistake: running `git log -- todo.txt` while on `topic` branch or looking at wrong ref,
    # or accidentally checking out a commit/branch or detaching HEAD, thinking todo.txt commits are missing.
    # Specifically demonstrate: on `topic` branch, `git log -- todo.txt` returns empty!
    git(d, "switch", "topic")
    log_topic_todo = git(d, "log", "--oneline", "--", "todo.txt")
    assert log_topic_todo == ""

    # Recovery: use `--all` flag or inspect all branches to find commits containing todo.txt across all refs
    log_recovered = git(d, "log", "--format=%H %s", "--all", "--", "todo.txt")
    assert f"{c} C" in log_recovered

    # Switch back to main to verify working tree and tree hash
    git(d, "switch", "main")
    tree_recovered = git(d, "rev-parse", "HEAD^{tree}")

    # Meaningful state assertions:
    # Assertion 1: Recovered tree matches saved tree hash
    assert tree_recovered == tree_c

    # Assertion 2: File contents match exactly
    assert open(os.path.join(d, "notes.txt")).read() == "alpha\nbeta\n"
    assert open(os.path.join(d, "todo.txt")).read() == "one\n"

    # Assertion 3: Working tree is clean and branches are intact
    assert git(d, "status", "--porcelain") == ""
    assert git(d, "rev-parse", "main") == c
    assert git(d, "rev-parse", "topic") == b

    summary = (
        f"commits: A={a[:7]}, B={b[:7]}, C={c[:7]}\n"
        f"log -- notes.txt:\n{log_notes}\n"
        f"log -- todo.txt on main:\n{log_todo}\n"
        f"log -- todo.txt on topic (mistake / empty):\n'{log_topic_todo}'\n"
        f"log --all -- todo.txt (recovered):\n{log_recovered}\n"
    )
    return summary


def main():
    out = os.path.dirname(os.path.abspath(__file__))
    results = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as d:
            results.append(run_once(d))

    with open(os.path.join(out, "evidence.txt"), "w") as f:
        f.write(subprocess.run(["git", "--version"], capture_output=True, text=True).stdout)
        f.write("python: " + sys.version.split()[0] + "\n\n")
        f.write("expected: git log -- <file> lists only commits affecting <file>; "
                "searching on a branch lacking the commit yields empty, recoverable via --all; "
                "tree hash and file contents match original commit C\n\n")
        f.write("actual:\n" + results[0])
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
