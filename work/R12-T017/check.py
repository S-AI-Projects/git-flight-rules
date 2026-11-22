#!/usr/bin/env python3
"""
Automated verification check for Task R12-T017
Item: README.md - "Final Step: Pushing your changed repo history"

Verifies:
- Setup with branch main, author Course Student <student@example.invalid>
- Commits A, B, and C; branch topic at Commit B; tag v1.0 created
- Reflog cleanup: git reflog expire --expire=now --all && git gc --prune=now --aggressive
- Violated precondition: running `git push origin --force --tags` without configuring remote `origin`
- Captures nonzero exit code (128) and diagnostic indicating missing origin
- Smallest correction: git remote add origin <url>
- Repaired execution: git push origin --force --tags succeeds (exit 0)
- Remote tags verified via git ls-remote
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
        log_records.append(f"Bare target remote URL: {bare_url}")

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

        # 6. Create tag v1.0 at Commit C
        execute("git tag v1.0")

        # 7. Execute reflog expiration and aggressive garbage collection
        execute("git reflog expire --expire=now --all && git gc --prune=now --aggressive")
        log_records.append("Executed: git reflog expire and git gc")

        # --- ASSERTION 1: Violated Precondition - Missing remote origin triggers non-zero exit ---
        res_bad = execute("git push origin --force --tags", check=False)
        assert res_bad.returncode != 0, f"Expected non-zero exit code for missing origin, got {res_bad.returncode}"
        assert "origin" in res_bad.stderr, f"Expected stderr to mention 'origin', got: {res_bad.stderr}"
        log_records.append(f"Assertion 1 Passed: git push failed as expected with code {res_bad.returncode}")

        # --- ASSERTION 2: Smallest correction - add remote origin ---
        execute(f"git remote add origin {bare_url}")
        configured_url = execute("git config remote.origin.url").stdout.strip()
        assert configured_url == bare_url, f"Remote origin URL mismatch: {configured_url}"
        log_records.append(f"Assertion 2 Passed: Remote origin configured with {bare_url}")

        # --- ASSERTION 3: Repaired case succeeds with exit code 0 ---
        res_good = execute("git push origin --force --tags")
        assert res_good.returncode == 0, f"Repaired push failed with code {res_good.returncode}"
        log_records.append("Assertion 3 Passed: Repaired git push origin --force --tags succeeded with exit code 0")

        # Verify tag reached the remote
        ls_remote_tags = execute("git ls-remote --tags origin").stdout.strip()
        assert "refs/tags/v1.0" in ls_remote_tags, "Tag v1.0 not found in remote repository"
        assert commit_c in ls_remote_tags, "Remote tag v1.0 does not point to Commit C"
        log_records.append("Assertion 4 Passed: Remote tag v1.0 verified pointing to Commit C")

        # Verify working tree and index are clean
        status_porcelain = execute("git status --porcelain").stdout.strip()
        assert status_porcelain == "", f"Working tree not clean: {status_porcelain}"

        return {
            "iteration": iteration_num,
            "commit_a": commit_a,
            "commit_b": commit_b,
            "commit_c": commit_c,
            "bad_exit_code": res_bad.returncode,
            "good_exit_code": res_good.returncode,
            "remote_tag_verified": True,
            "all_assertions_passed": True
        }

def main():
    log_records = []
    log_records.append("Starting automated verification check for R12-T017")

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
                "task": "R12-T017",
                "success": success,
                "tool_versions": versions,
                "iterations": results
            }, f, indent=2)

    print("All checks for R12-T017 passed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
