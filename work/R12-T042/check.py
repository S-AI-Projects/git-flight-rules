#!/usr/bin/env python3
"""
Automated verification script for Git Flight Rules task R12-T042.

Validates the state transition for "I want to choose which entire files to stage"
using git add -p (selecting 'a' for entire file). Runs the workflow across two
independent temporary repositories and verifies exact ref states, ancestry
immutability, index transitions, and working tree preservation.
"""

import os
import subprocess
import sys
import tempfile


def run_git(cmd, cwd, env, input_text=None):
    """Executes a git command and returns stdout."""
    res = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        input=input_text,
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout


def run_workflow_in_dir(repo_dir: str) -> dict:
    """Executes the exact workflow in repo_dir and collects all state transitions."""
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

    # 5. Modify both files in working tree
    with open(notes_path, "a", encoding="utf-8") as f:
        f.write("gamma\n")
    with open(todo_path, "a", encoding="utf-8") as f:
        f.write("two\n")

    # Record Pre-State
    pre_staged = run_git(["git", "diff", "--cached", "--name-only"], cwd=repo_dir, env=env).splitlines()
    pre_unstaged = run_git(["git", "diff", "--name-only"], cwd=repo_dir, env=env).splitlines()
    pre_head = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()
    pre_main = run_git(["git", "rev-parse", "refs/heads/main"], cwd=repo_dir, env=env).strip()
    pre_topic = run_git(["git", "rev-parse", "refs/heads/topic"], cwd=repo_dir, env=env).strip()
    pre_notes_index = run_git(["git", "show", ":notes.txt"], cwd=repo_dir, env=env)

    # 6. Execute git add -p notes.txt and choose 'a' (stage entire file)
    run_git(["git", "add", "-p", "notes.txt"], cwd=repo_dir, env=env, input_text="a\n")

    # Record Post-State
    post_staged = run_git(["git", "diff", "--cached", "--name-only"], cwd=repo_dir, env=env).splitlines()
    post_unstaged = run_git(["git", "diff", "--name-only"], cwd=repo_dir, env=env).splitlines()
    post_head = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()
    post_main = run_git(["git", "rev-parse", "refs/heads/main"], cwd=repo_dir, env=env).strip()
    post_topic = run_git(["git", "rev-parse", "refs/heads/topic"], cwd=repo_dir, env=env).strip()
    c_parent = run_git(["git", "rev-parse", f"{commit_c}^"], cwd=repo_dir, env=env).strip()
    b_parent = run_git(["git", "rev-parse", f"{commit_b}^"], cwd=repo_dir, env=env).strip()

    with open(notes_path, "r", encoding="utf-8") as f:
        notes_worktree = f.read()
    with open(todo_path, "r", encoding="utf-8") as f:
        todo_worktree = f.read()

    post_notes_index = run_git(["git", "show", ":notes.txt"], cwd=repo_dir, env=env)
    post_todo_index = run_git(["git", "show", ":todo.txt"], cwd=repo_dir, env=env)
    status_human = run_git(["git", "status"], cwd=repo_dir, env=env)

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "c_parent": c_parent,
        "b_parent": b_parent,
        "pre_head": pre_head,
        "pre_main": pre_main,
        "pre_topic": pre_topic,
        "pre_staged": pre_staged,
        "pre_unstaged": pre_unstaged,
        "pre_notes_index": pre_notes_index,
        "post_head": post_head,
        "post_main": post_main,
        "post_topic": post_topic,
        "post_staged": post_staged,
        "post_unstaged": post_unstaged,
        "post_notes_index": post_notes_index,
        "post_todo_index": post_todo_index,
        "notes_worktree": notes_worktree,
        "todo_worktree": todo_worktree,
        "status_human": status_human,
    }


def verify_repo_state(data: dict):
    # Assertion 1: Topology and Ref Immutability
    assert data["post_head"] == data["commit_c"], "HEAD must remain at Commit C"
    assert data["post_main"] == data["commit_c"], "refs/heads/main must remain at Commit C"
    assert data["post_topic"] == data["commit_b"], "refs/heads/topic must remain at Commit B"
    assert data["c_parent"] == data["commit_b"], "Commit C parent must be Commit B"
    assert data["b_parent"] == data["commit_a"], "Commit B parent must be Commit A"

    # Assertion 2: Pre-state vs Post-state Index Transition
    assert data["pre_staged"] == [], "Initially no files should be staged"
    assert set(data["pre_unstaged"]) == {"notes.txt", "todo.txt"}, "Both modified files unstaged initially"
    assert data["post_staged"] == ["notes.txt"], "Only notes.txt staged after git add -p with 'a'"
    assert data["post_unstaged"] == ["todo.txt"], "todo.txt remains unstaged"

    # Assertion 3: Blob content in Index
    assert data["pre_notes_index"] == "alpha\nbeta\n", "Pre-state index had Commit B content"
    assert data["post_notes_index"] == "alpha\nbeta\ngamma\n", "Post-state index has working tree content"
    assert data["post_todo_index"] == "one\n", "todo.txt in index unchanged at Commit C content"

    # Assertion 4: Working tree preservation
    assert data["notes_worktree"] == "alpha\nbeta\ngamma\n", "Working tree notes.txt preserved"
    assert data["todo_worktree"] == "one\ntwo\n", "Working tree todo.txt preserved"


def main():
    print("Starting verification of R12-T042...")
    with tempfile.TemporaryDirectory(prefix="gfr_t042_1_") as dir1, tempfile.TemporaryDirectory(prefix="gfr_t042_2_") as dir2:
        print(f"Executing workflow in temporary repo 1: {dir1}")
        res1 = run_workflow_in_dir(dir1)
        verify_repo_state(res1)
        print("  Repo 1: All state assertions passed.")

        print(f"Executing workflow in temporary repo 2: {dir2}")
        res2 = run_workflow_in_dir(dir2)
        verify_repo_state(res2)
        print("  Repo 2: All state assertions passed.")

        print("Checking cross-repository consistency...")
        assert res1["post_staged"] == res2["post_staged"]
        assert res1["post_unstaged"] == res2["post_unstaged"]
        assert res1["notes_worktree"] == res2["notes_worktree"]
        assert res1["todo_worktree"] == res2["todo_worktree"]
        assert res1["post_notes_index"] == res2["post_notes_index"]
        print("  Cross-repository consistency verified.")

    print("\nSUCCESS: All state transition assertions passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
