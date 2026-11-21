#!/usr/bin/env python3
"""
Automated verification script for Git Flight Rules task R12-T050.

Validates the prediction-and-verification exercise for
"I want to move my unstaged edits to a new branch" using git checkout -b <branch>.
Asserts exact ref changes (HEAD switch, new branch creation at Commit C, main immutability)
and working tree persistence across two independent temporary repositories.
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
    commit_c = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()

    # 5. Make unstaged edits to both files
    with open(notes_path, "a", encoding="utf-8") as f:
        f.write("gamma\n")
    with open(todo_path, "a", encoding="utf-8") as f:
        f.write("two\n")

    # Record Pre-State
    pre_branch = run_git(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo_dir, env=env).strip()
    pre_unstaged = run_git(["git", "diff", "--name-only"], cwd=repo_dir, env=env).splitlines()
    pre_staged = run_git(["git", "diff", "--cached", "--name-only"], cwd=repo_dir, env=env).splitlines()

    # 6. Execute operation: create and switch to feature-edits
    run_git(["git", "checkout", "-b", "feature-edits"], cwd=repo_dir, env=env)

    # Record Post-State
    post_branch = run_git(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo_dir, env=env).strip()
    feature_ref = run_git(["git", "rev-parse", "refs/heads/feature-edits"], cwd=repo_dir, env=env).strip()
    main_ref = run_git(["git", "rev-parse", "refs/heads/main"], cwd=repo_dir, env=env).strip()
    topic_ref = run_git(["git", "rev-parse", "refs/heads/topic"], cwd=repo_dir, env=env).strip()
    post_unstaged = run_git(["git", "diff", "--name-only"], cwd=repo_dir, env=env).splitlines()
    post_staged = run_git(["git", "diff", "--cached", "--name-only"], cwd=repo_dir, env=env).splitlines()

    with open(notes_path, "r", encoding="utf-8") as f:
        notes_content = f.read()
    with open(todo_path, "r", encoding="utf-8") as f:
        todo_content = f.read()

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "pre_branch": pre_branch,
        "pre_unstaged": pre_unstaged,
        "pre_staged": pre_staged,
        "post_branch": post_branch,
        "feature_ref": feature_ref,
        "main_ref": main_ref,
        "topic_ref": topic_ref,
        "post_unstaged": post_unstaged,
        "post_staged": post_staged,
        "notes_content": notes_content,
        "todo_content": todo_content,
    }


def verify_repo_state(data: dict):
    # Assertion 1: Branch ref creation and HEAD movement
    assert data["post_branch"] == "feature-edits", "Active branch must switch to feature-edits"
    assert data["feature_ref"] == data["commit_c"], "New branch must point to Commit C"

    # Assertion 2: Existing branch refs remain untouched
    assert data["main_ref"] == data["commit_c"], "main branch ref must remain at Commit C"
    assert data["topic_ref"] == data["commit_b"], "topic branch ref must remain at Commit B"

    # Assertion 3: Unstaged edits carried over intact into new branch
    assert set(data["post_unstaged"]) == {"notes.txt", "todo.txt"}, "Unstaged edits must persist on new branch"
    assert data["post_staged"] == [], "No edits staged in index"

    # Assertion 4: Working tree content preserved exactly
    assert data["notes_content"] == "alpha\nbeta\ngamma\n", "notes.txt working tree content preserved"
    assert data["todo_content"] == "one\ntwo\n", "todo.txt working tree content preserved"


def main():
    print("Starting verification of R12-T050...")
    with tempfile.TemporaryDirectory(prefix="gfr_t050_1_") as dir1, tempfile.TemporaryDirectory(prefix="gfr_t050_2_") as dir2:
        print(f"Executing workflow in temporary repo 1: {dir1}")
        res1 = run_workflow_in_dir(dir1)
        verify_repo_state(res1)
        print("  Repo 1: All prediction and verification assertions passed.")

        print(f"Executing workflow in temporary repo 2: {dir2}")
        res2 = run_workflow_in_dir(dir2)
        verify_repo_state(res2)
        print("  Repo 2: All prediction and verification assertions passed.")

        print("Checking cross-repository consistency...")
        assert res1["post_branch"] == res2["post_branch"]
        assert res1["post_unstaged"] == res2["post_unstaged"]
        assert res1["notes_content"] == res2["notes_content"]
        assert res1["todo_content"] == res2["todo_content"]
        print("  Cross-repository consistency verified.")

    print("\nSUCCESS: All prediction and verification assertions passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
