#!/usr/bin/env python3
"""
Automated verification check for Task R12-T011
Item: README.md - "The rebase editing screen says 'noop'"

Verifies start-to-finish setup, assertions on file contents, refs, index state,
and git rebase -i producing 'noop'.
Runs in two independent temporary directories.
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

def run_git_test_iteration(iteration_num, log_records):
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
                log_records.append(f"Command failed (exit {res.returncode}): {res.stderr}")
                raise AssertionError(f"Command failed (exit {res.returncode}): {cmd}\nStderr: {res.stderr}")
            return res

        # 1. Initialize repository with main branch
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
        log_records.append(f"Commit C hash: {commit_c}")

        # 6. Switch to topic branch
        execute("git checkout topic")
        current_branch = execute("git rev-parse --abbrev-ref HEAD").stdout.strip()
        assert current_branch == "topic", f"Expected branch 'topic', got '{current_branch}'"

        # --- ASSERTION 1: File contents on branch topic ---
        with open(notes_path, "r", encoding="utf-8") as f:
            actual_notes = f.read()
        expected_notes = "alpha\nbeta\n"
        assert actual_notes == expected_notes, (
            f"Assertion 1 Failed: notes.txt content mismatch.\nExpected: {repr(expected_notes)}\nActual: {repr(actual_notes)}"
        )
        assert not os.path.exists(todo_path), "Assertion 1 Failed: todo.txt should not exist on branch topic"
        log_records.append("Assertion 1 Passed: Working tree files match expected state ('alpha\\nbeta\\n', todo.txt absent)")

        # --- ASSERTION 2: Refs and Ancestry ---
        topic_head = execute("git rev-parse HEAD").stdout.strip()
        main_head = execute("git rev-parse main").stdout.strip()
        assert topic_head == commit_b, f"Assertion 2 Failed: topic HEAD ({topic_head}) != Commit B ({commit_b})"
        assert main_head == commit_c, f"Assertion 2 Failed: main HEAD ({main_head}) != Commit C ({commit_c})"
        
        # Verify Commit B is ancestor of Commit C
        ancestor_check = execute(f"git merge-base --is-ancestor {commit_b} {commit_c}", check=False)
        assert ancestor_check.returncode == 0, "Assertion 2 Failed: Commit B must be ancestor of Commit C"
        log_records.append("Assertion 2 Passed: Refs correct; Commit B is ancestor of Commit C")

        # --- ASSERTION 3: Working tree and index cleanliness ---
        status_porcelain = execute("git status --porcelain").stdout.strip()
        assert status_porcelain == "", f"Assertion 3 Failed: Working tree/index not clean: {status_porcelain}"
        log_records.append("Assertion 3 Passed: Working tree and index are clean")

        # --- ASSERTION 4: Interactive Rebase produces 'noop' ---
        captured_todo = os.path.join(td, "todo_list.txt")
        # Use python script as sequence editor to capture the instruction sheet
        sequence_editor = f'python3 -c "import sys, shutil; shutil.copyfile(sys.argv[1], {repr(captured_todo)})"'
        rebase_env = {**env, "GIT_SEQUENCE_EDITOR": sequence_editor}
        
        rebase_res = subprocess.run(
            "git rebase -i main",
            cwd=td,
            env=rebase_env,
            shell=True,
            capture_output=True,
            text=True
        )
        assert rebase_res.returncode == 0, f"Assertion 4 Failed: git rebase -i main exited with {rebase_res.returncode}: {rebase_res.stderr}"
        
        with open(captured_todo, "r", encoding="utf-8") as f:
            raw_todo = f.read()
        
        todo_commands = [
            line.strip() for line in raw_todo.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        log_records.append(f"Captured todo commands: {todo_commands}")
        assert len(todo_commands) >= 1, "Assertion 4 Failed: No commands in rebase todo list"
        assert todo_commands[0] == "noop", f"Assertion 4 Failed: Expected 'noop', got '{todo_commands[0]}'"
        log_records.append("Assertion 4 Passed: Rebase instruction sheet contains 'noop' as expected")

        return {
            "iteration": iteration_num,
            "commit_a": commit_a,
            "commit_b": commit_b,
            "commit_c": commit_c,
            "notes_content": actual_notes,
            "todo_commands": todo_commands,
            "status_clean": (status_porcelain == ""),
            "rebase_exit_code": rebase_res.returncode
        }

def main():
    log_records = []
    log_records.append("Starting automated verification check for R12-T011")
    
    versions = get_tool_versions()
    log_records.append(f"Tool versions: {json.dumps(versions, indent=2)}")

    results = []
    try:
        # Run setup twice in separate temporary directories to ensure full reproducibility
        results.append(run_git_test_iteration(1, log_records))
        results.append(run_git_test_iteration(2, log_records))
        log_records.append("\nBoth iterations completed successfully with all assertions passing.")
        success = True
    except Exception as e:
        log_records.append(f"\nFAILED: {str(e)}")
        success = False
        raise
    finally:
        # Save evidence and tool versions in work/R12-T011/
        os.makedirs(SCRIPT_DIR, exist_ok=True)
        with open(os.path.join(SCRIPT_DIR, "tool_versions.txt"), "w", encoding="utf-8") as f:
            for k, v in versions.items():
                f.write(f"{k}: {v}\n")
        
        with open(os.path.join(SCRIPT_DIR, "evidence.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(log_records) + "\n")
            
        with open(os.path.join(SCRIPT_DIR, "check_summary.json"), "w", encoding="utf-8") as f:
            json.dump({
                "task": "R12-T011",
                "success": success,
                "tool_versions": versions,
                "iterations": results
            }, f, indent=2)

    print("All checks for R12-T011 passed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
