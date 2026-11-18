#!/usr/bin/env python3
"""
Verification check for Task R12-T037:
Failure diagnosis for "I want to remove a file from Git but keep the file" (git rm --cached log.txt)
in git-flight-rules.

Verifies:
1. Standard repository setup:
   - Branch: main
   - Author: Course Student <student@example.invalid>
   - Commit A: creates notes.txt containing "alpha\n"
   - Commit B: appends "beta\n" to notes.txt
   - Branch topic created at commit B
   - Commit C: creates todo.txt containing "one\n"
   - Commit D: adds log.txt containing "log line 1\n"
   - Local bare repository used as remote via file:// URL
2. Violated Precondition (Bad Case):
   - Precondition: The file's staged index content must not differ from both HEAD and the working tree.
   - Violation:
     a) Modify log.txt and stage changes via git add (index differs from HEAD).
     b) Modify log.txt again in working directory without staging (worktree differs from index).
   - Execution of `git rm --cached log.txt` fails with non-zero exit status (code 1).
   - Error category: Data Safety / Staged Content Divergence (Git refuses to destroy intermediate staged work).
   - Assert that log.txt remains in Git's index during the failed attempt.
3. Repaired Case:
   - Smallest correction:
     Align the index with the working tree using `git add log.txt` (or pass `-f` to force),
     then execute `git rm --cached log.txt`.
   - Execution succeeds with exit code 0.
   - State assertions:
     - log.txt is removed from the index (git ls-files --error-unmatch fails).
     - log.txt remains intact on the filesystem in the working tree with all lines preserved.
     - git status --porcelain confirms staged deletion ('D ') and untracked file ('??').
     - Unrelated files (notes.txt, todo.txt) and commit history remain untouched.
4. Two independent runs across separate temporary directories with matching results.
5. Generates inputs.json, results.json, tool_versions.json, tool_versions.txt, and run_check.log.
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


def setup_and_run(base_dir):
    """
    Sets up the repository fixture, demonstrates the violated precondition
    on `git rm --cached log.txt`, executes the repair, and returns captured states.
    """
    bare_repo = os.path.join(base_dir, "remote.git")
    work_repo = os.path.join(base_dir, "workdir")

    # Step 1: Initialize bare remote and working repository
    run_cmd(["git", "init", "--bare", "-b", "main", bare_repo])
    run_cmd(["git", "init", "-b", "main", work_repo])
    run_cmd(["git", "config", "user.name", "Course Student"], cwd=work_repo)
    run_cmd(["git", "config", "user.email", "student@example.invalid"], cwd=work_repo)
    run_cmd(["git", "config", "commit.gpgSign", "false"], cwd=work_repo)

    # Commit A: creates notes.txt with "alpha\n"
    notes_path = os.path.join(work_repo, "notes.txt")
    with open(notes_path, "w") as f:
        f.write("alpha\n")
    run_cmd(["git", "add", "notes.txt"], cwd=work_repo)
    run_cmd(["git", "commit", "-m", "Commit A: create notes.txt"], cwd=work_repo)
    commit_a_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=work_repo)
    commit_a_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=work_repo)

    # Commit B: appends "beta\n"
    with open(notes_path, "a") as f:
        f.write("beta\n")
    run_cmd(["git", "add", "notes.txt"], cwd=work_repo)
    run_cmd(["git", "commit", "-m", "Commit B: append beta"], cwd=work_repo)
    commit_b_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=work_repo)
    commit_b_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=work_repo)

    # Create branch topic at Commit B
    run_cmd(["git", "branch", "topic"], cwd=work_repo)

    # Commit C: adds todo.txt with "one\n"
    todo_path = os.path.join(work_repo, "todo.txt")
    with open(todo_path, "w") as f:
        f.write("one\n")
    run_cmd(["git", "add", "todo.txt"], cwd=work_repo)
    run_cmd(["git", "commit", "-m", "Commit C: add todo.txt"], cwd=work_repo)
    commit_c_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=work_repo)
    commit_c_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=work_repo)

    # Commit D: adds log.txt containing "log line 1\n"
    log_path = os.path.join(work_repo, "log.txt")
    with open(log_path, "w") as f:
        f.write("log line 1\n")
    run_cmd(["git", "add", "log.txt"], cwd=work_repo)
    run_cmd(["git", "commit", "-m", "Commit D: add log.txt"], cwd=work_repo)
    commit_d_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=work_repo)
    commit_d_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=work_repo)

    # Push to bare remote
    run_cmd(["git", "remote", "add", "origin", f"file://{bare_repo}"], cwd=work_repo)
    run_cmd(["git", "push", "origin", "main"], cwd=work_repo)
    run_cmd(["git", "push", "origin", "topic"], cwd=work_repo)

    # Step 2: Construct violated precondition (three-way divergence)
    # Modification 1: Stage an edit to log.txt (index diverges from HEAD)
    with open(log_path, "a") as f:
        f.write("staged log line 2\n")
    run_cmd(["git", "add", "log.txt"], cwd=work_repo)

    # Modification 2: Make further unstaged edits in working directory (worktree diverges from index)
    with open(log_path, "a") as f:
        f.write("unstaged log line 3\n")

    expected_full_content = "log line 1\nstaged log line 2\nunstaged log line 3\n"
    with open(log_path) as f:
        assert f.read() == expected_full_content

    # Step 3: Bad Case Execution - `git rm --cached log.txt`
    bad_rc, bad_stdout, bad_stderr = run_cmd_allow_fail(
        ["git", "rm", "--cached", "log.txt"], cwd=work_repo
    )
    # Assert nonzero exit status
    assert bad_rc != 0, f"Expected non-zero exit code for violated precondition, got {bad_rc}"
    # Semantic verification of error message (avoid brittle byte-for-byte comparison)
    assert any(
        kw in bad_stderr.lower()
        for kw in ["staged content different", "different from both", "force removal", "use -f"]
    ), f"Unexpected error output: {bad_stderr}"

    # State assertion: log.txt is still tracked in the index
    in_index_rc, _, _ = run_cmd_allow_fail(
        ["git", "ls-files", "--error-unmatch", "log.txt"], cwd=work_repo
    )
    assert in_index_rc == 0, "log.txt should still be in index after failed git rm --cached"

    # Step 4: Repaired Case Execution - Smallest Correction
    # Smallest correction: Stage the working tree modifications so index matches working tree
    run_cmd(["git", "add", "log.txt"], cwd=work_repo)
    # Now git rm --cached log.txt succeeds cleanly
    repaired_rc, repaired_stdout, repaired_stderr = run_cmd_allow_fail(
        ["git", "rm", "--cached", "log.txt"], cwd=work_repo
    )
    assert repaired_rc == 0, f"Repaired git rm --cached failed: {repaired_stderr}"

    # Step 5: Post-repair state verifications
    # 5.1: File removed from index
    ls_rc, _, _ = run_cmd_allow_fail(
        ["git", "ls-files", "--error-unmatch", "log.txt"], cwd=work_repo
    )
    assert ls_rc != 0, "log.txt must no longer be present in Git index"

    # 5.2: File remains intact in the working tree
    assert os.path.exists(log_path), "log.txt must remain on disk in working directory"
    with open(log_path) as f:
        actual_worktree_content = f.read()
    assert actual_worktree_content == expected_full_content, "Working tree content was corrupted"

    # 5.3: Status verifies staged deletion and untracked file
    status_porcelain = run_cmd(["git", "status", "--porcelain"], cwd=work_repo, strip=False)
    assert "D  log.txt" in status_porcelain or "D log.txt" in status_porcelain, "Status must show staged deletion of log.txt"
    assert "?? log.txt" in status_porcelain, "Status must show log.txt as untracked in working tree"

    # 5.4: Unrelated files remain unchanged
    with open(notes_path) as f:
        assert f.read() == "alpha\nbeta\n"
    with open(todo_path) as f:
        assert f.read() == "one\n"

    # 5.5: HEAD commit hash remains at Commit D
    current_head = run_cmd(["git", "rev-parse", "HEAD"], cwd=work_repo)
    assert current_head == commit_d_hash

    return {
        "commit_a_hash": commit_a_hash,
        "commit_a_tree": commit_a_tree,
        "commit_b_hash": commit_b_hash,
        "commit_b_tree": commit_b_tree,
        "commit_c_hash": commit_c_hash,
        "commit_c_tree": commit_c_tree,
        "commit_d_hash": commit_d_hash,
        "commit_d_tree": commit_d_tree,
        "bad_rc": bad_rc,
        "bad_stderr": bad_stderr,
        "still_in_index": in_index_rc == 0,
        "repaired_rc": repaired_rc,
        "removed_from_index": ls_rc != 0,
        "file_kept_on_disk": os.path.exists(log_path),
        "file_content": actual_worktree_content,
        "status_porcelain": status_porcelain.strip(),
        "current_head": current_head,
    }


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    work_dir = os.path.join(repo_root, "work", "R12-T037")
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
        "task": "R12-T037",
        "guide_section": "I want to remove a file from Git but keep the file",
        "command_anchor": "git rm --cached log.txt",
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
                "action": "add log.txt",
                "content": "log line 1\n",
            },
        ],
        "violated_precondition": {
            "description": "Staged index content differs from both HEAD and the working tree",
            "error_category": "Data Safety / Staged Content Divergence",
            "expected_exit_code": 1,
            "smallest_correction": "Stage current working tree state (git add log.txt) or pass -f flag (git rm --cached -f log.txt)",
        },
    }

    with open(os.path.join(work_dir, "inputs.json"), "w") as f:
        json.dump(inputs_data, f, indent=2)

    # Run 1 in temporary directory
    with tempfile.TemporaryDirectory(prefix="gfr_t037_run1_") as td1:
        run1 = setup_and_run(td1)

    # Run 2 in temporary directory
    with tempfile.TemporaryDirectory(prefix="gfr_t037_run2_") as td2:
        run2 = setup_and_run(td2)

    # Deterministic consistency assertions
    assert run1["commit_a_tree"] == run2["commit_a_tree"]
    assert run1["commit_b_tree"] == run2["commit_b_tree"]
    assert run1["commit_c_tree"] == run2["commit_c_tree"]
    assert run1["commit_d_tree"] == run2["commit_d_tree"]
    assert run1["bad_rc"] == run2["bad_rc"] == 1
    assert run1["repaired_rc"] == run2["repaired_rc"] == 0
    assert run1["file_content"] == run2["file_content"]
    assert run1["removed_from_index"] == run2["removed_from_index"] is True
    assert run1["file_kept_on_disk"] == run2["file_kept_on_disk"] is True

    # Save results
    results_data = {
        "status": "PASS",
        "assertions_verified": [
            {
                "fact": "Violated precondition causes git rm --cached log.txt to fail with nonzero exit status (code 1)",
                "expected_rc": 1,
                "actual_rc": run1["bad_rc"],
                "passed": True,
            },
            {
                "fact": "Git protects uncommitted staged work and keeps file in the index during the bad case",
                "expected_still_in_index": True,
                "actual_still_in_index": run1["still_in_index"],
                "passed": True,
            },
            {
                "fact": "Smallest correction (aligning index via git add) allows git rm --cached log.txt to succeed with exit code 0",
                "expected_rc": 0,
                "actual_rc": run1["repaired_rc"],
                "passed": True,
            },
            {
                "fact": "Repaired operation removes log.txt from Git index (untracked by Git)",
                "expected_removed_from_index": True,
                "actual_removed_from_index": run1["removed_from_index"],
                "passed": True,
            },
            {
                "fact": "log.txt is preserved on disk in working directory with full content intact",
                "expected_preserved": True,
                "actual_preserved": run1["file_kept_on_disk"],
                "actual_content": run1["file_content"],
                "passed": True,
            },
            {
                "fact": "git status shows staged deletion (D) in index and untracked (??) in worktree",
                "expected_in_status": "D log.txt and ?? log.txt",
                "actual_status": run1["status_porcelain"],
                "passed": True,
            },
            {
                "fact": "Two independent runs across separate temporary directories produce identical results",
                "expected_tree": run1["commit_d_tree"],
                "actual_tree": run2["commit_d_tree"],
                "passed": True,
            },
        ],
        "failure_diagnosis": {
            "violated_precondition": "Three-way divergence: staged index differs from both HEAD and worktree",
            "error_category": "Data Safety / Staged Content Divergence",
            "exit_status": run1["bad_rc"],
            "captured_error_snippet": run1["bad_stderr"].splitlines()[0] if run1["bad_stderr"] else "",
            "correction_applied": "git add log.txt (aligns index to working tree before git rm --cached)",
        },
    }

    with open(os.path.join(work_dir, "results.json"), "w") as f:
        json.dump(results_data, f, indent=2)

    log_message = (
        "All assertions PASSED successfully across two independent temporary directory runs!\n"
        f"Fixture HEAD Commit: {run1['commit_d_hash']}\n"
        f"Fixture HEAD Tree:   {run1['commit_d_tree']}\n"
        f"Bad case failed as expected with exit status {run1['bad_rc']}.\n"
        f"  Error message: {run1['bad_stderr'].splitlines()[0] if run1['bad_stderr'] else ''}\n"
        f"Repaired case succeeded with exit status {run1['repaired_rc']}.\n"
        "Verified: log.txt removed from index, preserved in working directory.\n"
        f"Working tree status: {run1['status_porcelain']}\n"
    )

    with open(os.path.join(work_dir, "run_check.log"), "w") as f:
        f.write(log_message)

    print(log_message)


if __name__ == "__main__":
    main()
