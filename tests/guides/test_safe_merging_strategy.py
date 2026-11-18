#!/usr/bin/env python3
"""
Automated integration check for "Safe merging strategy" in git-flight-rules.
Anchor: git merge --no-ff --no-commit my-branch

Verifies:
1. Isolated temporary repository setup with branch main, author Course Student <student@example.invalid>,
   commits A, B, C on main, topic branched from B with commit D.
2. Safe merge execution: git merge --no-ff --no-commit topic.
3. State fact assertions:
   - HEAD ref does not advance (remains at Commit C because of --no-commit).
   - MERGE_HEAD exists in .git/MERGE_HEAD and matches the topic commit hash.
   - The merge changes are staged in Git's index (git status shows 'A  feature.txt').
   - Working tree contains both main files and topic files.
4. Child process failure propagation: Subprocess errors are propagated via check=True.
5. Temporary directory cleanup: Cleaned automatically via tempfile context managers.
"""

import os
import subprocess
import sys
import tempfile


def run_cmd(cmd, cwd=None, strip=True):
    """Run subprocess command with check=True to propagate child failures."""
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert proc.returncode == 0, f"Command {cmd} failed with returncode {proc.returncode}"
    return proc.stdout.strip() if strip else proc.stdout


def setup_repository(repo_dir):
    """
    Sets up the repository with required commits:
    - Commit A: notes.txt with "alpha\n"
    - Commit B: notes.txt with "beta\n"
    - Branch topic created at Commit B
    - Commit C: todo.txt with "one\n" on main
    - Commit D: feature.txt with "topic feature\n" on topic
    """
    run_cmd(["git", "init", "-b", "main", repo_dir])
    run_cmd(["git", "config", "user.name", "Course Student"], cwd=repo_dir)
    run_cmd(["git", "config", "user.email", "student@example.invalid"], cwd=repo_dir)
    run_cmd(["git", "config", "commit.gpgSign", "false"], cwd=repo_dir)

    # Commit A
    notes_path = os.path.join(repo_dir, "notes.txt")
    with open(notes_path, "w") as f:
        f.write("alpha\n")
    run_cmd(["git", "add", "notes.txt"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "Commit A: create notes.txt"], cwd=repo_dir)
    commit_a_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    commit_a_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_dir)

    # Commit B
    with open(notes_path, "a") as f:
        f.write("beta\n")
    run_cmd(["git", "add", "notes.txt"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "Commit B: append beta"], cwd=repo_dir)
    commit_b_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    commit_b_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_dir)

    # Create branch topic at Commit B
    run_cmd(["git", "branch", "topic"], cwd=repo_dir)

    # Commit C on main
    todo_path = os.path.join(repo_dir, "todo.txt")
    with open(todo_path, "w") as f:
        f.write("one\n")
    run_cmd(["git", "add", "todo.txt"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "Commit C: add todo.txt"], cwd=repo_dir)
    commit_c_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    commit_c_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_dir)

    # Checkout topic and create Commit D
    run_cmd(["git", "checkout", "topic"], cwd=repo_dir)
    feat_path = os.path.join(repo_dir, "feature.txt")
    with open(feat_path, "w") as f:
        f.write("topic feature\n")
    run_cmd(["git", "add", "feature.txt"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "Commit D: add feature on topic"], cwd=repo_dir)
    commit_d_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    commit_d_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_dir)

    # Return to main
    run_cmd(["git", "checkout", "main"], cwd=repo_dir)

    return {
        "commit_a_hash": commit_a_hash,
        "commit_a_tree": commit_a_tree,
        "commit_b_hash": commit_b_hash,
        "commit_b_tree": commit_b_tree,
        "commit_c_hash": commit_c_hash,
        "commit_c_tree": commit_c_tree,
        "commit_d_hash": commit_d_hash,
        "commit_d_tree": commit_d_tree,
    }


def execute_safe_merge_test(repo_dir, omit_decisive_command=False):
    """
    Executes or omits the decisive merge command and evaluates resulting Git state.
    """
    fixture = setup_repository(repo_dir)
    head_before = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)

    if not omit_decisive_command:
        # Decisive command from guide: git merge --no-ff --no-commit my-branch
        run_cmd(["git", "merge", "--no-ff", "--no-commit", "topic"], cwd=repo_dir)

    head_after = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    merge_head_file = os.path.join(repo_dir, ".git", "MERGE_HEAD")
    merge_head_exists = os.path.exists(merge_head_file)
    merge_head_content = None
    if merge_head_exists:
        with open(merge_head_file) as f:
            merge_head_content = f.read().strip()

    status_output = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
    feature_file_exists = os.path.exists(os.path.join(repo_dir, "feature.txt"))

    if omit_decisive_command:
        # Assert that omitting the decisive command leaves repo without merge state
        assert not merge_head_exists, "MERGE_HEAD must not exist when decisive command is omitted"
        assert status_output == "", "Status must be clean when decisive command is omitted"
        return {
            "omitted": True,
            "merge_head_exists": merge_head_exists,
            "status_output": status_output,
        }

    # State fact 1: HEAD ref does NOT change (remains at Commit C because of --no-commit)
    assert head_before == head_after == fixture["commit_c_hash"], (
        f"HEAD advanced unexpectedly: {head_before} != {head_after}"
    )

    # State fact 2: MERGE_HEAD exists and records topic commit hash
    assert merge_head_exists, ".git/MERGE_HEAD must exist after git merge --no-commit"
    assert merge_head_content == fixture["commit_d_hash"], (
        f"MERGE_HEAD {merge_head_content} does not match topic commit {fixture['commit_d_hash']}"
    )

    # State fact 3: The merged changes are staged in the index
    assert "A  feature.txt" in status_output, (
        f"Expected staged 'A  feature.txt' in status, got: {status_output}"
    )

    # State fact 4: Working tree contains merged files
    assert feature_file_exists, "feature.txt must exist in working tree"
    with open(os.path.join(repo_dir, "feature.txt")) as f:
        assert f.read() == "topic feature\n"

    return {
        "omitted": False,
        "fixture": fixture,
        "head_before": head_before,
        "head_after": head_after,
        "merge_head_exists": merge_head_exists,
        "merge_head_content": merge_head_content,
        "status_output": status_output,
        "feature_file_exists": feature_file_exists,
    }


def main():
    print("Running focused guide test for: Safe merging strategy...")
    with tempfile.TemporaryDirectory(prefix="gfr_safe_merge_") as td:
        repo_dir = os.path.join(td, "repo")
        result = execute_safe_merge_test(repo_dir, omit_decisive_command=False)
        print("  State Fact 1: HEAD unchanged at Commit C:", result["head_after"])
        print("  State Fact 2: MERGE_HEAD recorded topic commit:", result["merge_head_content"])
        print("  State Fact 3: Staged index changes:", result["status_output"])
        print("  State Fact 4: Working tree contains feature.txt:", result["feature_file_exists"])

    # Verify negative test: omitting decisive command fails assertions
    print("Testing negative scenario (omitting decisive command)...")
    with tempfile.TemporaryDirectory(prefix="gfr_safe_merge_omit_") as td_omit:
        repo_dir_omit = os.path.join(td_omit, "repo")
        omit_result = execute_safe_merge_test(repo_dir_omit, omit_decisive_command=True)
        assert omit_result["omitted"] is True
        print("  Verified: Omitting decisive command prevents merge state from appearing.")

    print("All focused guide tests PASSED successfully!")


if __name__ == "__main__":
    main()
