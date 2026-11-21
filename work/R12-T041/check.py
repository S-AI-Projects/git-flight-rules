#!/usr/bin/env python3
"""
Automated verification script for Git Flight Rules task R12-T041.

Validates the reproducible setup for "I want to unstage a specific staged file"
using git reset -- <filename>. Runs the workflow across two independent
temporary repositories and verifies exact ref states, index/working tree
distinctions, and content preservation.
"""

import os
import subprocess
import sys
import tempfile


def run_git(cmd, cwd, env):
    """Executes a git command with check=True and returns standard output."""
    res = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout


def run_workflow_in_dir(repo_dir: str) -> dict:
    """Executes the exact reproducible workflow in repo_dir and collects state."""
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

    # 5. Modify both files
    with open(notes_path, "a", encoding="utf-8") as f:
        f.write("gamma\n")
    with open(todo_path, "a", encoding="utf-8") as f:
        f.write("two\n")

    # 6. Stage both files
    run_git(["git", "add", "notes.txt", "todo.txt"], cwd=repo_dir, env=env)

    pre_staged = run_git(["git", "diff", "--cached", "--name-only"], cwd=repo_dir, env=env).splitlines()
    pre_unstaged = run_git(["git", "diff", "--name-only"], cwd=repo_dir, env=env).splitlines()

    # 7. Unstage notes.txt using git reset --
    reset_stdout = run_git(["git", "reset", "--", "notes.txt"], cwd=repo_dir, env=env)

    # 8. Collect final state
    post_staged = run_git(["git", "diff", "--cached", "--name-only"], cwd=repo_dir, env=env).splitlines()
    post_unstaged = run_git(["git", "diff", "--name-only"], cwd=repo_dir, env=env).splitlines()
    untracked = run_git(["git", "ls-files", "--others", "--exclude-standard"], cwd=repo_dir, env=env).splitlines()
    status_porcelain = run_git(["git", "status", "--porcelain"], cwd=repo_dir, env=env)
    status_human = run_git(["git", "status"], cwd=repo_dir, env=env)
    log_all = run_git(["git", "log", "--oneline", "--graph", "--all"], cwd=repo_dir, env=env)

    main_ref = run_git(["git", "rev-parse", "refs/heads/main"], cwd=repo_dir, env=env).strip()
    topic_ref = run_git(["git", "rev-parse", "refs/heads/topic"], cwd=repo_dir, env=env).strip()
    head_ref = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()
    c_parent = run_git(["git", "rev-parse", f"{commit_c}^"], cwd=repo_dir, env=env).strip()
    b_parent = run_git(["git", "rev-parse", f"{commit_b}^"], cwd=repo_dir, env=env).strip()

    with open(notes_path, "r", encoding="utf-8") as f:
        notes_worktree = f.read()
    with open(todo_path, "r", encoding="utf-8") as f:
        todo_worktree = f.read()

    notes_index = run_git(["git", "show", ":notes.txt"], cwd=repo_dir, env=env)
    todo_index = run_git(["git", "show", ":todo.txt"], cwd=repo_dir, env=env)

    return {
        "repo_dir": repo_dir,
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "main_ref": main_ref,
        "topic_ref": topic_ref,
        "head_ref": head_ref,
        "c_parent": c_parent,
        "b_parent": b_parent,
        "pre_staged": sorted(pre_staged),
        "pre_unstaged": pre_unstaged,
        "reset_stdout": reset_stdout,
        "post_staged": post_staged,
        "post_unstaged": post_unstaged,
        "untracked": untracked,
        "status_porcelain": status_porcelain,
        "status_human": status_human,
        "log_all": log_all,
        "notes_worktree": notes_worktree,
        "todo_worktree": todo_worktree,
        "notes_index": notes_index,
        "todo_index": todo_index,
    }


