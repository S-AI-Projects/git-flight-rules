import os
import subprocess
import sys
import tempfile


def git(cwd, *args, env=None, check=True):
    e = os.environ.copy()
    if env:
        e.update(env)
    r = subprocess.run(["git", *args], cwd=cwd, check=check,
                       capture_output=True, text=True, env=e)
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
    # Per-test config is strictly local, leaving user's global config untouched
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

    return work_dir, bare_dir, a, b, c


def run_once(root_dir):
    work_dir, bare_dir, a, b, c = setup_repos(root_dir)

    # Prerequisite verification / state assertion:
    # 1. Repository state: clean working directory, HEAD on main
    assert git(work_dir, "status", "--porcelain")[0] == ""
    assert git(work_dir, "branch", "--show-current")[0] == "main"
    assert git(work_dir, "rev-parse", "main")[0] == c
    assert git(work_dir, "rev-parse", "topic")[0] == b

    # 2. Remote configuration: remote 'origin' exists with valid file:// URL
    remote_url = git(work_dir, "remote", "get-url", "origin")[0]
    assert remote_url == f"file://{bare_dir}"

    # 3. Simulate origin/HEAD pointing to a non-default branch (e.g. topic)
    # in the local remote tracking refs:
    git(work_dir, "remote", "set-head", "origin", "topic")

    # Command anchor 1: git branch -r
    branches_r_before = git(work_dir, "branch", "-r")[0]
    assert "origin/HEAD -> origin/topic" in branches_r_before
    assert "origin/main" in branches_r_before
    assert git(work_dir, "symbolic-ref", "refs/remotes/origin/HEAD")[0] == "refs/remotes/origin/topic"

    # Command anchor 2: git remote set-head origin --auto
    # Run the named guide command
    out_auto, err_auto, code_auto = git(work_dir, "remote", "set-head", "origin", "--auto")
    assert code_auto == 0

    # Meaningful state facts after running command:
    # Fact 1: origin/HEAD successfully updated to point to remote default branch (main)
    branches_r_after = git(work_dir, "branch", "-r")[0]
    assert "origin/HEAD -> origin/main" in branches_r_after
    assert git(work_dir, "symbolic-ref", "refs/remotes/origin/HEAD")[0] == "refs/remotes/origin/main"

    # Fact 2: Working directory, index, and commit history remain completely untouched
    assert git(work_dir, "status", "--porcelain")[0] == ""
    assert git(work_dir, "rev-parse", "HEAD")[0] == c
    assert open(os.path.join(work_dir, "notes.txt")).read() == "alpha\nbeta\n"
    assert open(os.path.join(work_dir, "todo.txt")).read() == "one\n"

    # Fact 3: Unrelated branches (topic) remain fixed at commit B
    assert git(work_dir, "rev-parse", "topic")[0] == b
    assert git(bare_dir, "rev-parse", "refs/heads/topic")[0] == b

    summary = (
        f"Initial IDs: A={a[:7]}, B={b[:7]}, C={c[:7]}\n"
        f"Prerequisites verified: clean work tree, local repo config, remote 'origin' configured\n"
        f"Before: {branches_r_before.replace('\n', '; ')}\n"
        f"Executed: git remote set-head origin --auto (exit code {code_auto})\n"
        f"After: {branches_r_after.replace('\n', '; ')}\n"
        f"origin/HEAD updated: refs/remotes/origin/topic -> refs/remotes/origin/main\n"
        f"Topic unchanged at {b[:7]}\n"
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
        f.write("expected: Setting origin/HEAD to track default remote branch queries the remote; "
                "prerequisites (configured remote, local config, clean state) are validated explicitly; "
                "origin/HEAD updates to origin/main without altering commit refs or local files.\n\n")
        f.write("actual:\n" + results[0])
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
