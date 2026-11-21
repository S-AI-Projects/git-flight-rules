#!/usr/bin/env python3
"""
Automated verification script for Git Flight Rules task R12-T045.

Validates path quoting and '--' disambiguation for discarding unstaged changes
in paths containing spaces ("release notes.txt" and "sample data"). Runs across
two independent temporary repositories.
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

    # 5. Create file with spaces and directory with spaces
    rel_notes_path = os.path.join(repo_dir, "release notes.txt")
    with open(rel_notes_path, "w", encoding="utf-8") as f:
        f.write("v1.0.0 initial notes\n")

    sample_dir = os.path.join(repo_dir, "sample data")
    os.makedirs(sample_dir, exist_ok=True)
    sample_file = os.path.join(sample_dir, "records.txt")
    with open(sample_file, "w", encoding="utf-8") as f:
        f.write("record 1\n")

    run_git(["git", "add", "release notes.txt", "sample data"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit D: add release notes and sample data"], cwd=repo_dir, env=env)

    # 6. Introduce unstaged modifications to both
    with open(rel_notes_path, "a", encoding="utf-8") as f:
        f.write("draft edit in release notes\n")

    with open(sample_file, "a", encoding="utf-8") as f:
        f.write("draft edit in sample data\n")

    # 7. Demonstrate failure when spaces are unquoted (word splitting)
    unquoted_res = run_git(["git", "checkout", "release", "notes.txt"], cwd=repo_dir, env=env, check=False)
    assert unquoted_res.returncode != 0, "Unquoted spaced path must fail due to argument splitting"
    assert "pathspec" in unquoted_res.stderr or "did not match" in unquoted_res.stderr

    # 8. Correctly discard unstaged changes in "release notes.txt" using '--' and quotes
    quoted_file_res = run_git(["git", "checkout", "--", "release notes.txt"], cwd=repo_dir, env=env)
    assert quoted_file_res.returncode == 0

    with open(rel_notes_path, "r", encoding="utf-8") as f:
        restored_rel_notes = f.read()

    # "sample data/records.txt" must still retain its unstaged draft edit
    with open(sample_file, "r", encoding="utf-8") as f:
        retained_sample_edit = f.read()

    # 9. Discard unstaged changes in directory with spaces "sample data"
    quoted_dir_res = run_git(["git", "checkout", "--", "sample data"], cwd=repo_dir, env=env)
    assert quoted_dir_res.returncode == 0

    with open(sample_file, "r", encoding="utf-8") as f:
        restored_sample_file = f.read()

    unstaged_after = run_git(["git", "diff", "--name-only"], cwd=repo_dir, env=env).stdout.splitlines()

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "unquoted_stderr": unquoted_res.stderr,
        "restored_rel_notes": restored_rel_notes,
        "retained_sample_edit": retained_sample_edit,
        "restored_sample_file": restored_sample_file,
        "unstaged_after": unstaged_after,
    }


def verify_repo_state(data: dict):
    # Assertion 1: Unquoted path splitting error captured
    assert "release" in data["unquoted_stderr"], "Error must reflect pathspec 'release' mismatch"

    # Assertion 2: Discarding file with space restored exact original committed content
    assert data["restored_rel_notes"] == "v1.0.0 initial notes\n", "release notes.txt must match clean commit"

    # Assertion 3: Unstaged edits in directory preserved prior to targeted directory discard
    assert "draft edit in sample data\n" in data["retained_sample_edit"], "sample data edit must be retained until discarded"

    # Assertion 4: Discarding directory with space restored exact original content
    assert data["restored_sample_file"] == "record 1\n", "sample data/records.txt must match clean commit"

    # Assertion 5: Working tree completely clean after both discards
    assert data["unstaged_after"] == [], "No unstaged files should remain"


def main():
    print("Starting verification of R12-T045...")
    with tempfile.TemporaryDirectory(prefix="gfr_t045_1_") as dir1, tempfile.TemporaryDirectory(prefix="gfr_t045_2_") as dir2:
        print(f"Executing workflow in temporary repo 1: {dir1}")
        res1 = run_workflow_in_dir(dir1)
        verify_repo_state(res1)
        print("  Repo 1: All quoting and path handling assertions passed.")

        print(f"Executing workflow in temporary repo 2: {dir2}")
        res2 = run_workflow_in_dir(dir2)
        verify_repo_state(res2)
        print("  Repo 2: All quoting and path handling assertions passed.")

        print("Checking cross-repository consistency...")
        assert res1["restored_rel_notes"] == res2["restored_rel_notes"]
        assert res1["restored_sample_file"] == res2["restored_sample_file"]
        print("  Cross-repository consistency verified.")

    print("\nSUCCESS: All path handling and quoting assertions passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
