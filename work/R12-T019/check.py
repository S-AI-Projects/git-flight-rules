#!/usr/bin/env python3
"""
Automated verification check for Task R12-T019
Item: README.md - "I want to delete or remove my last commit"

Verifies:
- Setup with branch main, author Course Student <student@example.invalid>
- Commits A, B, and C; branch topic at Commit B
- Local bare repository for remote tracking via file:// URL
- Verification of prerequisites:
    1. Current branch is main
    2. Non-root commit (HEAD^ exists)
    3. Working tree state clean before reset
    4. Remote origin configured and in-sync
- Operation 1: git reset --soft HEAD^ keeps changes staged in index
- Operation 2: git reset HEAD^ --hard discards changes and resets working tree
- Operation 3: git push --force-with-lease origin main updates remote ref safely
- Asserts unrelated ref (refs/heads/topic) remains fixed
- Per-test config is purely local; user's global Git config is untouched
- Runs twice in separate temporary directories
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

        # Create a local bare repository for the remote
        bare_remote_dir = os.path.join(td, "remote-target.git")
        subprocess.run(["git", "init", "--bare", bare_remote_dir], check=True, capture_output=True)
        bare_url = f"file://{bare_remote_dir}"
        log_records.append(f"Bare remote URL: {bare_url}")

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

        # 1. Initialize local repository with main branch (local config only)
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

        # 3. Commit B: appends "beta\n" to notes.txt
        with open(notes_path, "a", encoding="utf-8") as f:
            f.write("beta\n")
        execute("git add notes.txt")
        execute('git commit -m "Commit B: append to notes.txt"')
        commit_b = execute("git rev-parse HEAD").stdout.strip()

        # 4. Create branch topic at Commit B
        execute("git branch topic")

        # 5. Commit C: adds todo.txt with "one\n" on main
        todo_path = os.path.join(worktree_dir, "todo.txt")
        with open(todo_path, "w", encoding="utf-8") as f:
            f.write("one\n")
        execute("git add todo.txt")
        execute('git commit -m "Commit C: add todo.txt"')
        commit_c = execute("git rev-parse HEAD").stdout.strip()

        # 6. Configure remote origin and push main
        execute(f"git remote add origin {bare_url}")
        execute("git push -u origin main")
        remote_main_before = execute("git rev-parse refs/remotes/origin/main").stdout.strip()
        assert remote_main_before == commit_c, "Remote main ref must equal Commit C"

        # --- ASSERTION 1: Verify Prerequisites before undoing commit ---
        current_branch = execute("git rev-parse --abbrev-ref HEAD").stdout.strip()
        assert current_branch == "main", f"Expected current branch 'main', got {current_branch}"

        parent_commit = execute("git rev-parse --verify HEAD^").stdout.strip()
        assert parent_commit == commit_b, f"Expected parent commit to be Commit B ({commit_b}), got {parent_commit}"

        status_before = execute("git status --porcelain").stdout.strip()
        assert status_before == "", f"Working tree not clean: {status_before}"
        log_records.append("Assertion 1 Passed: All prerequisites verified (branch, parent commit, clean status, remote)")

        # --- ASSERTION 2: git reset --soft HEAD^ keeps changes staged in index ---
        execute("git reset --soft HEAD^")
        head_soft = execute("git rev-parse HEAD").stdout.strip()
        assert head_soft == commit_b, f"HEAD after soft reset ({head_soft}) != Commit B ({commit_b})"
        status_soft = execute("git status --porcelain").stdout.strip()
        assert "A  todo.txt" in status_soft, f"Expected todo.txt staged after soft reset, got: {status_soft}"
        log_records.append("Assertion 2 Passed: git reset --soft HEAD^ restored HEAD to Commit B with todo.txt staged")

        # Re-commit C to test hard reset and force-push-with-lease
        execute('git commit -m "Commit C: add todo.txt"')
        commit_c2 = execute("git rev-parse HEAD").stdout.strip()

        # --- ASSERTION 3: git reset HEAD^ --hard discards changes cleanly ---
        execute("git reset HEAD^ --hard")
        head_hard = execute("git rev-parse HEAD").stdout.strip()
        assert head_hard == commit_b, f"HEAD after hard reset ({head_hard}) != Commit B ({commit_b})"
        assert not os.path.exists(todo_path), "todo.txt should be deleted from working tree after hard reset"
        status_hard = execute("git status --porcelain").stdout.strip()
        assert status_hard == "", f"Working tree not clean after hard reset: {status_hard}"
        log_records.append("Assertion 3 Passed: git reset HEAD^ --hard restored HEAD to Commit B and deleted todo.txt")

        # --- ASSERTION 4: git push --force-with-lease origin main updates remote safely ---
        execute("git push --force-with-lease origin main")
        remote_main_after = execute("git rev-parse refs/remotes/origin/main").stdout.strip()
        assert remote_main_after == commit_b, f"Remote main ref after force push ({remote_main_after}) != Commit B ({commit_b})"

        # Verify topic branch is completely untouched
        topic_head = execute("git rev-parse refs/heads/topic").stdout.strip()
        assert topic_head == commit_b, f"Topic branch ref changed unexpectedly: {topic_head}"
        log_records.append("Assertion 4 Passed: Remote main ref updated to Commit B; topic ref remains fixed")

        return {
            "iteration": iteration_num,
            "commit_a": commit_a,
            "commit_b": commit_b,
            "commit_c": commit_c,
            "head_soft": head_soft,
            "head_hard": head_hard,
            "remote_main_after": remote_main_after,
            "topic_head": topic_head,
            "all_assertions_passed": True
        }

def main():
    log_records = []
    log_records.append("Starting automated verification check for R12-T019")

    versions = get_tool_versions()
    log_records.append(f"Tool versions: {json.dumps(versions, indent=2)}")

    results = []
    try:
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
                "task": "R12-T019",
                "success": success,
                "tool_versions": versions,
                "iterations": results
            }, f, indent=2)

    print("All checks for R12-T019 passed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
