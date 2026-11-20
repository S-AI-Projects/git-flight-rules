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


def setup_repos(root_dir):
    # If a remote is needed, use a second local bare repository and a file:// URL.
    bare_dir = os.path.join(root_dir, "remote.git")
    git(root_dir, "init", "--bare", "-b", "main", bare_dir)

    work_dir = os.path.join(root_dir, "repo")
    # Step 2: Use a temporary repository with branch main, author Course Student student@example.invalid,
    # and three commits: A creates notes.txt with "alpha\n"; B appends "beta\n";
    # C adds todo.txt with "one\n". Create branch topic at B.
    git(root_dir, "init", "-b", "main", work_dir)
    git(work_dir, "config", "user.name", "Course Student")
    git(work_dir, "config", "user.email", "student@example.invalid")

    write(work_dir, "notes.txt", "alpha\n")
    git(work_dir, "add", "notes.txt")
    git(work_dir, "commit", "-m", "A")
    a = git(work_dir, "rev-parse", "HEAD")

    write(work_dir, "notes.txt", "beta\n", "a")
    git(work_dir, "commit", "-am", "B")
    b = git(work_dir, "rev-parse", "HEAD")
    git(work_dir, "branch", "topic")

    write(work_dir, "todo.txt", "one\n")
    git(work_dir, "add", "todo.txt")
    git(work_dir, "commit", "-m", "C")
    c = git(work_dir, "rev-parse", "HEAD")

    # Connect remote origin to local bare repository
    git(work_dir, "remote", "add", "origin", f"file://{bare_dir}")
    git(work_dir, "push", "-u", "origin", "main")
    git(work_dir, "push", "origin", "topic")

    return work_dir, bare_dir, a, b, c


def run_once(root_dir):
    work_dir, bare_dir, a, b, c = setup_repos(root_dir)

    # Initial state assertions
    assert git(work_dir, "rev-parse", "main") == c
    assert git(work_dir, "rev-parse", "topic") == b
    assert git(work_dir, "rev-parse", "origin/main") == c
    assert git(work_dir, "rev-parse", "origin/topic") == b

    # Switch to topic branch where default branch is main
    git(work_dir, "switch", "topic")
    assert git(work_dir, "branch", "--show-current") == "topic"

    # Capture initial object IDs dynamically
    old_topic = git(work_dir, "rev-parse", "topic")
    old_main = git(work_dir, "rev-parse", "main")
    assert old_topic == b
    assert old_main == c

    # Execute named guide command anchors on topic:
    # Anchor: (main)$ git rm path/to/filetoremove | git commit -m "Commit removing filetoremove"
    # Here filetoremove is notes.txt on topic branch
    git(work_dir, "rm", "notes.txt")
    git(work_dir, "commit", "-m", "Commit removing filetoremove")

    new_topic = git(work_dir, "rev-parse", "topic")

    # Done when assertions:
    # 1. The check asserts the intended ref changed (topic changed to new commit)
    assert new_topic != old_topic
    assert git(work_dir, "rev-parse", "HEAD") == new_topic
    assert git(work_dir, "rev-parse", "HEAD~1") == b

    # 2. Unrelated refs stayed fixed (main remained at C, origin/* remained at initial pushes)
    assert git(work_dir, "rev-parse", "main") == old_main
    assert git(work_dir, "rev-parse", "origin/main") == c
    assert git(work_dir, "rev-parse", "origin/topic") == b

    # 3. No public remote or personal branch is used (verified file:// URL bare repo and standard branch names)
    remote_url = git(work_dir, "remote", "get-url", "origin")
    assert remote_url.startswith("file://")
    assert "github.com" not in remote_url

    # Meaningful state facts:
    # Fact 1: Working tree on topic reflects removal of notes.txt
    assert not os.path.exists(os.path.join(work_dir, "notes.txt"))
    assert git(work_dir, "status", "--porcelain") == ""

    # Fact 2: Switching to main restores all files from main commit C
    git(work_dir, "switch", "main")
    assert os.path.exists(os.path.join(work_dir, "notes.txt"))
    assert os.path.exists(os.path.join(work_dir, "todo.txt"))
    assert open(os.path.join(work_dir, "notes.txt")).read() == "alpha\nbeta\n"
    assert open(os.path.join(work_dir, "todo.txt")).read() == "one\n"

    # Fact 3: Commits are distinct between branches; main is unaffected by topic removal
    log_topic = git(work_dir, "log", "--oneline", "topic")
    log_main = git(work_dir, "log", "--oneline", "main")
    assert "Commit removing filetoremove" in log_topic
    assert "Commit removing filetoremove" not in log_main

    summary = (
        f"Initial IDs: A={a[:7]}, B={b[:7]}, C={c[:7]}\n"
        f"Branch 'topic' updated: {old_topic[:7]} -> {new_topic[:7]}\n"
        f"Branch 'main' unchanged: {old_main[:7]}\n"
        f"Remote 'origin/main' unchanged: {c[:7]}\n"
        f"Remote 'origin/topic' unchanged until pushed: {b[:7]}\n"
    )
    return summary


def main():
    out = os.path.dirname(os.path.abspath(__file__))
    results = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as root_dir:
            results.append(run_once(root_dir))

    with open(os.path.join(out, "evidence.txt"), "w") as f:
        f.write(subprocess.run(["git", "--version"], capture_output=True, text=True).stdout)
        f.write("python: " + sys.version.split()[0] + "\n\n")
        f.write("expected: When current branch is topic and default is main, git rm and commit update "
                "only the current branch (topic); unrelated refs (main, remote refs) stay unchanged; "
                "no public remote used.\n\n")
        f.write("actual:\n" + results[0])
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
