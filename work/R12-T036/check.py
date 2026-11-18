#!/usr/bin/env python3
"""
Verification check for Task R12-T036:
Command comparison for "I want to add code to someone else's repository" in git-flight-rules.

Compares:
1. Hosted Fork & Pull Request workflow:
   - Contributor pushes topic branch to personal fork remote (`origin`):
     (topic)$ git push --set-upstream origin topic
   - Precondition: Requires a hosted fork remote repository with contributor write access.
   - Resulting ref state: Creates `refs/remotes/origin/topic` and configures tracking (`@{u} == origin/topic`).
   - Resulting worktree/index state: Clean working tree and index; no auxiliary transfer files on disk.
   - Resulting commit state: Contributor's commit object ID is preserved identically on the remote fork.

2. Patch export and application workflow:
   - Contributor generates standalone patch file using git format-patch:
     (topic)$ git format-patch -1 topic
   - Maintainer applies patch via git am:
     (main)$ git am 0001-*.patch
   - Precondition: Operates locally; no remote fork repository or network access required.
   - Resulting ref state: No remote tracking ref `origin/topic` is created; local refs remain unchanged.
   - Resulting worktree/index state: Untracked patch file `0001-*.patch` appears in contributor worktree.
   - Resulting commit state: Maintainer creates a new commit object ID with identical tree hash and
     contributor author metadata, but with maintainer's committer identity and timestamp.

Verifies:
- Standard test fixture: Branch main, author Course Student <student@example.invalid>,
  commits A (create notes.txt with "alpha\n"), B (append "beta\n"), branch topic at B,
  commit C (add todo.txt with "one\n"), and topic contribution commit D.
- Runs twice in separate temporary directories with identical deterministic results.
- Saves inputs.json, results.json, tool_versions.json, tool_versions.txt, and run_check.log.
"""

import glob
import json
import os
import platform
import shutil
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


def setup_fixture(base_dir):
    """
    Sets up the upstream remote and contributor repository with:
    - Commit A: notes.txt with "alpha\n"
    - Commit B: notes.txt with "beta\n"
    - Branch topic created at Commit B
    - Commit C: todo.txt with "one\n" on main
    - Commit D: feature.txt with "contribution feature\n" on topic
    """
    upstream_bare = os.path.join(base_dir, "upstream.git")
    run_cmd(["git", "init", "--bare", "-b", "main", upstream_bare])

    work_repo = os.path.join(base_dir, "fixture_repo")
    run_cmd(["git", "clone", f"file://{upstream_bare}", work_repo])
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

    # Push main to upstream
    run_cmd(["git", "push", "origin", "main"], cwd=work_repo)

    # Checkout branch topic and create contribution Commit D
    run_cmd(["git", "checkout", "topic"], cwd=work_repo)
    feat_path = os.path.join(work_repo, "feature.txt")
    with open(feat_path, "w") as f:
        f.write("contribution feature\n")
    run_cmd(["git", "add", "feature.txt"], cwd=work_repo)
    run_cmd(["git", "commit", "-m", "Commit D: add feature on topic"], cwd=work_repo)
    commit_d_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=work_repo)
    commit_d_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=work_repo)

    return {
        "upstream_bare": upstream_bare,
        "fixture_repo": work_repo,
        "commit_a_hash": commit_a_hash,
        "commit_a_tree": commit_a_tree,
        "commit_b_hash": commit_b_hash,
        "commit_b_tree": commit_b_tree,
        "commit_c_hash": commit_c_hash,
        "commit_c_tree": commit_c_tree,
        "commit_d_hash": commit_d_hash,
        "commit_d_tree": commit_d_tree,
    }


