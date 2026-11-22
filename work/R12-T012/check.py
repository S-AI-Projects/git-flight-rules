#!/usr/bin/env python3
"""
Automated verification check for Task R12-T012
Item: README.md - "I set the wrong remote repository"

Verifies:
- Repository setup with branch main, author Course Student <student@example.invalid>
- Three commits (A, B, C) and branch topic at B
- Remote origin updated via: git remote set-url origin [url of the actual repo]
- Verification that remote URL changes while HEAD, branch refs, commit ancestry,
  staged files (index), and working tree remain completely unchanged.
- Runs setup twice in separate temporary directories.
"""

import os
import sys
import tempfile
import subprocess
import shutil
import json
import platform

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_tool_versions():
    git_ver = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    python_ver = f"Python {platform.python_version()}"
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    return {
        "git": git_ver,
        "python": python_ver,
        "os": os_info
    }

def run_test_iteration(iteration_num, log_records):
    log_records.append(f"\n=== Running Test Iteration {iteration_num} ===")

    with tempfile.TemporaryDirectory() as td:
        log_records.append(f"Temporary root directory: {td}")
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Course Student",
            "GIT_AUTHOR_EMAIL": "student@example.invalid",
            "GIT_COMMITTER_NAME": "Course Student",
            "GIT_COMMITTER_EMAIL": "student@example.invalid",
        }

        # Create two bare remote repositories to simulate wrong and actual remotes
        wrong_remote_dir = os.path.join(td, "wrong-repo.git")
        actual_remote_dir = os.path.join(td, "actual-repo.git")
        subprocess.run(["git", "init", "--bare", wrong_remote_dir], check=True, capture_output=True)
        subprocess.run(["git", "init", "--bare", actual_remote_dir], check=True, capture_output=True)

        wrong_url = f"file://{wrong_remote_dir}"
        actual_url = f"file://{actual_remote_dir}"
        log_records.append(f"Initial wrong remote URL: {wrong_url}")
        log_records.append(f"Target actual remote URL: {actual_url}")

        worktree_dir = os.path.join(td, "worktree")

        def execute(cmd, check=True):
            log_records.append(f"Execute: {cmd}")
            res = subprocess.run(
                cmd,
                cwd=worktree_dir,
                env=env,
                shell=True,
                capture_output=True,
                text=True
            )
            if check and res.returncode != 0:
                log_records.append(f"Command failed ({res.returncode}): {res.stderr}")
                raise AssertionError(f"Command failed ({res.returncode}): {cmd}\nStderr: {res.stderr}")
            return res

        # 1. Initialize local repository with main branch
        subprocess.run(["git", "init", "-b", "main", worktree_dir], check=True, capture_output=True)
        execute('git config user.name "Course Student"')
        execute('git config user.email "student@example.invalid"')

        # 2. Commit A: creates notes.txt with "alpha\n"
        notes_path = os.path.join(worktree_dir, "notes.txt")
        with open(notes_path, "w", encoding="utf-8") as f:
            f.write("alpha\n")
        execute("git add notes.txt")
        execute('git commit -m "Commit A: create notes.txt"')
        commit_a = execute("git rev-parse HEAD").stdout.strip()
        log_records.append(f"Commit A hash: {commit_a}")

        # 3. Commit B: appends "beta\n" to notes.txt
        with open(notes_path, "a", encoding="utf-8") as f:
            f.write("beta\n")
        execute("git add notes.txt")
        execute('git commit -m "Commit B: append to notes.txt"')
        commit_b = execute("git rev-parse HEAD").stdout.strip()
        log_records.append(f"Commit B hash: {commit_b}")

        # 4. Create branch topic at Commit B
        execute("git branch topic")

        # 5. Commit C: adds todo.txt with "one\n" on main
        todo_path = os.path.join(worktree_dir, "todo.txt")
        with open(todo_path, "w", encoding="utf-8") as f:
            f.write("one\n")
        execute("git add todo.txt")
        execute('git commit -m "Commit C: add todo.txt"')
        commit_c = execute("git rev-parse HEAD").stdout.strip()
        log_records.append(f"Commit C hash: {commit_c}")

        # 6. Configure initial wrong remote
        execute(f"git remote add origin {wrong_url}")

        # Capture pre-transition state
        before_url = execute("git config remote.origin.url").stdout.strip()
        before_head = execute("git rev-parse HEAD").stdout.strip()
        before_main = execute("git rev-parse refs/heads/main").stdout.strip()
        before_topic = execute("git rev-parse refs/heads/topic").stdout.strip()
        before_status = execute("git status --porcelain").stdout.strip()
        with open(notes_path, "r", encoding="utf-8") as f:
            before_notes = f.read()
        with open(todo_path, "r", encoding="utf-8") as f:
            before_todo = f.read()
        before_commit_count = int(execute("git rev-list --count HEAD").stdout.strip())

        assert before_url == wrong_url, f"Expected initial URL {wrong_url}, got {before_url}"
        assert before_head == commit_c, f"Expected HEAD {commit_c}, got {before_head}"
        assert before_main == commit_c, f"Expected main {commit_c}, got {before_main}"
        assert before_topic == commit_b, f"Expected topic {commit_b}, got {before_topic}"
        assert before_status == "", f"Expected clean status before set-url, got: {before_status}"

        # 7. Execute named command: git remote set-url origin [url of the actual repo]
        execute(f"git remote set-url origin {actual_url}")
        log_records.append(f"Executed: git remote set-url origin {actual_url}")

        # Capture post-transition state
        after_url = execute("git config remote.origin.url").stdout.strip()
        after_head = execute("git rev-parse HEAD").stdout.strip()
        after_main = execute("git rev-parse refs/heads/main").stdout.strip()
        after_topic = execute("git rev-parse refs/heads/topic").stdout.strip()
        after_status = execute("git status --porcelain").stdout.strip()
        with open(notes_path, "r", encoding="utf-8") as f:
            after_notes = f.read()
        with open(todo_path, "r", encoding="utf-8") as f:
            after_todo = f.read()
        after_commit_count = int(execute("git rev-list --count HEAD").stdout.strip())

        # --- ASSERTION 1: Remote configuration updated ---
        assert after_url == actual_url, (
            f"Assertion 1 Failed: remote.origin.url mismatch.\nExpected: {actual_url}\nActual: {after_url}"
        )
        log_records.append(f"Assertion 1 Passed: remote.origin.url successfully updated to '{after_url}'")

        # --- ASSERTION 2: HEAD, Branch Refs, and Commit Ancestry Unchanged ---
        assert after_head == before_head == commit_c, (
            f"Assertion 2 Failed: HEAD changed.\nBefore: {before_head}\nAfter: {after_head}"
        )
        assert after_main == before_main == commit_c, (
            f"Assertion 2 Failed: refs/heads/main changed.\nBefore: {before_main}\nAfter: {after_main}"
        )
        assert after_topic == before_topic == commit_b, (
            f"Assertion 2 Failed: refs/heads/topic changed.\nBefore: {before_topic}\nAfter: {after_topic}"
        )
        assert after_commit_count == before_commit_count == 3, (
            f"Assertion 2 Failed: Commit count changed.\nBefore: {before_commit_count}\nAfter: {after_commit_count}"
        )
        is_ancestor = execute(f"git merge-base --is-ancestor {commit_b} {commit_c}", check=False).returncode
        assert is_ancestor == 0, "Assertion 2 Failed: Commit B must remain ancestor of Commit C"
        log_records.append("Assertion 2 Passed: HEAD, branch refs, and commit ancestry are identical")

        # --- ASSERTION 3: Index and Working Tree Unchanged ---
        assert after_status == "", f"Assertion 3 Failed: Working tree/index dirty after set-url: {after_status}"
        assert after_notes == before_notes == "alpha\nbeta\n", (
            f"Assertion 3 Failed: notes.txt changed: {repr(after_notes)}"
        )
        assert after_todo == before_todo == "one\n", (
            f"Assertion 3 Failed: todo.txt changed: {repr(after_todo)}"
        )
        log_records.append("Assertion 3 Passed: Index and working tree files are completely unchanged")

        return {
            "iteration": iteration_num,
            "commit_a": commit_a,
            "commit_b": commit_b,
            "commit_c": commit_c,
            "before_url": before_url,
            "after_url": after_url,
            "status_clean": (after_status == ""),
            "all_assertions_passed": True
        }

def main():
    log_records = []
    log_records.append("Starting automated verification check for R12-T012")

    versions = get_tool_versions()
    log_records.append(f"Tool versions: {json.dumps(versions, indent=2)}")

    results = []
    try:
        # Run twice in separate temporary directories
        results.append(run_test_iteration(1, log_records))
        results.append(run_test_iteration(2, log_records))
        log_records.append("\nBoth iterations completed successfully with all assertions passing.")
        success = True
    except Exception as e:
        log_records.append(f"\nFAILED: {str(e)}")
        success = False
        raise
    finally:
        os.makedirs(SCRIPT_DIR, exist_ok=True)
        with open(os.path.join(SCRIPT_DIR, "tool_versions.txt"), "w", encoding="utf-8") as f:
            for k, v in versions.items():
                f.write(f"{k}: {v}\n")

        with open(os.path.join(SCRIPT_DIR, "evidence.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(log_records) + "\n")

        with open(os.path.join(SCRIPT_DIR, "check_summary.json"), "w", encoding="utf-8") as f:
            json.dump({
                "task": "R12-T012",
                "success": success,
                "tool_versions": versions,
                "iterations": results
            }, f, indent=2)

    print("All checks for R12-T012 passed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
