#!/usr/bin/env python3
"""
Automated verification script for Git Flight Rules task R12-T046.

Compares two workflows to split a branch:
1. Guide method: checkout -b new_branch -> checkout original -> reset --hard <split_sha>
2. Direct method: checkout -b branch_early <split_sha>

Verifies observable differences in branch refs, ORIG_HEAD, and active HEAD.
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


def setup_base_fixture(repo_dir: str, env: dict) -> dict:
    """Sets up standard coursework commits A, B (topic), C, plus D on main."""
    run_git(["git", "init", "-b", "main"], cwd=repo_dir, env=env)
    run_git(["git", "config", "user.name", "Course Student"], cwd=repo_dir, env=env)
    run_git(["git", "config", "user.email", "student@example.invalid"], cwd=repo_dir, env=env)

    # Commit A
    notes_path = os.path.join(repo_dir, "notes.txt")
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write("alpha\n")
    run_git(["git", "add", "notes.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit A: create notes.txt"], cwd=repo_dir, env=env)
    commit_a = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()

    # Commit B & topic branch
    with open(notes_path, "a", encoding="utf-8") as f:
        f.write("beta\n")
    run_git(["git", "add", "notes.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit B: append beta to notes.txt"], cwd=repo_dir, env=env)
    commit_b = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()
    run_git(["git", "branch", "topic"], cwd=repo_dir, env=env)

    # Commit C
    todo_path = os.path.join(repo_dir, "todo.txt")
    with open(todo_path, "w", encoding="utf-8") as f:
        f.write("one\n")
    run_git(["git", "add", "todo.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit C: create todo.txt"], cwd=repo_dir, env=env)

    # Commit D: further change on main
    with open(notes_path, "a", encoding="utf-8") as f:
        f.write("gamma\n")
    run_git(["git", "add", "notes.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit D: append gamma to notes.txt"], cwd=repo_dir, env=env)
    commit_d = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).strip()

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_d": commit_d,
    }


def run_workflow_guide(repo_dir: str) -> dict:
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    fix = setup_base_fixture(repo_dir, env)

    # Guide method:
    # (main)$ git checkout -b new_branch
    # (new_branch)$ git checkout main
    # (main)$ git reset --hard <commit_b>
    run_git(["git", "checkout", "-b", "new_branch"], cwd=repo_dir, env=env)
    run_git(["git", "checkout", "main"], cwd=repo_dir, env=env)
    run_git(["git", "reset", "--hard", fix["commit_b"]], cwd=repo_dir, env=env)

    main_ref = run_git(["git", "rev-parse", "refs/heads/main"], cwd=repo_dir, env=env).strip()
    new_branch_ref = run_git(["git", "rev-parse", "refs/heads/new_branch"], cwd=repo_dir, env=env).strip()
    orig_head = run_git(["git", "rev-parse", "ORIG_HEAD"], cwd=repo_dir, env=env).strip()
    current_branch = run_git(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo_dir, env=env).strip()

    return {
        **fix,
        "main_ref": main_ref,
        "new_branch_ref": new_branch_ref,
        "orig_head": orig_head,
        "current_branch": current_branch,
    }


def run_workflow_direct(repo_dir: str) -> dict:
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    fix = setup_base_fixture(repo_dir, env)

    # Direct method:
    # (main)$ git checkout -b branch_early <commit_b>
    run_git(["git", "checkout", "-b", "branch_early", fix["commit_b"]], cwd=repo_dir, env=env)

    main_ref = run_git(["git", "rev-parse", "refs/heads/main"], cwd=repo_dir, env=env).strip()
    branch_early_ref = run_git(["git", "rev-parse", "refs/heads/branch_early"], cwd=repo_dir, env=env).strip()
    orig_head_check = subprocess.run(["git", "rev-parse", "--verify", "ORIG_HEAD"], cwd=repo_dir, env=env, capture_output=True)
    orig_head = orig_head_check.stdout.decode().strip() if orig_head_check.returncode == 0 else None
    current_branch = run_git(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo_dir, env=env).strip()

    return {
        **fix,
        "main_ref": main_ref,
        "branch_early_ref": branch_early_ref,
        "orig_head": orig_head,
        "current_branch": current_branch,
    }


def main():
    print("Starting verification of R12-T046...")
    with tempfile.TemporaryDirectory(prefix="gfr_t046_guide_") as dir1, tempfile.TemporaryDirectory(prefix="gfr_t046_direct_") as dir2:
        print(f"Executing Guide workflow in: {dir1}")
        res_guide = run_workflow_guide(dir1)

        print(f"Executing Direct workflow in: {dir2}")
        res_direct = run_workflow_direct(dir2)

        # Assertion 1: Guide rewinds original branch (main) in-place to Commit B
        assert res_guide["main_ref"] == res_guide["commit_b"], "Guide method must rewind main to Commit B"
        assert res_guide["new_branch_ref"] == res_guide["commit_d"], "Guide method new_branch keeps Commit D"
        assert res_guide["current_branch"] == "main", "Guide method ends on main"
        assert res_guide["orig_head"] == res_guide["commit_d"], "Guide method sets ORIG_HEAD to pre-reset Commit D"
        print("  Guide assertions passed.")

        # Assertion 2: Direct method keeps original branch (main) untouched at Commit D
        assert res_direct["main_ref"] == res_direct["commit_d"], "Direct method leaves main untouched at Commit D"
        assert res_direct["branch_early_ref"] == res_direct["commit_b"], "Direct method branch_early points to Commit B"
        assert res_direct["current_branch"] == "branch_early", "Direct method ends on branch_early"
        assert res_direct["orig_head"] != res_direct["commit_d"], "Direct method does not rewrite ORIG_HEAD via reset"
        print("  Direct assertions passed.")

        # Assertion 3: Comparison demonstration
        assert res_guide["main_ref"] != res_direct["main_ref"], "Observable difference: main is rewound in guide vs untouched in direct"
        print("  Comparison differences verified.")

    print("\nSUCCESS: All command comparison assertions passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
