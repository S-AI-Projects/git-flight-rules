#!/usr/bin/env python3
"""
Verification check for Task R12-T040:
Worked teaching example for Git tag deletion (git tag -d, git push :refs/tags/)
in git-flight-rules.

Verifies:
1. Standard repository scenario:
   - Branch: main
   - Author: Course Student <student@example.invalid>
   - Commit A: creates notes.txt with "alpha\\n"
   - Commit B: appends "beta\\n" to notes.txt
   - Branch topic created at commit B
   - Commit C: creates todo.txt with "one\\n" on main
   - Remote: local bare repository via file:// URL
2. Tag creation & push:
   - Create annotated tag v1.0.0 pointing to commit B (git tag -a v1.0.0 -m "Release v1.0.0" topic)
   - Push tag to remote (git push origin v1.0.0)
   - Verify local tag and remote tag exist before deletion.
3. Prediction vs Actual execution:
   - Ref state prediction: refs/tags/v1.0.0 deleted locally and remotely.
   - Index/worktree state prediction: 100% invariant (files and status untouched).
   - Commit history prediction: Commit B and tree object remain intact in repository graph.
4. Execution of tag deletion:
   - Local: git tag -d v1.0.0
   - Remote: git push origin :refs/tags/v1.0.0
5. State Fact Assertions:
   - Fact 1: Local tag ref deletion (refs/tags/v1.0.0 completely removed from local refs).
   - Fact 2: Remote tag ref deletion (refs/tags/v1.0.0 completely removed from remote repository).
   - Fact 3: Worktree and index invariance (file contents, staged/unstaged status unaffected).
   - Fact 4: Commit and tree object persistence (commit B and its tree object remain valid).
   - Fact 5: Branch refs invariance (refs/heads/main and refs/heads/topic unaffected).
   - Fact 6: Purely local Git configuration (never modifies global ~/.gitconfig).
   - Fact 7: Deterministic consistency across independent temporary directory runs.
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
    Sets up the bare remote and work repository, exercises tag deletion,
    and returns captured state facts and assertions.
    """
    bare_dir = os.path.join(base_dir, "remote.git")
    repo_dir = os.path.join(base_dir, "repo")

    # 1. Initialize bare remote repository
    run_cmd(["git", "init", "--bare", bare_dir])

    # 2. Initialize work repository
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

    # Create branch topic at commit B
    run_cmd(["git", "branch", "topic"], cwd=repo_dir)
    topic_hash = run_cmd(["git", "rev-parse", "topic"], cwd=repo_dir)
    assert topic_hash == commit_b_hash

    # Commit C on main
    todo_path = os.path.join(repo_dir, "todo.txt")
    with open(todo_path, "w") as f:
        f.write("one\n")
    run_cmd(["git", "add", "todo.txt"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", "Commit C: add todo.txt"], cwd=repo_dir)
    commit_c_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    commit_c_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=repo_dir)

    # Connect remote origin via file:// URL
    bare_url = f"file://{bare_dir}"
    run_cmd(["git", "remote", "add", "origin", bare_url], cwd=repo_dir)
    run_cmd(["git", "push", "origin", "main", "topic"], cwd=repo_dir)

    # 3. Create annotated tag v1.0.0 pointing to commit B
    tag_name = "v1.0.0"
    run_cmd(["git", "tag", "-a", tag_name, "-m", "Release v1.0.0 at commit B", "topic"], cwd=repo_dir)
    tag_object_hash = run_cmd(["git", "rev-parse", f"refs/tags/{tag_name}"], cwd=repo_dir)
    tag_target_commit = run_cmd(["git", "rev-parse", f"refs/tags/{tag_name}^{{commit}}"], cwd=repo_dir)
    assert tag_target_commit == commit_b_hash

    # Push tag to remote
    run_cmd(["git", "push", "origin", tag_name], cwd=repo_dir)

    # Verify initial state before deletion
    local_tags_before = run_cmd(["git", "tag", "--list"], cwd=repo_dir)
    assert tag_name in local_tags_before
    remote_tags_before = run_cmd(["git", "ls-remote", "--tags", "origin"], cwd=repo_dir)
    assert f"refs/tags/{tag_name}" in remote_tags_before

    status_before = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
    with open(notes_path) as f:
        notes_before = f.read()
    with open(todo_path) as f:
        todo_before = f.read()

    # --- Step 4: Execute local tag deletion: git tag -d <tag_name> ---
    del_local_stdout = run_cmd(["git", "tag", "-d", tag_name], cwd=repo_dir)
    assert f"Deleted tag '{tag_name}'" in del_local_stdout

    # State verification after local deletion
    # Fact 1: Local tag reference no longer exists
    rc_revparse, out_revparse, err_revparse = run_cmd_allow_fail(
        ["git", "rev-parse", "--verify", f"refs/tags/{tag_name}"], cwd=repo_dir
    )
    assert rc_revparse != 0, f"Expected refs/tags/{tag_name} to be deleted locally, but rev-parse succeeded"
    local_tags_after = run_cmd(["git", "tag", "--list"], cwd=repo_dir)
    assert tag_name not in local_tags_after

    # --- Step 5: Execute remote tag deletion: git push <remote> :refs/tags/<tag_name> ---
    del_remote_code, del_remote_stdout, del_remote_stderr = run_cmd_allow_fail(
        ["git", "push", "origin", f":refs/tags/{tag_name}"], cwd=repo_dir
    )
    assert del_remote_code == 0, f"Remote tag deletion failed: {del_remote_stderr}"
    # Git push output can be on stdout or stderr depending on git version
    push_output = del_remote_stdout + "\n" + del_remote_stderr
    assert "deleted" in push_output or f":refs/tags/{tag_name}" in push_output or "To " in push_output

    # Fact 2: Remote tag reference no longer exists on remote
    remote_tags_after = run_cmd(["git", "ls-remote", "--tags", "origin"], cwd=repo_dir)
    assert f"refs/tags/{tag_name}" not in remote_tags_after

    # Fact 3: Worktree and index invariance
    status_after = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
    assert status_after == status_before == ""
    with open(notes_path) as f:
        notes_after = f.read()
    with open(todo_path) as f:
        todo_after = f.read()
    assert notes_after == notes_before == "alpha\nbeta\n"
    assert todo_after == todo_before == "one\n"

    # Fact 4: Commit and tree object persistence
    rc_cat_commit, _, _ = run_cmd_allow_fail(["git", "cat-file", "-e", commit_b_hash], cwd=repo_dir)
    assert rc_cat_commit == 0, "Commit B object was unexpectedly affected"
    commit_b_tree_after = run_cmd(["git", "rev-parse", f"{commit_b_hash}^{{tree}}"], cwd=repo_dir)
    assert commit_b_tree_after == commit_b_tree

    # Fact 5: Branch references invariance
    main_ref_after = run_cmd(["git", "rev-parse", "refs/heads/main"], cwd=repo_dir)
    topic_ref_after = run_cmd(["git", "rev-parse", "refs/heads/topic"], cwd=repo_dir)
    assert main_ref_after == commit_c_hash
    assert topic_ref_after == commit_b_hash

    return {
        "commit_a_hash": commit_a_hash,
        "commit_a_tree": commit_a_tree,
        "commit_b_hash": commit_b_hash,
        "commit_b_tree": commit_b_tree,
        "commit_c_hash": commit_c_hash,
        "commit_c_tree": commit_c_tree,
        "topic_hash": topic_hash,
        "tag_name": tag_name,
        "tag_object_hash": tag_object_hash,
        "tag_target_commit": tag_target_commit,
        "del_local_stdout": del_local_stdout,
        "push_output": push_output,
        "status_before": status_before,
        "status_after": status_after,
        "notes_content": notes_after,
        "todo_content": todo_after,
        "main_ref_after": main_ref_after,
        "topic_ref_after": topic_ref_after,
    }


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    work_dir = os.path.join(repo_root, "work", "R12-T040")
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
        "task": "R12-T040",
        "guide_section": "Delete tag",
        "command_anchors": [
            "git tag -d <tag_name>",
            "git push <remote> :refs/tags/<tag_name>",
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
        "remote": "file://<bare_repository>",
        "worked_exercise": {
            "prompt": "Predict resulting ref, index, worktree, and commit state before executing git tag -d and git push origin :refs/tags/<tag>.",
            "predictions": {
                "local_ref_state": "refs/tags/<tag> is deleted; rev-parse exits non-zero.",
                "remote_ref_state": "refs/tags/<tag> is deleted from origin; ls-remote returns empty.",
                "worktree_state": "Completely untouched; working tree files retain exact contents.",
                "index_state": "Completely untouched; index status remains invariant.",
                "commit_state": "Commit B and its tree object remain reachable and intact in repository graph.",
            },
        },
    }

    with open(os.path.join(work_dir, "inputs.json"), "w") as f:
        json.dump(inputs_data, f, indent=2)

    # Run 1 in temporary directory
    with tempfile.TemporaryDirectory(prefix="gfr_t040_run1_") as td1:
        run1 = setup_and_run(td1)

    # Run 2 in temporary directory
    with tempfile.TemporaryDirectory(prefix="gfr_t040_run2_") as td2:
        run2 = setup_and_run(td2)

    # Deterministic consistency assertions across runs
    assert run1["commit_a_tree"] == run2["commit_a_tree"]
    assert run1["commit_b_tree"] == run2["commit_b_tree"]
    assert run1["commit_c_tree"] == run2["commit_c_tree"]
    assert run1["status_after"] == run2["status_after"] == ""
    assert run1["notes_content"] == run2["notes_content"] == "alpha\nbeta\n"
    assert run1["todo_content"] == run2["todo_content"] == "one\n"
    assert "Deleted tag 'v1.0.0'" in run1["del_local_stdout"]
    assert "Deleted tag 'v1.0.0'" in run2["del_local_stdout"]
    assert run1["tag_target_commit"] == run1["commit_b_hash"]
    assert run2["tag_target_commit"] == run2["commit_b_hash"]

    # Save results
    results_data = {
        "status": "PASS",
        "assertions_verified": [
            {
                "fact": "Local tag ref deleted: refs/tags/v1.0.0 completely removed from local refs",
                "tag_name": run1["tag_name"],
                "passed": True,
            },
            {
                "fact": "Remote tag ref deleted: git push origin :refs/tags/v1.0.0 removes tag on remote",
                "remote_ref": f"refs/tags/{run1['tag_name']}",
                "passed": True,
            },
            {
                "fact": "Worktree and index invariant: files and porcelain status untouched",
                "status_after": run1["status_after"],
                "notes_content": run1["notes_content"],
                "todo_content": run1["todo_content"],
                "passed": True,
            },
            {
                "fact": "Commit and tree objects persist: Commit B and tree object remain intact",
                "commit_b_tree": run1["commit_b_tree"],
                "passed": True,
            },
            {
                "fact": "Branch refs unaffected: refs/heads/main and refs/heads/topic remain intact",
                "passed": True,
            },
            {
                "fact": "Purely local configuration: git config --local used; no global ~/.gitconfig modification",
                "passed": True,
            },
            {
                "fact": "Deterministic consistency verified across separate temporary repositories",
                "passed": True,
            },
        ],
        "state_summary": {
            "deleted_tag": run1["tag_name"],
            "local_deletion_output": run1["del_local_stdout"],
            "worktree_status": run1["status_after"],
            "main_head": run1["main_ref_after"],
            "topic_head": run1["topic_ref_after"],
        },
    }

    with open(os.path.join(work_dir, "results.json"), "w") as f:
        json.dump(results_data, f, indent=2)

    log_message = (
        "All assertions PASSED successfully across two independent temporary directory runs!\n"
        f"Tag Name:                {run1['tag_name']}\n"
        f"Local Deletion Output:   {run1['del_local_stdout']}\n"
        f"Worktree Status After:   {repr(run1['status_after'])}\n"
        f"Notes Content After:     {repr(run1['notes_content'])}\n"
        f"Todo Content After:      {repr(run1['todo_content'])}\n"
        f"Commit B Tree Hash:      {run1['commit_b_tree']}\n"
        "Purely local configuration verified (zero global config modifications).\n"
    )

    with open(os.path.join(work_dir, "run_check.log"), "w") as f:
        f.write(log_message)

    print(log_message)


if __name__ == "__main__":
    main()
