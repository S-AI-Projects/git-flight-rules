#!/usr/bin/env python3
"""
Automated verification script for Git Flight Rules task R12-T048.

Validates that the shell sequence for "I want to cache a username and password
for a repository" (git config credential.helper cache) is executable as an
isolated test with explicit assertions about Git credential state.
Also asserts that the test fails if the decisive command is deliberately omitted.
"""

import os
import subprocess
import sys
import tempfile


def run_git(cmd, cwd, env, input_text=None, check=True):
    """Executes a git command and returns subprocess result."""
    res = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        input=input_text,
        check=check,
        capture_output=True,
        text=True,
    )
    return res


def setup_test_repo(repo_dir: str, env: dict):
    """Creates the standard Course Student commits A, B (topic), C."""
    run_git(["git", "init", "-b", "main"], cwd=repo_dir, env=env)
    run_git(["git", "config", "user.name", "Course Student"], cwd=repo_dir, env=env)
    run_git(["git", "config", "user.email", "student@example.invalid"], cwd=repo_dir, env=env)

    # Commit A
    notes_path = os.path.join(repo_dir, "notes.txt")
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write("alpha\n")
    run_git(["git", "add", "notes.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit A: create notes.txt"], cwd=repo_dir, env=env)
    commit_a = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()

    # Commit B & topic
    with open(notes_path, "a", encoding="utf-8") as f:
        f.write("beta\n")
    run_git(["git", "add", "notes.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit B: append beta to notes.txt"], cwd=repo_dir, env=env)
    commit_b = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()
    run_git(["git", "branch", "topic"], cwd=repo_dir, env=env)

    # Commit C
    todo_path = os.path.join(repo_dir, "todo.txt")
    with open(todo_path, "w", encoding="utf-8") as f:
        f.write("one\n")
    run_git(["git", "add", "todo.txt"], cwd=repo_dir, env=env)
    run_git(["git", "commit", "-m", "Commit C: create todo.txt"], cwd=repo_dir, env=env)
    commit_c = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir, env=env).stdout.strip()

    return commit_a, commit_b, commit_c


def execute_credential_flow(repo_dir: str, with_decisive_command: bool) -> dict:
    """Executes credential storage and retrieval with or without the helper config."""
    global_config = os.path.join(repo_dir, "fake_global_config")
    open(global_config, "w").close()

    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = global_config
    env["GIT_TERMINAL_PROMPT"] = "0"

    setup_test_repo(repo_dir, env)

    if with_decisive_command:
        # Decisive command from the guide
        run_git(["git", "config", "--global", "credential.helper", "cache"], cwd=repo_dir, env=env)

    # Inspect configured helper
    config_check = run_git(["git", "config", "--global", "--get", "credential.helper"], cwd=repo_dir, env=env, check=False)
    configured_helper = config_check.stdout.strip() if config_check.returncode == 0 else ""

    # Approve (store) credentials
    approve_input = "protocol=https\nhost=example.invalid\nusername=testuser\npassword=secretpass\n\n"
    run_git(["git", "credential", "approve"], cwd=repo_dir, env=env, input_text=approve_input, check=False)

    # Fill (retrieve) credentials
    fill_input = "protocol=https\nhost=example.invalid\n\n"
    fill_res = run_git(["git", "credential", "fill"], cwd=repo_dir, env=env, input_text=fill_input, check=False)

    return {
        "configured_helper": configured_helper,
        "fill_stdout": fill_res.stdout,
        "fill_returncode": fill_res.returncode,
    }


def main():
    print("Starting verification of R12-T048...")
    with tempfile.TemporaryDirectory(prefix="gfr_t048_pass_") as pass_dir:
        print(f"Testing execution with decisive command in: {pass_dir}")
        res_pass = execute_credential_flow(pass_dir, with_decisive_command=True)

        # Assertion 1: Credential helper is correctly set to cache
        assert res_pass["configured_helper"] == "cache", "credential.helper must be configured to 'cache'"
        print("  Assertion 1: Credential helper config verified.")

        # Assertion 2: Cached credentials contain stored username and password
        assert "username=testuser" in res_pass["fill_stdout"], "Cached credentials must include username"
        assert "password=secretpass" in res_pass["fill_stdout"], "Cached credentials must include password"
        print("  Assertion 2: Credential retrieval verified.")

    # Clean temporary directory verified via context manager exiting
    assert not os.path.exists(pass_dir), "Temporary directory must be cleaned up"
    print("  Assertion 3: Temporary directory cleanup verified.")

    # Negative test: deliberately omit decisive command
    with tempfile.TemporaryDirectory(prefix="gfr_t048_fail_") as fail_dir:
        print(f"Testing deliberate omission of decisive command in: {fail_dir}")
        res_fail = execute_credential_flow(fail_dir, with_decisive_command=False)

        # Assertion 4: Fails to retrieve cached password when command is omitted
        assert res_fail["configured_helper"] == "", "Helper should not be set"
        assert "password=secretpass" not in res_fail["fill_stdout"], "Credentials must not be cached without helper"
        print("  Assertion 4: Omission failure check verified.")

    assert not os.path.exists(fail_dir), "Temporary directory must be cleaned up"

    print("\nSUCCESS: All executable guide assertions passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
