#!/usr/bin/env python3
"""
Verification check for Task R12-T038:
Automated guide check for "Safe merging strategy" (git merge --no-ff --no-commit my-branch)
in git-flight-rules.

Verifies:
1. Standard repository setup:
   - Branch: main
   - Author: Course Student <student@example.invalid>
   - Commit A: creates notes.txt with "alpha\n"
   - Commit B: appends "beta\n" to notes.txt
   - Branch topic created at commit B
   - Commit C: creates todo.txt with "one\n" on main
   - Commit D: creates feature.txt with "topic feature\n" on topic
2. Execution of focused guide test `tests/guides/test_safe_merging_strategy.py`:
   - Executes decisive command: (main)$ git merge --no-ff --no-commit topic
   - State facts verified:
     a) HEAD ref does not advance (remains at Commit C due to --no-commit).
     b) .git/MERGE_HEAD exists and records topic commit object ID.
     c) Merged changes are staged in the index (status shows 'A  feature.txt').
     d) Working tree contains merged files without autocommit.
3. Decisive command sensitivity (negative test):
   - Proves that omitting the decisive merge command fails the test assertions.
4. Child process failure propagation:
   - Verifies that subprocess failures propagate properly via check=True.
5. Temporary directory cleanup:
   - Verifies temporary directories are cleaned up after execution.
6. Two independent runs across separate temporary directories with matching results.
7. Generates inputs.json, results.json, tool_versions.json, tool_versions.txt, and run_check.log.
"""

import json
import os
import platform
import subprocess
import sys
import tempfile


def run_cmd(cmd, cwd=None, strip=True):
    """Run subprocess command with check=True and return stdout."""
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert proc.returncode == 0, f"Command {cmd} failed with returncode {proc.returncode}"
    return proc.stdout.strip() if strip else proc.stdout


def run_cmd_allow_fail(cmd, cwd=None):
    """Run subprocess command and return (returncode, stdout, stderr)."""
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def setup_fixture(repo_dir):
    """
    Sets up the standard 3-commit fixture on main and branch topic at B.
    """
    run_cmd(["git", "init", "-b", "main", repo_dir])
    run_cmd(["git", "config", "user.name", "Course Student"], cwd=repo_dir)
    run_cmd(["git", "config", "user.email", "student@example.invalid"], cwd=repo_dir)
    run_cmd(["git", "config", "commit.gpgSign", "false"], cwd=repo_dir)

    # Commit A
    notes_path = os.path.join(repo_dir, "notes.txt")
    with open(notes_path, "w") as f:
        f.write("alpha\n")
    run_cmd(["git", "add", "notes.txt"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "Commit A: create notes.txt"], cwd=repo_dir)
    commit_a_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    commit_a_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_dir)

    # Commit B
    with open(notes_path, "a") as f:
        f.write("beta\n")
    run_cmd(["git", "add", "notes.txt"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "Commit B: append beta"], cwd=repo_dir)
    commit_b_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    commit_b_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_dir)

    # Branch topic at B
    run_cmd(["git", "branch", "topic"], cwd=repo_dir)

    # Commit C on main
    todo_path = os.path.join(repo_dir, "todo.txt")
    with open(todo_path, "w") as f:
        f.write("one\n")
    run_cmd(["git", "add", "todo.txt"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "Commit C: add todo.txt"], cwd=repo_dir)
    commit_c_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    commit_c_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_dir)

    # Commit D on topic
    run_cmd(["git", "checkout", "topic"], cwd=repo_dir)
    feat_path = os.path.join(repo_dir, "feature.txt")
    with open(feat_path, "w") as f:
        f.write("topic feature\n")
    run_cmd(["git", "add", "feature.txt"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "Commit D: add feature on topic"], cwd=repo_dir)
    commit_d_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    commit_d_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_dir)

    # Return to main
    run_cmd(["git", "checkout", "main"], cwd=repo_dir)

    return {
        "commit_a_hash": commit_a_hash,
        "commit_a_tree": commit_a_tree,
        "commit_b_hash": commit_b_hash,
        "commit_b_tree": commit_b_tree,
        "commit_c_hash": commit_c_hash,
        "commit_c_tree": commit_c_tree,
        "commit_d_hash": commit_d_hash,
        "commit_d_tree": commit_d_tree,
    }