def execute_workflow_1_fork_pr(base_dir, fixture_repo, commit_d_hash):
    """
    Workflow 1: Hosted Fork & Pull Request workflow
    - Sets up a bare fork remote repository
    - Renames 'origin' to 'upstream' and adds 'origin' as the fork (per README.md guide)
    - Pushes topic branch with upstream tracking:
      (topic)$ git push --set-upstream origin topic
    """
    w1_dir = os.path.join(base_dir, "workflow1_fork_pr")
    shutil.copytree(fixture_repo, w1_dir)

    fork_bare = os.path.join(base_dir, "fork.git")
    run_cmd(["git", "init", "--bare", "-b", "main", fork_bare])

    # Follow README.md guide steps:
    # Rename origin (pointing to upstream) to upstream
    run_cmd(["git", "remote", "rename", "origin", "upstream"], cwd=w1_dir)
    # Add new origin pointing to personal fork
    run_cmd(["git", "remote", "add", "origin", f"file://{fork_bare}"], cwd=w1_dir)

    # Push topic branch to origin with --set-upstream
    run_cmd(["git", "push", "--set-upstream", "origin", "topic"], cwd=w1_dir)

    # State fact 1: Tracking branch configured
    tracking_ref = run_cmd(["git", "rev-parse", "--abbrev-ref", "@{u}"], cwd=w1_dir)
    assert tracking_ref == "origin/topic"

    # State fact 2: Remote-tracking ref points to commit D
    remote_ref_hash = run_cmd(["git", "rev-parse", "refs/remotes/origin/topic"], cwd=w1_dir)
    assert remote_ref_hash == commit_d_hash

    # State fact 3: Remote fork repository contains branch topic at commit D
    fork_branch_hash = run_cmd(["git", "rev-parse", "refs/heads/topic"], cwd=fork_bare)
    assert fork_branch_hash == commit_d_hash

    # State fact 4: Working tree and index are clean; no patch files created
    status_output = run_cmd(["git", "status", "--porcelain"], cwd=w1_dir)
    assert status_output == "", f"Expected clean working tree, got: {status_output}"
    patch_files = glob.glob(os.path.join(w1_dir, "*.patch"))
    assert len(patch_files) == 0, f"Expected 0 patch files, found: {patch_files}"

    return {
        "tracking_ref": tracking_ref,
        "remote_ref_hash": remote_ref_hash,
        "fork_branch_hash": fork_branch_hash,
        "status_output": status_output,
        "patch_files_count": len(patch_files),
    }


def execute_workflow_2_format_patch(base_dir, fixture_repo, upstream_bare, commit_d_tree):
    """
    Workflow 2: Patch export via git format-patch and maintainer application via git am
    - Generates patch file: (topic)$ git format-patch -1 topic
    - Maintainer applies patch in upstream repository: (main)$ git am 0001-*.patch
    """
    w2_dir = os.path.join(base_dir, "workflow2_format_patch")
    shutil.copytree(fixture_repo, w2_dir)

    # Contributor generates patch using git format-patch
    patch_filename = run_cmd(["git", "format-patch", "-1", "topic"], cwd=w2_dir)
    assert patch_filename.endswith(".patch"), f"Expected .patch file, got: {patch_filename}"

    # State fact 1: No remote tracking ref created
    rc, _, _ = run_cmd_allow_fail(["git", "rev-parse", "--abbrev-ref", "@{u}"], cwd=w2_dir)
    has_tracking_ref = (rc == 0)
    assert not has_tracking_ref, "format-patch workflow must not create a remote tracking branch"

    # State fact 2: Working tree contains untracked patch file
    status_output = run_cmd(["git", "status", "--porcelain"], cwd=w2_dir)
    assert f"?? {patch_filename}" in status_output, f"Expected patch file in status, got: {status_output}"

    # State fact 3: Patch file contents preserve author metadata and commit message
    patch_path = os.path.join(w2_dir, patch_filename)
    with open(patch_path) as f:
        patch_content = f.read()
    assert "From: Course Student <student@example.invalid>" in patch_content
    assert "Subject: [PATCH] Commit D: add feature on topic" in patch_content
    assert "+contribution feature" in patch_content

    # State fact 4: Maintainer applies patch via git am in a separate upstream workspace
    maintainer_dir = os.path.join(base_dir, "maintainer_work")
    run_cmd(["git", "clone", f"file://{upstream_bare}", maintainer_dir])
    run_cmd(["git", "config", "user.name", "Course Maintainer"], cwd=maintainer_dir)
    run_cmd(["git", "config", "user.email", "maintainer@example.invalid"], cwd=maintainer_dir)
    run_cmd(["git", "config", "commit.gpgSign", "false"], cwd=maintainer_dir)

    # Maintainer starts review branch at commit B (parent of contribution) and applies patch
    run_cmd(["git", "checkout", "-b", "review-contrib", "HEAD~1"], cwd=maintainer_dir)
    run_cmd(["git", "am", patch_path], cwd=maintainer_dir)

    am_commit_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=maintainer_dir)
    am_tree_hash = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=maintainer_dir)
    am_author = run_cmd(["git", "log", "-1", "--format=%an <%ae>"], cwd=maintainer_dir)
    am_committer = run_cmd(["git", "log", "-1", "--format=%cn <%ce>"], cwd=maintainer_dir)

    # Tree matches contributor's topic commit tree exactly
    assert am_tree_hash == commit_d_tree, f"Applied tree {am_tree_hash} != original tree {commit_d_tree}"
    # Author is preserved as original contributor
    assert am_author == "Course Student <student@example.invalid>"
    # Committer is recorded as the maintainer
    assert am_committer == "Course Maintainer <maintainer@example.invalid>"

    return {
        "patch_filename": patch_filename,
        "has_tracking_ref": has_tracking_ref,
        "status_output": status_output,
        "patch_author_header": "Course Student <student@example.invalid>",
        "am_commit_hash": am_commit_hash,
        "am_tree_hash": am_tree_hash,
        "am_author": am_author,
        "am_committer": am_committer,
    }


