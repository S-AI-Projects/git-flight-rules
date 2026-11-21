#!/usr/bin/env python3
"""
Automated verification script for Git Flight Rules task R12-T043.

Validates recovery from deleting an annotated tag using git fsck --unreachable
and git update-ref refs/tags/<tag_name> <hash>. Verifies tree hash match,
commit ancestry, and file contents across two independent temporary repos.
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
    commit_b_tree = run_git(["git", "rev-parse", f"{commit_b}^{{tree}}"], cwd=repo_dir, env=env).strip()
    run_git(["git", "branch", "topic"], cwd=repo_dir, env=env)

    # 4. Commit C: creates todo.txt with "one\n" on branch main
    todo_path = os.path.join(repo_dir, "todo.txt")
    with open(todo_path, "w", encoding="utf-8") as f:
        f.write("one\n")
    run_git(["git", "add", "todo.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit C: create todo.txt"], cwd=repo_dir, env=env)
    commit_c = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()

    # 5. Create annotated tag on topic (Commit B)
    run_git(["git", "tag", "-a", "v1.0", "-m", "Release v1.0", "topic"], cwd=repo_dir, env=env)
    original_tag_hash = run_git(["git", "rev-parse", "refs/tags/v1.0"], cwd=repo_dir, env=env).strip()
    tag_target_commit = run_git(["git", "rev-parse", "v1.0^{commit}"], cwd=repo_dir, env=env).strip()

    # 6. Reversible mistake: accidentally delete tag v1.0
    run_git(["git", "tag", "-d", "v1.0"], cwd=repo_dir, env=env)
    tag_deleted_check = subprocess.run(
        ["git", "rev-parse", "--verify", "refs/tags/v1.0"],
        cwd=repo_dir,
        env=env,
        capture_output=True,
    )
    assert tag_deleted_check.returncode != 0, "Tag v1.0 must be deleted"

    # 7. Recovery: Find unreachable tag object via git fsck --unreachable
    fsck_out = run_git(["git", "fsck", "--unreachable"], cwd=repo_dir, env=env)
    unreachable_tag_hash = None
    for line in fsck_out.splitlines():
        if "unreachable tag" in line:
            unreachable_tag_hash = line.split()[-1].strip()
            break

    assert unreachable_tag_hash is not None, "fsck must locate unreachable tag object"
    assert unreachable_tag_hash == original_tag_hash, "fsck unreachable tag hash must match original tag hash"

    # 8. Restore the deleted tag with git update-ref
    run_git(["git", "update-ref", "refs/tags/v1.0", unreachable_tag_hash], cwd=repo_dir, env=env)

    # 9. Verify recovered state
    recovered_tag_hash = run_git(["git", "rev-parse", "refs/tags/v1.0"], cwd=repo_dir, env=env).strip()
    recovered_commit = run_git(["git", "rev-parse", "v1.0^{commit}"], cwd=repo_dir, env=env).strip()
    recovered_tree = run_git(["git", "rev-parse", "v1.0^{tree}"], cwd=repo_dir, env=env).strip()
    recovered_notes_content = run_git(["git", "show", "v1.0:notes.txt"], cwd=repo_dir, env=env)
    tag_message = run_git(["git", "cat-file", "-p", recovered_tag_hash], cwd=repo_dir, env=env)

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "commit_b_tree": commit_b_tree,
        "original_tag_hash": original_tag_hash,
        "tag_target_commit": tag_target_commit,
        "unreachable_tag_hash": unreachable_tag_hash,
        "recovered_tag_hash": recovered_tag_hash,
        "recovered_commit": recovered_commit,
        "recovered_tree": recovered_tree,
        "recovered_notes_content": recovered_notes_content,
        "tag_message": tag_message,
    }


def verify_repo_state(data: dict):
    # Assertion 1: Tag object integrity
    assert data["recovered_tag_hash"] == data["original_tag_hash"], "Recovered tag hash must match original tag hash"
    assert data["recovered_commit"] == data["commit_b"], "Recovered tag must point to Commit B"

    # Assertion 2: Tree hash and file content match
    assert data["recovered_tree"] == data["commit_b_tree"], "Recovered tag tree must match Commit B tree hash"
    assert data["recovered_notes_content"] == "alpha\nbeta\n", "Recovered notes.txt content must match Commit B"

    # Assertion 3: Tag metadata and message preservation
    assert "Release v1.0" in data["tag_message"], "Tag annotation message must be preserved"


def main():
    print("Starting verification of R12-T043...")
    with tempfile.TemporaryDirectory(prefix="gfr_t043_1_") as dir1, tempfile.TemporaryDirectory(prefix="gfr_t043_2_") as dir2:
        print(f"Executing workflow in temporary repo 1: {dir1}")
        res1 = run_workflow_in_dir(dir1)
        verify_repo_state(res1)
        print("  Repo 1: All recovery assertions passed.")

        print(f"Executing workflow in temporary repo 2: {dir2}")
        res2 = run_workflow_in_dir(dir2)
        verify_repo_state(res2)
        print("  Repo 2: All recovery assertions passed.")

        print("Checking cross-repository consistency...")
        assert res1["recovered_notes_content"] == res2["recovered_notes_content"]
        assert "Release v1.0" in res1["tag_message"]
        print("  Cross-repository consistency verified.")

    print("\nSUCCESS: All recovery and state assertions passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