def verify_state(state: dict, run_label: str):
    """Asserts that state satisfies all expected requirements."""
    # Assertion 1: Branch and Ref topology
    assert state["head_ref"] == state["main_ref"], f"[{run_label}] HEAD must point to refs/heads/main"
    assert state["main_ref"] == state["commit_c"], f"[{run_label}] main ref must point to Commit C"
    assert state["topic_ref"] == state["commit_b"], f"[{run_label}] topic ref must point to Commit B"
    assert state["c_parent"] == state["commit_b"], f"[{run_label}] Commit C parent must be Commit B"
    assert state["b_parent"] == state["commit_a"], f"[{run_label}] Commit B parent must be Commit A"

    # Assertion 2: Pre-reset state
    assert state["pre_staged"] == ["notes.txt", "todo.txt"], (
        f"[{run_label}] Pre-reset staged files must be notes.txt and todo.txt, got {state['pre_staged']}"
    )
    assert state["pre_unstaged"] == [], f"[{run_label}] Pre-reset unstaged must be empty"

    # Assertion 3: Post-reset staging status
    assert state["post_staged"] == ["todo.txt"], (
        f"[{run_label}] Staged files after reset must be exactly ['todo.txt'], got {state['post_staged']}"
    )
    assert state["post_unstaged"] == ["notes.txt"], (
        f"[{run_label}] Unstaged files after reset must be exactly ['notes.txt'], got {state['post_unstaged']}"
    )
    assert state["untracked"] == [], f"[{run_label}] There should be no untracked files"

    # Assertion 4: Working tree content preservation
    assert state["notes_worktree"] == "alpha\nbeta\ngamma\n", (
        f"[{run_label}] notes.txt worktree content mismatch: {state['notes_worktree']!r}"
    )
    assert state["todo_worktree"] == "one\ntwo\n", (
        f"[{run_label}] todo.txt worktree content mismatch: {state['todo_worktree']!r}"
    )

    # Assertion 5: Index (staged) content
    assert state["notes_index"] == "alpha\nbeta\n", (
        f"[{run_label}] notes.txt index content mismatch: {state['notes_index']!r}"
    )
    assert state["todo_index"] == "one\ntwo\n", (
        f"[{run_label}] todo.txt index content mismatch: {state['todo_index']!r}"
    )


def main():
    print("Starting verification of R12-T041...")

    with tempfile.TemporaryDirectory(prefix="gfr_test1_") as dir1,          tempfile.TemporaryDirectory(prefix="gfr_test2_") as dir2:

        print(f"Executing workflow in temporary repo 1: {dir1}")
        state1 = run_workflow_in_dir(dir1)
        verify_state(state1, "Repo 1")
        print("  Repo 1: All state assertions passed.")

        print(f"Executing workflow in temporary repo 2: {dir2}")
        state2 = run_workflow_in_dir(dir2)
        verify_state(state2, "Repo 2")
        print("  Repo 2: All state assertions passed.")

        # Assertion 6: Cross-directory consistency
        print("Checking cross-repository consistency...")
        assert state1["post_staged"] == state2["post_staged"], "Staged files differ across test runs"
        assert state1["post_unstaged"] == state2["post_unstaged"], "Unstaged files differ across test runs"
        assert state1["untracked"] == state2["untracked"], "Untracked files differ across test runs"
        assert state1["notes_worktree"] == state2["notes_worktree"], "notes.txt worktree differs across test runs"
        assert state1["todo_worktree"] == state2["todo_worktree"], "todo.txt worktree differs across test runs"
        assert state1["notes_index"] == state2["notes_index"], "notes.txt index differs across test runs"
        assert state1["todo_index"] == state2["todo_index"], "todo.txt index differs across test runs"
        assert state1["status_porcelain"] == state2["status_porcelain"], "Status porcelain output differs"
        print("  Cross-repository consistency verified.")

    print("\nSUCCESS: All state and reproducibility assertions passed successfully.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print("\nASSERTION FAILED: %s" % e, file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print("\nPROCESS ERROR: Command '%s' returned %d.\nStderr: %s" % (e.cmd, e.returncode, e.stderr), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print("\nUNEXPECTED ERROR: %s" % e, file=sys.stderr)
        sys.exit(1)
