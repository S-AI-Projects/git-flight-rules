#!/usr/bin/env python3
"""
Automated verification script for Git Flight Rules task R12-T044.

Validates branch and ref semantics for "Restore a deleted file" when the
current branch is topic and default branch is main. Verifies that the current
branch (topic) is updated while main remains unchanged.
"""

import os
import subprocess
import sys
import tempfile


def run_git(cmd, cwd, env, check=True):
    """Executes a git command and returns stdout."""
    res = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )
    return res.stdout


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
    commit_a = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()

    # 3. Commit B: appends "beta\n" to notes.txt and creates branch topic pointing at Commit B
    with open(notes_path, "a", encoding="utf-8") as f:
        f.write("beta\n")
    run_git(["git", "add", "notes.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit B: append beta to notes.txt"], cwd=repo_dir, env=env)
    commit_b = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()
    run_git(["git", "branch", "topic"], cwd=repo_dir, env=env)

    # 4. Commit C: creates todo.txt with "one\n" on branch main
    todo_path = os.path.join(repo_dir, "todo.txt")
    with open(todo_path, "w", encoding="utf-8") as f:
        f.write("one\n")
    run_git(["git", "add", "todo.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit C: create todo.txt"], cwd=repo_dir, env=env)
    commit_c = run_git(["git", "rev-parse", "refs/heads/main"], cwd=repo_dir, env=env).strip()

    # 5. Switch to branch topic
    run_git(["git", "checkout", "topic"], cwd=repo_dir, env=env)
    pre_topic_ref = run_git(["git", "rev-parse", "refs/heads/topic"], cwd=repo_dir, env=env).strip()
    assert pre_topic_ref == commit_b, "topic branch must point to Commit B"

    # 6. Delete notes.txt on topic
    run_git(["git", "rm", "notes.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit D: delete notes.txt on topic"], cwd=repo_dir, env=env)
    deleting_commit = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()

    # 7. Execute guide commands using HEAD on current branch (topic)
    found_commit = run_git(["git", "rev-list", "-n", "1", "HEAD", "--", "notes.txt"], cwd=repo_dir, env=env).strip()
    assert found_commit == deleting_commit, "rev-list -n 1 HEAD must find deleting commit"

    # Restore the file
    run_git(["git", "checkout", f"{deleting_commit}^", "--", "notes.txt"], cwd=repo_dir, env=env)

    # Check index and worktree state
    staged_after_checkout = run_git(["git", "diff", "--cached", "--name-only"], cwd=repo_dir, env=env).splitlines()
    assert staged_after_checkout == ["notes.txt"], "Restored file must be staged in index"

    with open(notes_path, "r", encoding="utf-8") as f:
        restored_content = f.read()

    # Commit restoration on topic
    run_git(["git", "commit", "-m", "Commit E: restore notes.txt on topic"], cwd=repo_dir, env=env)
    post_topic_ref = run_git(["git", "rev-parse", "refs/heads/topic"], cwd=repo_dir, env=env).strip()
    post_main_ref = run_git(["git", "rev-parse", "refs/heads/main"], cwd=repo_dir, env=env).strip()

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "deleting_commit": deleting_commit,
        "post_topic_ref": post_topic_ref,
        "post_main_ref": post_main_ref,
        "restored_content": restored_content,
        "staged_after_checkout": staged_after_checkout,
    }


def verify_repo_state(data: dict):
    # Assertion 1: Current branch (topic) changed and advanced
    assert data["post_topic_ref"] != data["commit_b"], "topic branch ref must advance"
    assert data["post_topic_ref"] != data["deleting_commit"], "topic branch ref must include restore commit"

    # Assertion 2: Unrelated default branch (main) stayed completely fixed
    assert data["post_main_ref"] == data["commit_c"], "main branch ref must remain exactly at Commit C"

    # Assertion 3: Restored content matches state prior to deletion (Commit B)
    assert data["restored_content"] == "alpha\nbeta\n", "Restored content must match Commit B"


def main():
    print("Starting verification of R12-T044...")
    with tempfile.TemporaryDirectory(prefix="gfr_t044_1_") as dir1, tempfile.TemporaryDirectory(prefix="gfr_t044_2_") as dir2:
        print(f"Executing workflow in temporary repo 1: {dir1}")
        res1 = run_workflow_in_dir(dir1)
        verify_repo_state(res1)
        print("  Repo 1: All branch/remote semantics assertions passed.")

        print(f"Executing workflow in temporary repo 2: {dir2}")
        res2 = run_workflow_in_dir(dir2)
        verify_repo_state(res2)
        print("  Repo 2: All branch/remote semantics assertions passed.")

        print("Checking cross-repository consistency...")
        assert res1["restored_content"] == res2["restored_content"]
        assert res1["staged_after_checkout"] == res2["staged_after_checkout"]
        print("  Cross-repository consistency verified.")

    print("\nSUCCESS: All branch semantics and recovery assertions passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
