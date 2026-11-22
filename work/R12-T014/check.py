#!/usr/bin/env python3
"""
Automated verification check for Task R12-T014
Item: README.md - "I want to remove a file from the previous commit"

Verifies:
- Repository setup with branch main, author Course Student <student@example.invalid>
- Commits A, B, and C; branch topic created at Commit B
- Local bare repository used as remote via file:// URL (no public remote or personal branch)
- Running named commands on branch topic:
    git checkout HEAD^ notes.txt
    git add notes.txt
    git commit --amend --no-edit --allow-empty
- Asserts that intended ref (refs/heads/topic) changed while unrelated refs
  (refs/heads/main, refs/remotes/origin/main) remained fixed.
- Asserts working tree file contents and clean index state.
- Runs twice across separate temporary directories.
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

        # Create a local bare repository for remote tracking (no public remote)
        remote_bare_dir = os.path.join(td, "remote-repo.git")
        subprocess.run(["git", "init", "--bare", remote_bare_dir], check=True, capture_output=True)
        remote_url = f"file://{remote_bare_dir}"
        log_records.append(f"Local bare remote URL: {remote_url}")

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

        # 6. Push main to local bare remote
        execute(f"git remote add origin {remote_url}")
        execute("git push -u origin main")
        remote_main_before = execute("git rev-parse refs/remotes/origin/main").stdout.strip()
        assert remote_main_before == commit_c, "Remote main ref must match Commit C"

        # 7. Switch to topic branch
        execute("git checkout topic")
        topic_before = execute("git rev-parse refs/heads/topic").stdout.strip()
        main_before = execute("git rev-parse refs/heads/main").stdout.strip()
        log_records.append(f"Before amend - topic HEAD: {topic_before}, main HEAD: {main_before}")

        assert topic_before == commit_b, "topic branch should initially point to Commit B"
        assert main_before == commit_c, "main branch should point to Commit C"

        # 8. Execute the named guide commands on topic
        execute("git checkout HEAD^ notes.txt")
        execute("git add notes.txt")
        execute("git commit --amend --no-edit --allow-empty")

        topic_after = execute("git rev-parse refs/heads/topic").stdout.strip()
        main_after = execute("git rev-parse refs/heads/main").stdout.strip()
        remote_main_after = execute("git rev-parse refs/remotes/origin/main").stdout.strip()
        log_records.append(f"After amend - topic HEAD: {topic_after}, main HEAD: {main_after}, origin/main: {remote_main_after}")

        # --- ASSERTION 1: Intended ref (refs/heads/topic) changed ---
        assert topic_after != topic_before, (
            f"Assertion 1 Failed: Intended ref topic did not change ({topic_before})"
        )
        log_records.append("Assertion 1 Passed: Intended ref (refs/heads/topic) successfully changed to new amended commit")

        # --- ASSERTION 2: Unrelated refs (local main and remote origin/main) stayed fixed ---
        assert main_after == main_before == commit_c, (
            f"Assertion 2 Failed: Unrelated ref main changed from {main_before} to {main_after}"
        )
        assert remote_main_after == remote_main_before == commit_c, (
            f"Assertion 2 Failed: Remote ref origin/main changed from {remote_main_before} to {remote_main_after}"
        )
        log_records.append("Assertion 2 Passed: Unrelated refs (refs/heads/main and refs/remotes/origin/main) stayed fixed")

        # --- ASSERTION 3: Working-tree file contents reflect removal of changes ---
        with open(notes_path, "r", encoding="utf-8") as f:
            notes_content = f.read()
        assert notes_content == "alpha\n", (
            f"Assertion 3 Failed: notes.txt did not revert to Commit A state: {repr(notes_content)}"
        )
        assert not os.path.exists(todo_path), "Assertion 3 Failed: todo.txt should not exist on branch topic"
        log_records.append("Assertion 3 Passed: notes.txt content successfully reverted to 'alpha\\n'")

        # --- ASSERTION 4: Clean index and working tree ---
        status_porcelain = execute("git status --porcelain").stdout.strip()
        assert status_porcelain == "", f"Assertion 4 Failed: Working tree/index dirty: {status_porcelain}"
        log_records.append("Assertion 4 Passed: Working tree and index are clean")

        return {
            "iteration": iteration_num,
            "commit_a": commit_a,
            "commit_b": commit_b,
            "commit_c": commit_c,
            "topic_before": topic_before,
            "topic_after": topic_after,
            "main_before": main_before,
            "main_after": main_after,
            "remote_main": remote_main_after,
            "all_assertions_passed": True
        }

def main():
    log_records = []
    log_records.append("Starting automated verification check for R12-T014")

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
                "task": "R12-T014",
                "success": success,
                "tool_versions": versions,
                "iterations": results
            }, f, indent=2)

    print("All checks for R12-T014 passed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
