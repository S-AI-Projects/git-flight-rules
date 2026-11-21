#!/usr/bin/env python3
"""
Automated verification script for Git Flight Rules task R12-T047.

Validates failure diagnosis for "I accidentally did a hard reset, and I want my changes back".
Constructs a violated precondition (invalid/nonexistent revision identifier),
captures Git's non-zero exit, applies the minimal correction (HEAD@{1} or valid reflog SHA),
and asserts that the repository state is restored cleanly.
"""

import os
import subprocess
import sys
import tempfile


def run_git(cmd, cwd, env, check=True):
    """Executes a git command and returns subprocess result."""
    res = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )
    return res


def run_workflow_in_dir(repo_dir: str) -> dict:
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"

    # 1. Initialize repo and author
    run_git(["git", "init", "-b", "main"], cwd=repo_dir, env=env)
    run_git(["git", "config", "user.name", "Course Student"], cwd=repo_dir, env=env)
    run_git(["git", "config", "user.email", "student@example.invalid"], cwd=repo_dir, env=env)

    # 2. Commit A: creates notes.txt with "alpha\n"
    notes_path = os.path.join(repo_dir, "notes.txt")
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write("alpha\n")
    run_git(["git", "add", "notes.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit A: create notes.txt"], cwd=repo_dir, env=env)
    commit_a = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()

    # 3. Commit B: appends "beta\n" to notes.txt and creates branch topic pointing at Commit B
    with open(notes_path, "a", encoding="utf-8") as f:
        f.write("beta\n")
    run_git(["git", "add", "notes.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit B: append beta to notes.txt"], cwd=repo_dir, env=env)
    commit_b = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()
    run_git(["git", "branch", "topic"], cwd=repo_dir, env=env)

    # 4. Commit C: creates todo.txt with "one\n" on branch main
    todo_path = os.path.join(repo_dir, "todo.txt")
    with open(todo_path, "w", encoding="utf-8") as f:
        f.write("one\n")
    run_git(["git", "add", "todo.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit C: create todo.txt"], cwd=repo_dir, env=env)
    commit_c = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()

    # 5. Accidental hard reset: moves main back to Commit B
    run_git(["git", "reset", "--hard", "HEAD~1"], cwd=repo_dir, env=env)
    post_accidental_head = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()
    assert post_accidental_head == commit_b, "HEAD must be at Commit B after accidental reset"

    # 6. Violated precondition: passing literal placeholder or nonexistent revision SHA1234
    bad_res = run_git(["git", "reset", "--hard", "SHA1234"], cwd=repo_dir, env=env, check=False)

    # 7. Repaired case: use HEAD@{1} (the reflog entry prior to the reset)
    repaired_res = run_git(["git", "reset", "--hard", "HEAD@{1}"], cwd=repo_dir, env=env, check=True)
    post_repaired_head = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()

    with open(todo_path, "r", encoding="utf-8") as f:
        todo_content = f.read()

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "post_accidental_head": post_accidental_head,
        "bad_returncode": bad_res.returncode,
        "bad_stderr": bad_res.stderr,
        "repaired_returncode": repaired_res.returncode,
        "post_repaired_head": post_repaired_head,
        "todo_content": todo_content,
    }


def verify_repo_state(data: dict):
    # Assertion 1: Bad case fails with non-zero exit code due to invalid revision
    assert data["bad_returncode"] != 0, "Bad command must fail with non-zero exit code"
    assert ("fatal:" in data["bad_stderr"] or "ambiguous" in data["bad_stderr"] or "unknown" in data["bad_stderr"]), \
        "Stderr must indicate unknown/invalid revision"

    # Assertion 2: Repaired command succeeds with exit code 0
    assert data["repaired_returncode"] == 0, "Repaired command must succeed"

    # Assertion 3: Repaired HEAD returns exactly to Commit C
    assert data["post_repaired_head"] == data["commit_c"], "HEAD must be restored to Commit C"

    # Assertion 4: Working tree contents of Commit C fully restored
    assert data["todo_content"] == "one\n", "todo.txt from Commit C must be restored in working tree"


def main():
    print("Starting verification of R12-T047...")
    with tempfile.TemporaryDirectory(prefix="gfr_t047_1_") as dir1, tempfile.TemporaryDirectory(prefix="gfr_t047_2_") as dir2:
        print(f"Executing workflow in temporary repo 1: {dir1}")
        res1 = run_workflow_in_dir(dir1)
        verify_repo_state(res1)
        print("  Repo 1: All failure diagnosis assertions passed.")

        print(f"Executing workflow in temporary repo 2: {dir2}")
        res2 = run_workflow_in_dir(dir2)
        verify_repo_state(res2)
        print("  Repo 2: All failure diagnosis assertions passed.")

        print("Checking cross-repository consistency...")
        assert res1["post_repaired_head"] == res2["post_repaired_head"]
        assert res1["todo_content"] == res2["todo_content"]
        print("  Cross-repository consistency verified.")

    print("\nSUCCESS: All failure diagnosis assertions passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