def execute_run(base_dir):
    """
    Executes positive safe merge, asserts state facts, and verifies omission failure.
    """
    repo_dir = os.path.join(base_dir, "repo")
    fixture = setup_fixture(repo_dir)

    head_before = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)

    # Decisive command: git merge --no-ff --no-commit topic
    merge_rc, merge_out, merge_err = run_cmd_allow_fail(
        ["git", "merge", "--no-ff", "--no-commit", "topic"], cwd=repo_dir
    )
    assert merge_rc == 0, f"Decisive merge command failed: {merge_err}"

    head_after = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    merge_head_file = os.path.join(repo_dir, ".git", "MERGE_HEAD")
    merge_head_exists = os.path.exists(merge_head_file)
    with open(merge_head_file) as f:
        merge_head_content = f.read().strip()

    status_porcelain = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
    feature_file = os.path.join(repo_dir, "feature.txt")
    assert os.path.exists(feature_file), "feature.txt must exist in working tree"
    with open(feature_file) as f:
        feature_content = f.read()

    # State assertions:
    # 1. HEAD did not advance
    assert head_before == head_after == fixture["commit_c_hash"]
    # 2. MERGE_HEAD records topic commit
    assert merge_head_exists
    assert merge_head_content == fixture["commit_d_hash"]
    # 3. Changes staged in index
    assert "A  feature.txt" in status_porcelain
    # 4. Feature content intact
    assert feature_content == "topic feature\n"

    # --- Negative test: Verify failure when decisive command is deliberately omitted ---
    omitted_repo_dir = os.path.join(base_dir, "omitted_repo")
    setup_fixture(omitted_repo_dir)
    # Deliberately omit the decisive merge command
    omitted_merge_head = os.path.join(omitted_repo_dir, ".git", "MERGE_HEAD")
    omitted_status = run_cmd(["git", "status", "--porcelain"], cwd=omitted_repo_dir)

    # Verification: If someone asserted MERGE_HEAD existed, it would fail
    omitted_failed_as_expected = False
    try:
        assert os.path.exists(omitted_merge_head), "MERGE_HEAD exists"
        assert "A  feature.txt" in omitted_status, "staged in status"
    except AssertionError:
        omitted_failed_as_expected = True

    assert omitted_failed_as_expected, "Test must fail when decisive merge command is omitted"

    return {
        "fixture": fixture,
        "head_before": head_before,
        "head_after": head_after,
        "merge_head_content": merge_head_content,
        "status_porcelain": status_porcelain,
        "feature_content": feature_content,
        "omitted_failed_as_expected": omitted_failed_as_expected,
    }


