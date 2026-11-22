#!/usr/bin/env python3
"""
Automated verification check for Task R12-T013
Item: README.md - "I need to add staged changes to the previous commit"

Verifies:
- Setup with branch main, author Course Student <student@example.invalid>
- Commits A, B, and C; branch topic created at Commit B
- Demonstrates mistake: accidental amend using `git commit --amend -C HEAD`
- Identifies recovery point via `HEAD@{1}` in reflog
- Recovers original commit, tree, and files using `git reset --hard HEAD@{1}`
- Asserts recovered tree matches saved tree hash, file contents match, and branch refs are preserved
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
        todo_path = os.path.join(td, "todo.txt")
        with open(todo_path, "w", encoding="utf-8") as f:
            f.write("one\n")
        execute("git add todo.txt")
        execute('git commit -m "Commit C: add todo.txt"')
        commit_c = execute("git rev-parse HEAD").stdout.strip()
        tree_c = execute("git rev-parse HEAD^{tree}").stdout.strip()
        log_records.append(f"Original Commit C hash: {commit_c}")
        log_records.append(f"Original Tree C hash: {tree_c}")

        # 6. Simulate mistake: unwanted edit staged and amended into Commit C
        with open(notes_path, "a", encoding="utf-8") as f:
            f.write("unwanted edit\n")
        execute("git add notes.txt")
        execute("git commit --amend -C HEAD")
        commit_amended = execute("git rev-parse HEAD").stdout.strip()
        tree_amended = execute("git rev-parse HEAD^{tree}").stdout.strip()
        log_records.append(f"Amended Commit hash: {commit_amended}")
        log_records.append(f"Amended Tree hash: {tree_amended}")

        assert commit_amended != commit_c, "Amended commit should have different hash from Commit C"
        assert tree_amended != tree_c, "Amended tree should have different hash from Commit C"

        # 7. Identify recovery point in reflog
        recovery_ref = execute("git rev-parse HEAD@{1}").stdout.strip()
        assert recovery_ref == commit_c, f"HEAD@{{1}} ({recovery_ref}) must match original Commit C ({commit_c})"
        log_records.append(f"Recovery target HEAD@{{1}} confirmed: {recovery_ref}")

        # 8. Perform recovery: git reset --hard HEAD@{1}
        execute("git reset --hard HEAD@{1}")
        recovered_commit = execute("git rev-parse HEAD").stdout.strip()
        recovered_tree = execute("git rev-parse HEAD^{tree}").stdout.strip()
        log_records.append(f"Recovered Commit hash: {recovered_commit}")
        log_records.append(f"Recovered Tree hash: {recovered_tree}")

        # --- ASSERTION 1: Recovered tree and commit match original pre-amend state ---
        assert recovered_commit == commit_c, (
            f"Assertion 1 Failed: Recovered commit ({recovered_commit}) != Commit C ({commit_c})"
        )
        assert recovered_tree == tree_c, (
            f"Assertion 1 Failed: Recovered tree ({recovered_tree}) != Tree C ({tree_c})"
        )
        log_records.append("Assertion 1 Passed: Recovered commit and tree hashes match original Commit C exactly")

        # --- ASSERTION 2: File contents match expected pre-amend state ---
        with open(notes_path, "r", encoding="utf-8") as f:
            notes_content = f.read()
        with open(todo_path, "r", encoding="utf-8") as f:
            todo_content = f.read()
        assert notes_content == "alpha\nbeta\n", f"Assertion 2 Failed: notes.txt mismatch: {repr(notes_content)}"
        assert todo_content == "one\n", f"Assertion 2 Failed: todo.txt mismatch: {repr(todo_content)}"
        log_records.append("Assertion 2 Passed: Working-tree file contents restored to exact expected state")

        # --- ASSERTION 3: Branch refs and ancestry intact ---
        main_ref = execute("git rev-parse refs/heads/main").stdout.strip()
        topic_ref = execute("git rev-parse refs/heads/topic").stdout.strip()
        assert main_ref == commit_c, f"Assertion 3 Failed: main ref ({main_ref}) != Commit C ({commit_c})"
        assert topic_ref == commit_b, f"Assertion 3 Failed: topic ref ({topic_ref}) != Commit B ({commit_b})"
        is_ancestor = execute(f"git merge-base --is-ancestor {commit_b} {commit_c}", check=False).returncode
        assert is_ancestor == 0, "Assertion 3 Failed: Commit B must be ancestor of Commit C"
        log_records.append("Assertion 3 Passed: Branch refs (main, topic) and ancestry are fully intact")

        # --- ASSERTION 4: Clean index and working tree ---
        status_porcelain = execute("git status --porcelain").stdout.strip()
        assert status_porcelain == "", f"Assertion 4 Failed: Working tree/index not clean: {status_porcelain}"
        log_records.append("Assertion 4 Passed: Working tree and index are clean")

        return {
            "iteration": iteration_num,
            "commit_a": commit_a,
            "commit_b": commit_b,
            "commit_c": commit_c,
            "commit_amended": commit_amended,
            "recovered_commit": recovered_commit,
            "recovered_tree": recovered_tree,
            "all_assertions_passed": True
        }

def main():
    log_records = []
    log_records.append("Starting automated verification check for R12-T013")

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
                "task": "R12-T013",
                "success": success,
                "tool_versions": versions,
                "iterations": results
            }, f, indent=2)

    print("All checks for R12-T013 passed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
