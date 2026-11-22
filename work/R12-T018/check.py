#!/usr/bin/env python3
"""
Automated verification check for Task R12-T018
Item: README.md - "I made changes on the wrong branch"

Verifies:
- Setup with branch main, author Course Student <student@example.invalid>
- Commits A, B, and C; branch topic created at Commit B
- Uncommitted change made on main (wrong branch)
- git stash clears working tree on main
- git checkout topic switches context to target branch
- Decisive command git stash apply transfers uncommitted change to topic
- Negative test: deliberately omitting git stash apply triggers assertion failure
- Runs twice in separate temporary directories, propagating child failures and cleaning temp dirs
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

def run_test_iteration(iteration_num, log_records, omit_decisive_command=False):
    prefix = f"Iteration {iteration_num}" if not omit_decisive_command else "Negative Test (Omission)"
    log_records.append(f"\n=== Running {prefix} ===")

    with tempfile.TemporaryDirectory() as td:
        log_records.append(f"Temporary directory: {td}")
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Course Student",
            "GIT_AUTHOR_EMAIL": "student@example.invalid",
            "GIT_COMMITTER_NAME": "Course Student",
            "GIT_COMMITTER_EMAIL": "student@example.invalid",
        }

        def execute(cmd, check=True):
            log_records.append(f"Execute: {cmd}")
            res = subprocess.run(
                cmd,
                cwd=td,
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
        execute("git init -b main")
        execute('git config user.name "Course Student"')
        execute('git config user.email "student@example.invalid"')

        # 2. Commit A: creates notes.txt with "alpha\n"
        notes_path = os.path.join(td, "notes.txt")
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
        todo_path = os.path.join(td, "todo.txt")
        with open(todo_path, "w", encoding="utf-8") as f:
            f.write("one\n")
        execute("git add todo.txt")
        execute('git commit -m "Commit C: add todo.txt"')
        commit_c = execute("git rev-parse HEAD").stdout.strip()

        # 6. Simulate uncommitted edit on main that belongs on topic
        with open(notes_path, "a", encoding="utf-8") as f:
            f.write("gamma\n")

        status_before_stash = execute("git status --porcelain").stdout.strip()
        assert "notes.txt" in status_before_stash, "Uncommitted edit should be present on main"

        # 7. Step 1: git stash on wrong_branch (main)
        execute("git stash")

        # --- ASSERTION 1: Stash cleans wrong_branch working tree ---
        status_after_stash = execute("git status --porcelain").stdout.strip()
        assert status_after_stash == "", f"Assertion 1 Failed: main working tree not clean after stash: {status_after_stash}"
        log_records.append("Assertion 1 Passed: git stash restored wrong_branch (main) to clean state")

        # 8. Step 2: git checkout correct_branch (topic)
        execute("git checkout topic")
        topic_head = execute("git rev-parse HEAD").stdout.strip()
        assert topic_head == commit_b, f"Expected topic HEAD to be Commit B ({commit_b}), got {topic_head}"
        log_records.append("Assertion 2 Passed: Successfully switched to correct_branch (topic) at Commit B")

        # 9. Step 3: git stash apply on correct_branch (topic)
        if not omit_decisive_command:
            execute("git stash apply")
            log_records.append("Executed decisive command: git stash apply")

        # 10. Verify state on topic
        with open(notes_path, "r", encoding="utf-8") as f:
            notes_content = f.read()

        if omit_decisive_command:
            if "gamma\n" not in notes_content:
                raise AssertionError("Decisive command omitted: uncommitted edit 'gamma\\n' missing on topic")
        else:
            # --- ASSERTION 3: Uncommitted edit transferred to correct_branch ---
            assert notes_content == "alpha\nbeta\ngamma\n", (
                f"Assertion 3 Failed: notes.txt on topic does not contain uncommitted edits: {repr(notes_content)}"
            )
            assert not os.path.exists(todo_path), "todo.txt from main should not exist on topic"
            status_topic = execute("git status --porcelain").stdout.strip()
            assert "notes.txt" in status_topic, f"Expected modified notes.txt in topic status: {status_topic}"
            log_records.append("Assertion 3 Passed: Uncommitted edits cleanly transferred to correct_branch (topic)")

        return {
            "iteration": iteration_num,
            "omit_decisive_command": omit_decisive_command,
            "commit_a": commit_a,
            "commit_b": commit_b,
            "commit_c": commit_c,
            "notes_content": notes_content,
            "status_clean_on_stash": (status_after_stash == ""),
            "all_assertions_passed": True
        }

def main():
    log_records = []
    log_records.append("Starting automated verification check for R12-T018")

    versions = get_tool_versions()
    log_records.append(f"Tool versions: {json.dumps(versions, indent=2)}")

    results = []
    try:
        # Run standard workflow twice in separate temporary directories
        results.append(run_test_iteration(1, log_records, omit_decisive_command=False))
        results.append(run_test_iteration(2, log_records, omit_decisive_command=False))
        log_records.append("\nBoth standard iterations completed successfully with all assertions passing.")

        # Run negative test: verify test fails when decisive command is omitted
        log_records.append("\nTesting negative case (omitting decisive command 'git stash apply'):")
        omission_failed_as_expected = False
        try:
            run_test_iteration("omission-check", log_records, omit_decisive_command=True)
        except AssertionError as e:
            omission_failed_as_expected = True
            log_records.append(f"Negative test passed: caught expected failure when decisive command omitted: {e}")

        assert omission_failed_as_expected, "Test must fail when the guide's decisive command is omitted!"
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
                "task": "R12-T018",
                "success": success,
                "tool_versions": versions,
                "iterations": results,
                "negative_test_omission_verified": omission_failed_as_expected
            }, f, indent=2)

    print("All checks for R12-T018 passed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
