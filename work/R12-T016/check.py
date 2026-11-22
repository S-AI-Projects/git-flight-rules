#!/usr/bin/env python3
"""
Automated verification check for Task R12-T016
Item: README.md - "Exporting a repository as a Zip file"

Verifies:
- Setup with branch main, author Course Student <student@example.invalid>
- Commits A, B, and C; branch topic at Commit B
- Comparison between:
    1. git archive --format zip --output ... main (root-level entries)
    2. git archive --format zip --prefix=release/ --output ... main (--prefix flag)
    3. git archive --format zip --output ... topic (branch tree comparison)
- Asserts observable differences in zip file entry structure and tree contents
- Asserts repository state (HEAD, refs, index, working tree) remains completely unchanged
- Runs twice in separate temporary directories
"""

import os
import sys
import tempfile
import subprocess
import shutil
import json
import zipfile
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

        worktree_dir = os.path.join(td, "worktree")
        archives_dir = os.path.join(td, "archives")
        os.makedirs(archives_dir, exist_ok=True)

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
        tree_b = execute("git rev-parse HEAD^{tree}").stdout.strip()
        log_records.append(f"Commit B hash: {commit_b}, Tree B: {tree_b}")

        # 4. Create branch topic at Commit B
        execute("git branch topic")

        # 5. Commit C: adds todo.txt with "one\n" on main
        todo_path = os.path.join(worktree_dir, "todo.txt")
        with open(todo_path, "w", encoding="utf-8") as f:
            f.write("one\n")
        execute("git add todo.txt")
        execute('git commit -m "Commit C: add todo.txt"')
        commit_c = execute("git rev-parse HEAD").stdout.strip()
        tree_c = execute("git rev-parse HEAD^{tree}").stdout.strip()
        log_records.append(f"Commit C hash: {commit_c}, Tree C: {tree_c}")

        # Record pre-archive state
        main_head_before = execute("git rev-parse refs/heads/main").stdout.strip()
        topic_head_before = execute("git rev-parse refs/heads/topic").stdout.strip()
        status_before = execute("git status --porcelain").stdout.strip()

        # 6. Workflow 1: git archive main (no prefix)
        zip1_path = os.path.join(archives_dir, "main.zip")
        execute(f'git archive --format zip --output "{zip1_path}" main')

        # 7. Workflow 2: git archive main with --prefix=release/
        zip2_path = os.path.join(archives_dir, "main_prefixed.zip")
        execute(f'git archive --format zip --prefix=release/ --output "{zip2_path}" main')

        # 8. Workflow 3: git archive topic (no prefix)
        zip3_path = os.path.join(archives_dir, "topic.zip")
        execute(f'git archive --format zip --output "{zip3_path}" topic')

        # --- ASSERTION 1: Workflow 1 (main.zip) contains root-level files matching Tree C ---
        with zipfile.ZipFile(zip1_path, "r") as z1:
            names1 = sorted(z1.namelist())
            notes1_content = z1.read("notes.txt").decode("utf-8")
            todo1_content = z1.read("todo.txt").decode("utf-8")
        assert names1 == ["notes.txt", "todo.txt"], f"Unexpected entries in main.zip: {names1}"
        assert notes1_content == "alpha\nbeta\n", "notes.txt content mismatch in main.zip"
        assert todo1_content == "one\n", "todo.txt content mismatch in main.zip"
        log_records.append("Assertion 1 Passed: main.zip contains exact root-level entries matching Tree C")

        # --- ASSERTION 2: Workflow 2 (--prefix=release/) nests all entries under prefix ---
        with zipfile.ZipFile(zip2_path, "r") as z2:
            names2 = sorted(z2.namelist())
            notes2_content = z2.read("release/notes.txt").decode("utf-8")
            todo2_content = z2.read("release/todo.txt").decode("utf-8")
        assert names2 == ["release/", "release/notes.txt", "release/todo.txt"], f"Unexpected entries in main_prefixed.zip: {names2}"
        assert notes2_content == "alpha\nbeta\n", "notes.txt content mismatch in main_prefixed.zip"
        assert todo2_content == "one\n", "todo.txt content mismatch in main_prefixed.zip"
        log_records.append("Assertion 2 Passed: main_prefixed.zip entries are correctly nested under 'release/'")

        # --- ASSERTION 3: Workflow 3 (topic.zip) exports only Tree B, omitting Commit C files ---
        with zipfile.ZipFile(zip3_path, "r") as z3:
            names3 = sorted(z3.namelist())
            notes3_content = z3.read("notes.txt").decode("utf-8")
        assert names3 == ["notes.txt"], f"Unexpected entries in topic.zip: {names3}"
        assert "todo.txt" not in names3, "todo.txt should not be present in topic.zip"
        assert notes3_content == "alpha\nbeta\n", "notes.txt content mismatch in topic.zip"
        log_records.append("Assertion 3 Passed: topic.zip exports only Commit B files, omitting todo.txt")

        # --- ASSERTION 4: Repository state (refs, index, working tree) is untouched ---
        main_head_after = execute("git rev-parse refs/heads/main").stdout.strip()
        topic_head_after = execute("git rev-parse refs/heads/topic").stdout.strip()
        status_after = execute("git status --porcelain").stdout.strip()

        assert main_head_after == main_head_before == commit_c, "main ref changed unexpectedly"
        assert topic_head_after == topic_head_before == commit_b, "topic ref changed unexpectedly"
        assert status_after == status_before == "", "Working tree/index became dirty after git archive"
        log_records.append("Assertion 4 Passed: Repository refs, index, and working tree remain completely untouched")

        return {
            "iteration": iteration_num,
            "commit_a": commit_a,
            "commit_b": commit_b,
            "commit_c": commit_c,
            "main_zip_entries": names1,
            "prefixed_zip_entries": names2,
            "topic_zip_entries": names3,
            "status_clean": (status_after == ""),
            "all_assertions_passed": True
        }

def main():
    log_records = []
    log_records.append("Starting automated verification check for R12-T016")

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
                "task": "R12-T016",
                "success": success,
                "tool_versions": versions,
                "iterations": results
            }, f, indent=2)

    print("All checks for R12-T016 passed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