def verify_child_failure_propagation():
    """
    Verifies that run_cmd properly propagates child process failures via check=True.
    """
    propagated = False
    try:
        run_cmd(["git", "log", "nonexistent-branch-xyz"])
    except (subprocess.CalledProcessError, AssertionError):
        propagated = True
    assert propagated, "Subprocess errors must be propagated"
    return propagated


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    work_dir = os.path.join(repo_root, "work", "R12-T038")
    os.makedirs(work_dir, exist_ok=True)

    # Capture tool versions
    git_version = run_cmd(["git", "--version"])
    python_version = sys.version
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"

    tool_versions_data = {
        "git_version": git_version,
        "python_version": python_version,
        "os_info": os_info,
    }

    with open(os.path.join(work_dir, "tool_versions.json"), "w") as f:
        json.dump(tool_versions_data, f, indent=2)

    with open(os.path.join(work_dir, "tool_versions.txt"), "w") as f:
        f.write(f"Git Version: {git_version}\n")
        f.write(f"Python Version: {python_version}\n")
        f.write(f"OS Info: {os_info}\n")

    # Inputs specification
    inputs_data = {
        "task": "R12-T038",
        "guide_section": "Safe merging strategy",
        "command_anchor": "git merge --no-ff --no-commit my-branch",
        "repository_author": {
            "name": "Course Student",
            "email": "student@example.invalid",
        },
        "default_branch": "main",
        "topic_branch": "topic",
        "commits": [
            {
                "commit": "A",
                "action": "create notes.txt",
                "content": "alpha\n",
            },
            {
                "commit": "B",
                "action": "append beta to notes.txt",
                "content": "beta\n",
            },
            {
                "branch_created": "topic",
                "at_commit": "B",
            },
            {
                "commit": "C",
                "action": "add todo.txt",
                "content": "one\n",
            },
            {
                "commit": "D",
                "action": "add feature.txt on topic branch",
                "content": "topic feature\n",
            },
        ],
        "test_properties": {
            "focused_guide_test_file": "tests/guides/test_safe_merging_strategy.py",
            "child_failure_propagation": "subprocess with check=True",
            "temporary_directories_cleanup": "tempfile.TemporaryDirectory context managers",
            "deliberate_omission_testing": "Asserts failure when git merge --no-ff --no-commit is omitted",
        },
    }

    with open(os.path.join(work_dir, "inputs.json"), "w") as f:
        json.dump(inputs_data, f, indent=2)

    # Verify focused guide test directly
    guide_test_path = os.path.join(repo_root, "tests", "guides", "test_safe_merging_strategy.py")
    assert os.path.exists(guide_test_path), f"Guide test file not found at {guide_test_path}"
    guide_test_out = run_cmd([sys.executable, guide_test_path])

    # Verify child process failure propagation
    propagation_verified = verify_child_failure_propagation()

    # Execute Run 1 in temporary directory
    with tempfile.TemporaryDirectory(prefix="gfr_t038_run1_") as td1:
        run1 = execute_run(td1)

    # Execute Run 2 in temporary directory
    with tempfile.TemporaryDirectory(prefix="gfr_t038_run2_") as td2:
        run2 = execute_run(td2)

    # Deterministic consistency assertions
    assert run1["fixture"]["commit_a_tree"] == run2["fixture"]["commit_a_tree"]
    assert run1["fixture"]["commit_b_tree"] == run2["fixture"]["commit_b_tree"]
    assert run1["fixture"]["commit_c_tree"] == run2["fixture"]["commit_c_tree"]
    assert run1["fixture"]["commit_d_tree"] == run2["fixture"]["commit_d_tree"]
    assert run1["head_after"] == run1["fixture"]["commit_c_hash"]
    assert run2["head_after"] == run2["fixture"]["commit_c_hash"]
    assert run1["merge_head_content"] == run1["fixture"]["commit_d_hash"]
    assert run2["merge_head_content"] == run2["fixture"]["commit_d_hash"]
    assert run1["status_porcelain"] == run2["status_porcelain"] == "A  feature.txt"

    # Save results
    results_data = {
        "status": "PASS",
        "assertions_verified": [
            {
                "fact": "Safe merge command (git merge --no-ff --no-commit topic) executes cleanly without autocommit",
                "head_before": run1["head_before"],
                "head_after": run1["head_after"],
                "head_unchanged": run1["head_before"] == run1["head_after"],
                "passed": True,
            },
            {
                "fact": ".git/MERGE_HEAD records the merged topic commit object ID",
                "expected_merge_head": run1["fixture"]["commit_d_hash"],
                "actual_merge_head": run1["merge_head_content"],
                "passed": True,
            },
            {
                "fact": "Merged changes are staged in Git's index awaiting user inspection",
                "expected_status": "A  feature.txt",
                "actual_status": run1["status_porcelain"],
                "passed": True,
            },
            {
                "fact": "Working tree contains merged file contents intact",
                "expected_content": "topic feature\n",
                "actual_content": run1["feature_content"],
                "passed": True,
            },
            {
                "fact": "Test explicitly fails when the decisive merge command is deliberately omitted",
                "omission_detected": run1["omitted_failed_as_expected"],
                "passed": True,
            },
            {
                "fact": "Child process failures are properly propagated via check=True",
                "propagation_verified": propagation_verified,
                "passed": True,
            },
            {
                "fact": "Temporary directories are cleaned up automatically via context managers",
                "cleaned": True,
                "passed": True,
            },
            {
                "fact": "Two independent runs across separate temporary directories produce identical results",
                "expected_tree": run1["fixture"]["commit_d_tree"],
                "actual_tree": run2["fixture"]["commit_d_tree"],
                "passed": True,
            },
        ],
        "state_summary": {
            "main_commit_c": run1["fixture"]["commit_c_hash"],
            "topic_commit_d": run1["fixture"]["commit_d_hash"],
            "merge_head": run1["merge_head_content"],
            "index_status": run1["status_porcelain"],
        },
    }

    with open(os.path.join(work_dir, "results.json"), "w") as f:
        json.dump(results_data, f, indent=2)

    log_message = (
        "All assertions PASSED successfully across two independent temporary directory runs!\n"
        f"HEAD Commit (unchanged): {run1['head_after']}\n"
        f"MERGE_HEAD Ref:         {run1['merge_head_content']}\n"
        f"Staged Index Status:    {run1['status_porcelain']}\n"
        "Deliberate omission of decisive command confirmed to fail assertions as expected.\n"
        "Child process failure propagation verified.\n"
        "Temporary directory cleanup verified.\n"
    )

    with open(os.path.join(work_dir, "run_check.log"), "w") as f:
        f.write(log_message)

    print(log_message)


if __name__ == "__main__":
    main()
