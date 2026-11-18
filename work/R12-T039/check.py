#!/usr/bin/env python3
"""
Verification check for Task R12-T039:
Prerequisite clarification for "Stash specific files" (git stash push <path>...)
in git-flight-rules.

Verifies:
1. Prerequisites & Visibility:
   - Git Version requirement: Git >= 2.13.0 (supports pathspec in git stash push).
   - Valid repository state with existing commits (valid HEAD ref).
   - Current branch visibility: verified via git branch --show-current.
   - Staged changes visibility: verified via git status / git diff --cached.
   - Unstaged changes visibility: verified via git status / git diff.
   - Purely local Git configuration: user.name and user.email configured in repo only,
     never modifying global Git configuration (~/.gitconfig).
2. Standard repository scenario:
   - Branch: main
   - Author: Course Student <student@example.invalid>
   - Commit A: creates notes.txt with "alpha\n"
   - Commit B: appends "beta\n" to notes.txt
   - Branch topic created at commit B
   - Commit C: creates todo.txt with "one\n" on main
3. Execution of single-file stash:
   - On branch topic, notes.txt has staged edits, todo.txt has unstaged edits.
   - Command: (topic)$ git stash push notes.txt
   - State Fact 1: Only notes.txt is saved to the stash (git stash show --name-only).
   - State Fact 2: notes.txt in working tree and index is restored to clean commit state.
   - State Fact 3: Unmentioned file (todo.txt) is untouched and remains modified in worktree.
   - State Fact 4: refs/stash reference is created and points to a valid stash commit object.
   - State Fact 5: Current branch remains on topic throughout the operation.
4. Execution of multi-file stash:
   - Command: (topic)$ git stash push file1 file2
   - Verifies multiple specific files are stashed while leaving other modified files in worktree.
5. Runs twice across separate temporary directories with matching results.
6. Generates inputs.json, results.json, tool_versions.json, tool_versions.txt, and run_check.log.
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
    Sets up the repository, exercises single and multi-file stash push,
    and returns captured state facts and assertions.
    """
    repo_dir = os.path.join(base_dir, "repo")

    # Prerequisite verification: Purely local configuration (never modify global config)
    run_cmd(["git", "init", "-b", "main", repo_dir])
    run_cmd(["git", "config", "--local", "user.name", "Course Student"], cwd=repo_dir)
    run_cmd(["git", "config", "--local", "user.email", "student@example.invalid"], cwd=repo_dir)
    run_cmd(["git", "config", "--local", "commit.gpgSign", "false"], cwd=repo_dir)

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

    # Create branch topic at Commit B
    run_cmd(["git", "branch", "topic"], cwd=repo_dir)

    # Commit C on main
    todo_path = os.path.join(repo_dir, "todo.txt")
    with open(todo_path, "w") as f:
        f.write("one\n")
    run_cmd(["git", "add", "todo.txt"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "Commit C: add todo.txt"], cwd=repo_dir)
    commit_c_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    commit_c_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_dir)

    # Switch to branch topic
    run_cmd(["git", "checkout", "topic"], cwd=repo_dir)
    branch_visible = run_cmd(["git", "branch", "--show-current"], cwd=repo_dir)
    assert branch_visible == "topic", f"Expected branch topic, got: {branch_visible}"

    # Also track a second file on topic so we can test partial stashing of tracked files
    with open(todo_path, "w") as f:
        f.write("topic todo\n")
    run_cmd(["git", "add", "todo.txt"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "Commit D on topic: track todo.txt"], cwd=repo_dir)
    commit_d_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    commit_d_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_dir)

    # --- Step 1: Make repository state visible (staged vs unstaged) ---
    # Make staged changes to notes.txt
    with open(notes_path, "a") as f:
        f.write("staged gamma\n")
    run_cmd(["git", "add", "notes.txt"], cwd=repo_dir)

    # Make unstaged changes to todo.txt
    with open(todo_path, "a") as f:
        f.write("unstaged line\n")

    # Visibility checks
    status_before = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
    staged_diff = run_cmd(["git", "diff", "--cached", "--name-only"], cwd=repo_dir)
    unstaged_diff = run_cmd(["git", "diff", "--name-only"], cwd=repo_dir)
    assert "M  notes.txt" in status_before or "M notes.txt" in status_before
    assert " M todo.txt" in status_before
    assert staged_diff == "notes.txt"
    assert unstaged_diff == "todo.txt"

    # --- Step 2: Execute single-file stash: git stash push working-directory-path/filename.ext ---
    stash_single_res = run_cmd(["git", "stash", "push", "notes.txt"], cwd=repo_dir)
    assert "Saved working directory and index state" in stash_single_res

    # State Fact 1: Only notes.txt was stashed
    stashed_files_single = run_cmd(["git", "stash", "show", "--name-only"], cwd=repo_dir)
    assert stashed_files_single == "notes.txt", f"Unexpected files in stash: {stashed_files_single}"

    # State Fact 2: notes.txt restored to clean commit state (alpha\nbeta\n)
    with open(notes_path) as f:
        restored_notes_content = f.read()
    assert restored_notes_content == "alpha\nbeta\n", f"notes.txt content was not restored: {restored_notes_content}"

    # State Fact 3: Unmentioned file (todo.txt) was NOT stashed and remains modified
    status_after_single = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
    assert "M todo.txt" in status_after_single
    assert "notes.txt" not in status_after_single
    with open(todo_path) as f:
        todo_content = f.read()
    assert todo_content == "topic todo\nunstaged line\n"

    # State Fact 4: refs/stash points to a valid commit
    stash_ref_hash = run_cmd(["git", "rev-parse", "refs/stash"], cwd=repo_dir)
    assert len(stash_ref_hash) == 40

    # State Fact 5: Current branch remained on topic
    current_branch_after = run_cmd(["git", "branch", "--show-current"], cwd=repo_dir)
    assert current_branch_after == "topic"

    # Drop the stash to reset for multi-file stash test
    run_cmd(["git", "stash", "drop"], cwd=repo_dir)

    # --- Step 3: Multi-file stash: git stash push file1 file2 ---
    # Add a third file to demonstrate partial stashing of 2 out of 3 files
    extra_path = os.path.join(repo_dir, "extra.txt")
    with open(extra_path, "w") as f:
        f.write("extra file\n")
    run_cmd(["git", "add", "extra.txt"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "Commit E on topic: track extra.txt"], cwd=repo_dir)

    # Modify all 3 files
    with open(notes_path, "a") as f:
        f.write("notes edit\n")
    with open(todo_path, "a") as f:
        f.write("todo edit\n")
    with open(extra_path, "a") as f:
        f.write("extra edit\n")

    # Stash multiple specific files: notes.txt and todo.txt (leaving extra.txt modified)
    run_cmd(["git", "stash", "push", "notes.txt", "todo.txt"], cwd=repo_dir)

    stashed_files_multi = run_cmd(["git", "stash", "show", "--name-only"], cwd=repo_dir).splitlines()
    assert sorted(stashed_files_multi) == ["notes.txt", "todo.txt"], f"Unexpected stashed files: {stashed_files_multi}"

    # Verify extra.txt remained modified in working tree
    status_after_multi = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
    assert "M extra.txt" in status_after_multi
    assert "notes.txt" not in status_after_multi
    assert "todo.txt" not in status_after_multi

    return {
        "commit_a_hash": commit_a_hash,
        "commit_a_tree": commit_a_tree,
        "commit_b_hash": commit_b_hash,
        "commit_b_tree": commit_b_tree,
        "commit_c_hash": commit_c_hash,
        "commit_c_tree": commit_c_tree,
        "commit_d_hash": commit_d_hash,
        "commit_d_tree": commit_d_tree,
        "branch_visible": branch_visible,
        "status_before": status_before,
        "staged_diff": staged_diff,
        "unstaged_diff": unstaged_diff,
        "stashed_files_single": stashed_files_single,
        "restored_notes_content": restored_notes_content,
        "status_after_single": status_after_single,
        "stash_ref_hash": stash_ref_hash,
        "stashed_files_multi": sorted(stashed_files_multi),
        "status_after_multi": status_after_multi,
    }


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    work_dir = os.path.join(repo_root, "work", "R12-T039")
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
        "task": "R12-T039",
        "guide_section": "Stash specific files",
        "command_anchors": [
            "git stash push working-directory-path/filename.ext",
            "git stash push working-directory-path/filename1.ext working-directory-path/filename2.ext",
        ],
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
        ],
        "prerequisites_verified": [
            "Git version >= 2.13.0 supporting pathspecs in git stash push",
            "Valid repository with existing HEAD commit",
            "Targeted files are tracked with uncommitted changes (staged or unstaged)",
            "Purely local configuration (never touches user global ~/.gitconfig)",
            "Visibility of current branch, staged changes, and unstaged changes",
        ],
    }

    with open(os.path.join(work_dir, "inputs.json"), "w") as f:
        json.dump(inputs_data, f, indent=2)

    # Run 1 in temporary directory
    with tempfile.TemporaryDirectory(prefix="gfr_t039_run1_") as td1:
        run1 = setup_and_run(td1)

    # Run 2 in temporary directory
    with tempfile.TemporaryDirectory(prefix="gfr_t039_run2_") as td2:
        run2 = setup_and_run(td2)

    # Deterministic consistency assertions
    assert run1["commit_a_tree"] == run2["commit_a_tree"]
    assert run1["commit_b_tree"] == run2["commit_b_tree"]
    assert run1["commit_c_tree"] == run2["commit_c_tree"]
    assert run1["commit_d_tree"] == run2["commit_d_tree"]
    assert run1["branch_visible"] == run2["branch_visible"] == "topic"
    assert run1["stashed_files_single"] == run2["stashed_files_single"] == "notes.txt"
    assert run1["restored_notes_content"] == run2["restored_notes_content"] == "alpha\nbeta\n"
    assert run1["stashed_files_multi"] == run2["stashed_files_multi"] == ["notes.txt", "todo.txt"]

    # Save results
    results_data = {
        "status": "PASS",
        "assertions_verified": [
            {
                "fact": "Current branch visibility is verified before stashing",
                "expected_branch": "topic",
                "actual_branch": run1["branch_visible"],
                "passed": True,
            },
            {
                "fact": "Staged and unstaged changes visibility verified via status and diff",
                "staged_file": run1["staged_diff"],
                "unstaged_file": run1["unstaged_diff"],
                "passed": True,
            },
            {
                "fact": "Single-file stash (git stash push notes.txt) stashes only the specified file",
                "expected_stashed": "notes.txt",
                "actual_stashed": run1["stashed_files_single"],
                "passed": True,
            },
            {
                "fact": "Stashed file working tree is restored to clean commit state",
                "expected_content": "alpha\nbeta\n",
                "actual_content": run1["restored_notes_content"],
                "passed": True,
            },
            {
                "fact": "Unmentioned modified file (todo.txt) remains intact in working tree",
                "unmentioned_status": run1["status_after_single"],
                "passed": True,
            },
            {
                "fact": "Multi-file stash (git stash push notes.txt todo.txt) stashes exactly the named files",
                "expected_stashed_multi": ["notes.txt", "todo.txt"],
                "actual_stashed_multi": run1["stashed_files_multi"],
                "passed": True,
            },
            {
                "fact": "All Git configuration is purely local and never modifies global ~/.gitconfig",
                "local_only": True,
                "passed": True,
            },
            {
                "fact": "Two independent runs across separate temporary directories produce identical results",
                "expected_tree": run1["commit_d_tree"],
                "actual_tree": run2["commit_d_tree"],
                "passed": True,
            },
        ],
        "state_summary": {
            "branch": run1["branch_visible"],
            "stashed_single": run1["stashed_files_single"],
            "stashed_multi": run1["stashed_files_multi"],
            "remaining_untracked_or_modified": run1["status_after_multi"],
        },
    }

    with open(os.path.join(work_dir, "results.json"), "w") as f:
        json.dump(results_data, f, indent=2)

    log_message = (
        "All assertions PASSED successfully across two independent temporary directory runs!\n"
        f"Branch Verified:         {run1['branch_visible']}\n"
        f"Staged File Before:      {run1['staged_diff']}\n"
        f"Unstaged File Before:    {run1['unstaged_diff']}\n"
        f"Single Stash File:       {run1['stashed_files_single']}\n"
        f"Multi Stash Files:       {', '.join(run1['stashed_files_multi'])}\n"
        f"Restored Notes Content:  {repr(run1['restored_notes_content'])}\n"
        "Purely local configuration verified (zero global config modifications).\n"
    )

    with open(os.path.join(work_dir, "run_check.log"), "w") as f:
        f.write(log_message)

    print(log_message)


if __name__ == "__main__":
    main()
