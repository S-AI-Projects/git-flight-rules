#!/usr/bin/env python3
"""
Automated verification script for Git Flight Rules task R12-T049.

Validates the prerequisites for "I want to view the commit history for a specific function"
using git log -L :FunctionName:FilePath. Asserts preconditions:
1. File must exist and be committed in the current branch history.
2. Function definition syntax must match language diff driver (e.g. diff=python).
3. Missing prerequisites produce explicit, predictable Git errors.
"""

import os
import subprocess
import sys
import tempfile


def run_git(cmd, cwd, env, check=True):
    """Executes a git command and returns subprocess result."""
    res = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )
    return res


def run_workflow_in_dir(repo_dir: str) -> dict:
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"

    # 1. Initialize repo and author
    run_git(["git", "init", "-b", "main"], cwd=repo_dir, env=env)
    run_git(["git", "config", "user.name", "Course Student"], cwd=repo_dir, env=env)
    run_git(["git", "config", "user.email", "student@example.invalid"], cwd=repo_dir, env=env)

    # 2. Commit A: creates notes.txt with "alpha\n"
    notes_path = os.path.join(repo_dir, "notes.txt")
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write("alpha\n")
    run_git(["git", "add", "notes.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit A: create notes.txt"], cwd=repo_dir, env=env)
    commit_a = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()

    # 3. Commit B: appends "beta\n" to notes.txt and creates branch topic pointing at Commit B
    with open(notes_path, "a", encoding="utf-8") as f:
        f.write("beta\n")
    run_git(["git", "add", "notes.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit B: append beta to notes.txt"], cwd=repo_dir, env=env)
    commit_b = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()
    run_git(["git", "branch", "topic"], cwd=repo_dir, env=env)

    # 4. Commit C: creates todo.txt with "one\n" on branch main
    todo_path = os.path.join(repo_dir, "todo.txt")
    with open(todo_path, "w", encoding="utf-8") as f:
        f.write("one\n")
    run_git(["git", "add", "todo.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit C: create todo.txt"], cwd=repo_dir, env=env)
    commit_c = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()

    # 5. Set up local diff driver attribute in .gitattributes
    gitattributes_path = os.path.join(repo_dir, ".gitattributes")
    with open(gitattributes_path, "w", encoding="utf-8") as f:
        f.write("*.py diff=python\n")
    run_git(["git", "add", ".gitattributes"], cwd=repo_dir, env=env)

    # 6. Commit D: add calculate_total function
    py_path = os.path.join(repo_dir, "calc.py")
    with open(py_path, "w", encoding="utf-8") as f:
        f.write("def calculate_total(items):\n    return sum(items)\n")
    run_git(["git", "add", "calc.py"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit D: add calculate_total in calc.py"], cwd=repo_dir, env=env)
    commit_d = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()

    # 7. Commit E: update calculate_total function
    with open(py_path, "w", encoding="utf-8") as f:
        f.write("def calculate_total(items):\n    # add discount handling\n    total = sum(items)\n    return total\n")
    run_git(["git", "add", "calc.py"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit E: refactor calculate_total in calc.py"], cwd=repo_dir, env=env)
    commit_e = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()

    # Test Missing Prerequisite 1: File does not exist in HEAD
    missing_file_res = run_git(["git", "log", "-L", ":calculate_total:missing.py"], cwd=repo_dir, env=env, check=False)

    # Test Missing Prerequisite 2: Function name not present in file
    missing_func_res = run_git(["git", "log", "-L", ":undefined_func:calc.py"], cwd=repo_dir, env=env, check=False)

    # Test Valid Prerequisites: git log -L successfully traces commits D and E
    valid_res = run_git(["git", "log", "-L", ":calculate_total:calc.py"], cwd=repo_dir, env=env, check=True)

    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "commit_d": commit_d,
        "commit_e": commit_e,
        "missing_file_code": missing_file_res.returncode,
        "missing_file_err": missing_file_res.stderr,
        "missing_func_code": missing_func_res.returncode,
        "missing_func_err": missing_func_res.stderr,
        "valid_log_stdout": valid_res.stdout,
    }


def verify_repo_state(data: dict):
    # Assertion 1: Missing file fails with nonzero exit code
    assert data["missing_file_code"] != 0, "Missing file must cause git log -L to fail"
    assert "fatal:" in data["missing_file_err"], "Missing file must produce fatal error"

    # Assertion 2: Missing function name fails with nonzero exit code
    assert data["missing_func_code"] != 0, "Missing function must cause git log -L to fail"
    assert "no match" in data["missing_func_err"] or "fatal:" in data["missing_func_err"], "Missing function must report no match"

    # Assertion 3: Valid prerequisites output traces both commits affecting the function
    assert "Commit D: add calculate_total" in data["valid_log_stdout"], "Trace must include Commit D"
    assert "Commit E: refactor calculate_total" in data["valid_log_stdout"], "Trace must include Commit E"
    assert "def calculate_total(items):" in data["valid_log_stdout"], "Trace must include function signature"


def main():
    print("Starting verification of R12-T049...")
    with tempfile.TemporaryDirectory(prefix="gfr_t049_1_") as dir1, tempfile.TemporaryDirectory(prefix="gfr_t049_2_") as dir2:
        print(f"Executing workflow in temporary repo 1: {dir1}")
        res1 = run_workflow_in_dir(dir1)
        verify_repo_state(res1)
        print("  Repo 1: All prerequisite clarification assertions passed.")

        print(f"Executing workflow in temporary repo 2: {dir2}")
        res2 = run_workflow_in_dir(dir2)
        verify_repo_state(res2)
        print("  Repo 2: All prerequisite clarification assertions passed.")

        print("Checking cross-repository consistency...")
        assert res1["missing_file_code"] == res2["missing_file_code"]
        assert res1["missing_func_code"] == res2["missing_func_code"]
        print("  Cross-repository consistency verified.")

    print("\nSUCCESS: All prerequisite clarification assertions passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
