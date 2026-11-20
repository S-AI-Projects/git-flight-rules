import os
import shutil
import subprocess
import sys
import tempfile


def git(cwd, *args, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, check=check,
                       capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def write(cwd, name, text, mode="w"):
    path = os.path.join(cwd, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode) as f:
        f.write(text)


def setup_repos(root_dir):
    # Step 2: Use a temporary repository with branch main, author Course Student student@example.invalid,
    # and three commits: A creates notes.txt with "alpha\n"; B appends "beta\n";
    # C adds todo.txt with "one\n". Create branch topic at B.
    # If a remote is needed, use a second local bare repository and a file:// URL.
    bare_dir = os.path.join(root_dir, "remote.git")
    git(root_dir, "init", "--bare", "-b", "main", bare_dir)

    work_dir = os.path.join(root_dir, "repo")
    git(root_dir, "init", "-b", "main", work_dir)
    git(work_dir, "config", "user.name", "Course Student")
    git(work_dir, "config", "user.email", "student@example.invalid")

    write(work_dir, "notes.txt", "alpha\n")
    git(work_dir, "add", "notes.txt")
    git(work_dir, "commit", "-m", "A")
    a = git(work_dir, "rev-parse", "HEAD")[0]

    write(work_dir, "notes.txt", "beta\n", "a")
    git(work_dir, "commit", "-am", "B")
    b = git(work_dir, "rev-parse", "HEAD")[0]
    git(work_dir, "branch", "topic")

    write(work_dir, "todo.txt", "one\n")
    git(work_dir, "add", "todo.txt")
    git(work_dir, "commit", "-m", "C")
    c = git(work_dir, "rev-parse", "HEAD")[0]

    git(work_dir, "remote", "add", "origin", f"file://{bare_dir}")
    git(work_dir, "push", "-u", "origin", "main")
    git(work_dir, "push", "origin", "topic")

    # Set up remote 'wrong-branch' branched from main (at commit C) with an extra commit
    other_work = os.path.join(root_dir, "other_repo")
    git(root_dir, "clone", f"file://{bare_dir}", other_work)
    git(other_work, "config", "user.name", "Course Student")
    git(other_work, "config", "user.email", "student@example.invalid")
    git(other_work, "switch", "-c", "wrong-branch")
    write(other_work, "wrong.txt", "wrong content\n")
    git(other_work, "add", "wrong.txt")
    git(other_work, "commit", "-m", "wrong commit")
    git(other_work, "push", "-u", "origin", "wrong-branch")

    return work_dir, bare_dir, a, b, c


def run_integration_test(root_dir, omit_decisive_command=False):
    work_dir, bare_dir, a, b, c = setup_repos(root_dir)

    # State fact 1: Initial ref state before accidental pull
    assert git(work_dir, "rev-parse", "main")[0] == c
    assert git(work_dir, "rev-parse", "topic")[0] == b
    tree_c = git(work_dir, "rev-parse", "HEAD^{tree}")[0]

    # Command anchor 1: Accidental pull from wrong branch
    # User on (main) accidentally pulls from wrong-branch
    out_pull, err_pull, code_pull = git(work_dir, "pull", "origin", "wrong-branch")
    assert code_pull == 0

    # Command anchor 2: (main)$ git reflog
    reflog_out, _, _ = git(work_dir, "reflog", "-n", "3")
    assert "pull origin wrong-branch" in reflog_out
    pre_pull_commit = git(work_dir, "rev-parse", "HEAD@{1}")[0]
    assert pre_pull_commit == c

    # Command anchor 3: git reset --hard <target_commit>
    # Decisive command: resetting back to pre-pull commit identified from reflog
    if not omit_decisive_command:
        out_reset, err_reset, code_reset = git(work_dir, "reset", "--hard", pre_pull_commit)
        assert code_reset == 0

    # State assertions:
    # Meaningful state fact 1: HEAD and main point to original commit C
    current_head = git(work_dir, "rev-parse", "HEAD")[0]
    assert current_head == c, f"Expected HEAD to be {c}, got {current_head}"

    # Meaningful state fact 2: Tree hash and working directory files match pre-pull state exactly
    current_tree = git(work_dir, "rev-parse", "HEAD^{tree}")[0]
    assert current_tree == tree_c, f"Expected tree {tree_c}, got {current_tree}"
    assert not os.path.exists(os.path.join(work_dir, "wrong.txt")), "wrong.txt should not exist after reset"
    assert open(os.path.join(work_dir, "notes.txt")).read() == "alpha\nbeta\n"
    assert open(os.path.join(work_dir, "todo.txt")).read() == "one\n"

    # Meaningful state fact 3: Working tree is clean and unrelated branch topic stayed fixed
    status = git(work_dir, "status", "--porcelain")[0]
    assert status == ""
    assert git(work_dir, "rev-parse", "topic")[0] == b

    return (
        f"Pre-pull commit C: {c[:7]}\n"
        f"Accidental pull merged/fast-forwarded wrong-branch\n"
        f"Reflog verified pre-pull commit: {pre_pull_commit[:7]}\n"
        f"Decisive command 'git reset --hard {pre_pull_commit[:7]}' restored tree {tree_c[:7]}\n"
        f"Branch 'topic' remained fixed at {b[:7]}\n"
    )


def test_runner():
    out = os.path.dirname(os.path.abspath(__file__))
    summary = None

    # Test 1: Full integration check (should pass and clean temporary directory)
    temp_dir = tempfile.mkdtemp()
    try:
        summary = run_integration_test(temp_dir, omit_decisive_command=False)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    assert not os.path.exists(temp_dir), "Temporary directory was not cleaned"

    # Test 2: Verify test fails when decisive command is deliberately omitted
    temp_dir_negative = tempfile.mkdtemp()
    negative_failed = False
    try:
        run_integration_test(temp_dir_negative, omit_decisive_command=True)
    except AssertionError:
        negative_failed = True
    finally:
        shutil.rmtree(temp_dir_negative, ignore_errors=True)
    assert not os.path.exists(temp_dir_negative), "Negative test temporary directory was not cleaned"
    assert negative_failed, "Test did not fail when the decisive command was deliberately omitted"

    with open(os.path.join(out, "evidence.txt"), "w") as f:
        f.write(subprocess.run(["git", "--version"], capture_output=True, text=True).stdout)
        f.write("python: " + sys.version.split()[0] + "\n\n")
        f.write("expected: An accidental pull from the wrong branch is recovered using "
                "git reflog and git reset --hard <commit>; test verifies child failures propagate, "
                "cleans temp dirs, and fails when the decisive reset command is omitted.\n\n")
        f.write("actual:\n" + summary)

    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    test_runner()
