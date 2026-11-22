#!/usr/bin/env python3
"""
Automated verification check for Task R12-T015
Item: README.md - "Suggesting code via patches"

Verifies:
- Setup with branch main, author Course Student <student@example.invalid>
- Commits A, B, and C; branch topic at Commit B
- Path quoting handling for 'release notes.txt' and 'sample data'
- Demonstrates failure when unquoted (shell word-splitting)
- Successful staging with quotes: git add "release notes.txt" "sample data"
- Disambiguation with -- in: git format-patch HEAD^ -- "release notes.txt" "sample data"
- Verification that patch applies cleanly with git am, preserving spaces in paths
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
        log_records.append(f"Commit C hash: {commit_c}")

        # 6. Switch to topic branch
        execute("git checkout topic")

        # 7. Create files and directory with spaces
        sample_data_dir = os.path.join(td, "sample data")
        os.makedirs(sample_data_dir, exist_ok=True)
        sample_file_path = os.path.join(sample_data_dir, "data.txt")
        with open(sample_file_path, "w", encoding="utf-8") as f:
            f.write("sample content\n")

        release_notes_path = os.path.join(td, "release notes.txt")
        with open(release_notes_path, "w", encoding="utf-8") as f:
            f.write("v1.0 release notes\n")

        # --- ASSERTION 1: Unquoted path handling triggers shell word-splitting error ---
        unquoted_res = execute("git add release notes.txt", check=False)
        assert unquoted_res.returncode != 0, "Unquoted git add should fail due to space in filename"
        assert "pathspec 'release' did not match any files" in unquoted_res.stderr, (
            f"Expected pathspec error, got: {unquoted_res.stderr}"
        )
        log_records.append("Assertion 1 Passed: Unquoted pathspec correctly rejected by git add")

        # --- ASSERTION 2: Quoted path handling stages intended files ---
        execute('git add "release notes.txt" "sample data"')
        execute('git commit -m "Add release notes and sample data"')
        topic_commit = execute("git rev-parse HEAD").stdout.strip()
        log_records.append(f"Topic commit with quoted paths: {topic_commit}")

        # Generate patch using -- to disambiguate revisions from paths
        patch_file = execute('git format-patch HEAD^ -- "release notes.txt" "sample data"').stdout.strip()
        patch_full_path = os.path.join(td, patch_file)
        assert os.path.exists(patch_full_path), f"Patch file not found: {patch_full_path}"

        with open(patch_full_path, "r", encoding="utf-8") as pf:
            patch_content = pf.read()
        assert "release notes.txt" in patch_content, "Patch file must preserve 'release notes.txt'"
        assert "sample data/data.txt" in patch_content, "Patch file must preserve 'sample data/data.txt'"
        log_records.append("Assertion 2 Passed: Patch generated cleanly preserving spaces in paths and filenames")

        # --- ASSERTION 3: git am applies patch preserving spaces and directory structure ---
        execute("git checkout main")
        execute(f'git am "{patch_full_path}"')
        main_patch_commit = execute("git rev-parse HEAD").stdout.strip()
        log_records.append(f"Main HEAD after git am: {main_patch_commit}")

        # Remove the patch file after applying so working tree is clean
        if os.path.exists(patch_full_path):
            os.remove(patch_full_path)

        # Verify applied files
        with open(release_notes_path, "r", encoding="utf-8") as rf:
            applied_release_notes = rf.read()
        with open(sample_file_path, "r", encoding="utf-8") as sf:
            applied_sample_data = sf.read()

        assert applied_release_notes == "v1.0 release notes\n", "Applied release notes content mismatch"
        assert applied_sample_data == "sample content\n", "Applied sample data content mismatch"
        log_records.append("Assertion 3 Passed: Applied files match original content with spaces in paths preserved")

        # --- ASSERTION 4: Clean index and working tree ---
        status_porcelain = execute("git status --porcelain").stdout.strip()
        assert status_porcelain == "", f"Assertion 4 Failed: Working tree/index not clean: {status_porcelain}"
        log_records.append("Assertion 4 Passed: Working tree and index are clean")

        return {
            "iteration": iteration_num,
            "commit_a": commit_a,
            "commit_b": commit_b,
            "commit_c": commit_c,
            "topic_commit": topic_commit,
            "patch_file": patch_file,
            "main_after_am": main_patch_commit,
            "all_assertions_passed": True
        }

def main():
    log_records = []
    log_records.append("Starting automated verification check for R12-T015")

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
                "task": "R12-T015",
                "success": success,
                "tool_versions": versions,
                "iterations": results
            }, f, indent=2)

    print("All checks for R12-T015 passed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