def run_full_check(base_dir):
    """Executes the complete test fixture and both workflows in a given base directory."""
    fixture = setup_fixture(base_dir)
    w1_results = execute_workflow_1_fork_pr(
        base_dir, fixture["fixture_repo"], fixture["commit_d_hash"]
    )
    w2_results = execute_workflow_2_format_patch(
        base_dir, fixture["fixture_repo"], fixture["upstream_bare"], fixture["commit_d_tree"]
    )
    return {
        "fixture": fixture,
        "w1": w1_results,
        "w2": w2_results,
    }


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    work_dir = os.path.join(repo_root, "work", "R12-T036")
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
        "task": "R12-T036",
        "guide_section": "I want to add code to someone else's repository",
        "author": {
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
                "content": "contribution feature\n",
            },
        ],
        "compared_workflows": {
            "workflow_1_guide_hosted": {
                "name": "Hosted Fork & Pull Request",
                "command": "git push --set-upstream origin topic",
                "precondition": "Secondary hosted fork repository with write access",
                "ref_state": "Creates refs/remotes/origin/topic and sets upstream tracking @{u}",
                "worktree_state": "Clean working tree; no local patch files created",
                "commit_state": "Commit ID preserved identically on remote fork",
            },
            "workflow_2_second_command": {
                "name": "Patch Export & git am",
                "command": "git format-patch -1 topic && git am <patch>",
                "precondition": "Local repository only; no remote fork or network required",
                "ref_state": "No remote tracking ref created; local refs unchanged",
                "worktree_state": "Untracked patch file (0001-*.patch) in working tree",
                "commit_state": "Maintainer creates new commit ID with identical tree hash and author, but maintainer committer",
            },
        },
    }

    with open(os.path.join(work_dir, "inputs.json"), "w") as f:
        json.dump(inputs_data, f, indent=2)

    # Execute Run 1 in temporary directory
    with tempfile.TemporaryDirectory(prefix="gfr_t036_run1_") as td1:
        run1 = run_full_check(td1)

    # Execute Run 2 in temporary directory
    with tempfile.TemporaryDirectory(prefix="gfr_t036_run2_") as td2:
        run2 = run_full_check(td2)

    # Cross-run deterministic assertions
    assert run1["fixture"]["commit_a_tree"] == run2["fixture"]["commit_a_tree"]
    assert run1["fixture"]["commit_b_tree"] == run2["fixture"]["commit_b_tree"]
    assert run1["fixture"]["commit_c_tree"] == run2["fixture"]["commit_c_tree"]
    assert run1["fixture"]["commit_d_tree"] == run2["fixture"]["commit_d_tree"]
    assert run1["w1"]["tracking_ref"] == run2["w1"]["tracking_ref"] == "origin/topic"
    assert run1["w1"]["patch_files_count"] == run2["w1"]["patch_files_count"] == 0
    assert run1["w2"]["has_tracking_ref"] == run2["w2"]["has_tracking_ref"] is False
    assert run1["w2"]["am_tree_hash"] == run2["w2"]["am_tree_hash"] == run1["fixture"]["commit_d_tree"]

    # Results documentation
    results_data = {
        "status": "PASS",
        "assertions_verified": [
            {
                "fact": "Workflow 1 (Fork & PR) configures remote tracking ref origin/topic pointing to topic commit",
                "expected_tracking_ref": "origin/topic",
                "actual_tracking_ref": run1["w1"]["tracking_ref"],
                "passed": True,
            },
            {
                "fact": "Workflow 1 (Fork & PR) preserves clean working tree with 0 patch files generated",
                "expected_patch_count": 0,
                "actual_patch_count": run1["w1"]["patch_files_count"],
                "passed": True,
            },
            {
                "fact": "Workflow 2 (format-patch) does not create any remote tracking ref",
                "expected_has_tracking": False,
                "actual_has_tracking": run1["w2"]["has_tracking_ref"],
                "passed": True,
            },
            {
                "fact": "Workflow 2 (format-patch) produces untracked patch file in contributor working tree",
                "expected_in_status": f"?? {run1['w2']['patch_filename']}",
                "actual_status": run1["w2"]["status_output"],
                "passed": True,
            },
            {
                "fact": "Workflow 2 maintainer application (git am) produces tree identical to contributor topic tree",
                "expected_tree": run1["fixture"]["commit_d_tree"],
                "actual_applied_tree": run1["w2"]["am_tree_hash"],
                "passed": True,
            },
            {
                "fact": "Workflow 2 maintainer application preserves author but records maintainer as committer",
                "expected_author": "Course Student <student@example.invalid>",
                "actual_author": run1["w2"]["am_author"],
                "expected_committer": "Course Maintainer <maintainer@example.invalid>",
                "actual_committer": run1["w2"]["am_committer"],
                "passed": True,
            },
            {
                "fact": "Two independent runs across separate temporary directories produce identical trees and states",
                "expected_tree": run1["fixture"]["commit_d_tree"],
                "actual_tree": run2["fixture"]["commit_d_tree"],
                "passed": True,
            },
        ],
        "workflow_comparison_summary": {
            "fixture_topic_commit": run1["fixture"]["commit_d_hash"],
            "fixture_topic_tree": run1["fixture"]["commit_d_tree"],
            "workflow_1_fork_pr": {
                "remote_tracking_ref": run1["w1"]["tracking_ref"],
                "remote_fork_commit": run1["w1"]["remote_ref_hash"],
                "working_tree_clean": run1["w1"]["status_output"] == "",
            },
            "workflow_2_format_patch": {
                "patch_file": run1["w2"]["patch_filename"],
                "applied_commit_hash": run1["w2"]["am_commit_hash"],
                "applied_tree_hash": run1["w2"]["am_tree_hash"],
                "applied_author": run1["w2"]["am_author"],
                "applied_committer": run1["w2"]["am_committer"],
            },
        },
    }

    with open(os.path.join(work_dir, "results.json"), "w") as f:
        json.dump(results_data, f, indent=2)

    log_message = (
        "All assertions PASSED successfully across two independent temporary directory runs!\n"
        f"Fixture Topic Commit: {run1['fixture']['commit_d_hash']}\n"
        f"Fixture Topic Tree:   {run1['fixture']['commit_d_tree']}\n"
        "Workflow 1 (Fork + PR): Configured remote tracking ref 'origin/topic', worktree clean.\n"
        f"Workflow 2 (format-patch + am): Created '{run1['w2']['patch_filename']}',\n"
        f"  maintainer applied tree {run1['w2']['am_tree_hash']} matches topic tree.\n"
        f"  author preserved: '{run1['w2']['am_author']}', committer: '{run1['w2']['am_committer']}'.\n"
    )

    with open(os.path.join(work_dir, "run_check.log"), "w") as f:
        f.write(log_message)

    print(log_message)


if __name__ == "__main__":
    main()
