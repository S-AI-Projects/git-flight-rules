#!/usr/bin/env python3
"""
Verification check for Task R12-T033:
Recovery exercise for "I rebased, but I don't want to force push" in git-flight-rules.

Verifies:
1. Setup of a temporary repository with branch main, author Course Student <student@example.invalid>,
   and three commits:
   - Commit A creates notes.txt with "alpha\n"
   - Commit B appends "beta\n" to notes.txt
   - Branch topic created at commit B
   - Commit C adds todo.txt with "one\n"
   - Local bare repository used as remote with file:// URL
2. Pre-rebase recovery point capture:
   - Topic branch commit hash and tree hash at commit B
   - Working tree file contents (notes.txt: "alpha\nbeta\n", todo.txt absent)
3. Demonstration of reversible mistake using command anchors:
   - git checkout topic
   - git rebase main
   - Topic branch moved to commit C, introducing todo.txt and rewriting history
4. Recovery of original file/commit state using documented Git mechanism:
   - ORIG_HEAD and reflog (topic@{1}) capture pre-rebase recovery point
   - git reset --hard ORIG_HEAD restores topic branch to commit B
5. Verification of state assertions:
   - Recovered tree matches saved tree hash exactly
   - Recovered commit matches saved commit hash
   - File contents restored (notes.txt: "alpha\nbeta\n", todo.txt absent)
   - Working tree and index are clean
   - Main branch remains intact at commit C
6. Documentation of recovery boundaries:
   - Uncommitted working-tree and index modifications cannot be recovered by git reset --hard
   - Overwritten ORIG_HEAD or expired reflog entries cannot be recovered by ORIG_HEAD
7. Runs twice in separate temporary directories with identical tree hashes.
8. Saves inputs, results, and tool versions in work/R12-T033/.
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


def setup_and_run(base_dir):
    """
    Sets up the repository, executes the rebase mistake, runs the recovery,
    and returns captured states and assertions.
    """
    bare_repo = os.path.join(base_dir, "remote.git")
    work_repo = os.path.join(base_dir, "workdir")

    # Step 1: Initialize local bare repository
    run_cmd(["git", "init", "--bare", "-b", "main", bare_repo])

    # Step 2: Initialize working repository with default branch main
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

    # Create branch topic at commit B
    run_cmd(["git", "branch", "topic"], cwd=work_repo)

    # Save recovery point for branch topic at commit B
    saved_topic_commit = run_cmd(["git", "rev-parse", "topic"], cwd=work_repo)
    saved_topic_tree = run_cmd(["git", "rev-parse", "topic^{tree}"], cwd=work_repo)

    # Commit C: adds todo.txt with "one\n"
    todo_path = os.path.join(work_repo, "todo.txt")
    with open(todo_path, "w") as f:
        f.write("one\n")
    run_cmd(["git", "add", "todo.txt"], cwd=work_repo)
    run_cmd(["git", "commit", "-m", "Commit C: add todo.txt"], cwd=work_repo)
    commit_c_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=work_repo)
    commit_c_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=work_repo)

    # Add remote
    run_cmd(["git", "remote", "add", "origin", f"file://{bare_repo}"], cwd=work_repo)

    # Verify initial topic state before mistake
    with open(notes_path, "r") as f:
        notes_before_rebase = f.read()
    todo_exists_before = os.path.exists(todo_path)

    # Command anchors: demonstrate rebase mistake
    # (main)$ git checkout topic
    run_cmd(["git", "checkout", "topic"], cwd=work_repo)
    # (topic)$ git rebase main
    rebase_out = run_cmd(["git", "rebase", "main"], cwd=work_repo)

    # State immediately after rebase (the mistake)
    rebased_topic_commit = run_cmd(["git", "rev-parse", "topic"], cwd=work_repo)
    rebased_topic_tree = run_cmd(["git", "rev-parse", "topic^{tree}"], cwd=work_repo)
    orig_head_ref = run_cmd(["git", "rev-parse", "ORIG_HEAD"], cwd=work_repo)
    reflog_prev_ref = run_cmd(["git", "rev-parse", "topic@{1}"], cwd=work_repo)
    todo_exists_after_rebase = os.path.exists(todo_path)

    # Perform documented recovery: git reset --hard ORIG_HEAD
    recovery_out = run_cmd(["git", "reset", "--hard", "ORIG_HEAD"], cwd=work_repo)

    # State after recovery
    recovered_topic_commit = run_cmd(["git", "rev-parse", "topic"], cwd=work_repo)
    recovered_topic_tree = run_cmd(["git", "rev-parse", "topic^{tree}"], cwd=work_repo)
    with open(notes_path, "r") as f:
        recovered_notes_content = f.read()
    todo_exists_after_recovery = os.path.exists(todo_path)
    status_porcelain_after = run_cmd(["git", "status", "--porcelain"], cwd=work_repo)
    main_commit_after = run_cmd(["git", "rev-parse", "main"], cwd=work_repo)

    state = {
        "bare_repo": bare_repo,
        "work_repo": work_repo,
        "commit_a_hash": commit_a_hash,
        "commit_a_tree": commit_a_tree,
        "commit_b_hash": commit_b_hash,
        "commit_b_tree": commit_b_tree,
        "commit_c_hash": commit_c_hash,
        "commit_c_tree": commit_c_tree,
        "saved_topic_commit": saved_topic_commit,
        "saved_topic_tree": saved_topic_tree,
        "notes_before_rebase": notes_before_rebase,
        "todo_exists_before": todo_exists_before,
        "rebase_out": rebase_out,
        "rebased_topic_commit": rebased_topic_commit,
        "rebased_topic_tree": rebased_topic_tree,
        "orig_head_ref": orig_head_ref,
        "reflog_prev_ref": reflog_prev_ref,
        "todo_exists_after_rebase": todo_exists_after_rebase,
        "recovery_out": recovery_out,
        "recovered_topic_commit": recovered_topic_commit,
        "recovered_topic_tree": recovered_topic_tree,
        "recovered_notes_content": recovered_notes_content,
        "todo_exists_after_recovery": todo_exists_after_recovery,
        "status_porcelain_after": status_porcelain_after,
        "main_commit_after": main_commit_after,
    }
    return state


def assert_state_facts(state):
    """Assert meaningful state facts verifying the mistake and successful recovery."""
    # State Fact 1: ORIG_HEAD and reflog topic@{1} capture the pre-rebase commit B
    assert state["orig_head_ref"] == state["saved_topic_commit"] == state["commit_b_hash"], (
        f"ORIG_HEAD ({state['orig_head_ref']}) does not match saved commit B ({state['commit_b_hash']})"
    )
    assert state["reflog_prev_ref"] == state["saved_topic_commit"], (
        f"topic@{{1}} does not match saved commit B"
    )

    # State Fact 2: The rebase moved topic to commit C (altering tree and introducing todo.txt)
    assert state["rebased_topic_commit"] == state["commit_c_hash"], (
        "Rebase should have advanced topic to commit C"
    )
    assert state["rebased_topic_tree"] == state["commit_c_tree"], (
        "Rebase tree should match commit C tree"
    )
    assert state["todo_exists_after_rebase"] == True, (
        "todo.txt should have been present after rebase onto main"
    )

    # State Fact 3: Recovered tree hash matches saved tree hash at commit B exactly
    assert state["recovered_topic_tree"] == state["saved_topic_tree"], (
        f"Recovered tree ({state['recovered_topic_tree']}) does not match saved tree ({state['saved_topic_tree']})"
    )
    assert state["recovered_topic_commit"] == state["saved_topic_commit"], (
        f"Recovered commit ({state['recovered_topic_commit']}) does not match saved commit ({state['saved_topic_commit']})"
    )

    # State Fact 4: Recovered file contents match pre-rebase state
    assert state["recovered_notes_content"] == "alpha\nbeta\n", (
        f"Recovered notes.txt does not match: '{state['recovered_notes_content']}'"
    )
    assert state["todo_exists_after_recovery"] == False, (
        "todo.txt should not exist after recovery"
    )

    # State Fact 5: Working tree and index are clean after recovery
    assert state["status_porcelain_after"] == "", (
        f"Working tree not clean after recovery: {state['status_porcelain_after']}"
    )

    # State Fact 6: Branch main is untouched and remains at commit C
    assert state["main_commit_after"] == state["commit_c_hash"], (
        f"Branch main was altered: {state['main_commit_after']}"
    )


def main():
    work_dir = os.path.dirname(os.path.abspath(__file__))

    # Capture tool versions
    git_ver = run_cmd(["git", "--version"])
    py_ver = sys.version.replace("\n", " ")
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"

    tool_versions = {
        "git_version": git_ver,
        "python_version": py_ver,
        "os_info": os_info,
    }

    with open(os.path.join(work_dir, "tool_versions.json"), "w") as f:
        json.dump(tool_versions, f, indent=2)

    with open(os.path.join(work_dir, "tool_versions.txt"), "w") as f:
        f.write(f"Git Version: {git_ver}\n")
        f.write(f"Python Version: {py_ver}\n")
        f.write(f"OS Info: {os_info}\n")

    # Save inputs
    inputs_data = {
        "task": "R12-T033",
        "guide_section": "I rebased, but I don't want to force push",
        "repository_author": {
            "name": "Course Student",
            "email": "student@example.invalid",
        },
        "default_branch": "main",
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
        "command_anchors": [
            "(main)$ git checkout my-branch",
            "(my-branch)$ git rebase -i main",
            "(my-branch)$ git checkout main",
        ],
        "demonstrated_mistake": "Unwanted rebase of topic onto main",
        "recovery_mechanism": "git reset --hard ORIG_HEAD (or git reset --hard topic@{1})",
        "unrecoverable_by_method": [
            "Uncommitted working tree modifications present when reset --hard was executed",
            "Unstaged file edits not tracked in commits or stash",
            "Reflog entries expired past gc.reflogExpire",
            "ORIG_HEAD if subsequent reset/merge/rebase has overwritten it",
        ],
    }

    with open(os.path.join(work_dir, "inputs.json"), "w") as f:
        json.dump(inputs_data, f, indent=2)

    # Run 1 in temporary directory 1
    with tempfile.TemporaryDirectory(prefix="gfr_rebase_rec1_") as td1:
        state1 = setup_and_run(td1)
        assert_state_facts(state1)

    # Run 2 in temporary directory 2
    with tempfile.TemporaryDirectory(prefix="gfr_rebase_rec2_") as td2:
        state2 = setup_and_run(td2)
        assert_state_facts(state2)

    # Cross-run consistency assertions
    assert state1["commit_a_tree"] == state2["commit_a_tree"], "Tree hashes for commit A must match"
    assert state1["commit_b_tree"] == state2["commit_b_tree"], "Tree hashes for commit B must match"
    assert state1["commit_c_tree"] == state2["commit_c_tree"], "Tree hashes for commit C must match"
    assert state1["saved_topic_tree"] == state2["saved_topic_tree"], "Saved topic trees must match"
    assert state1["recovered_topic_tree"] == state2["recovered_topic_tree"], "Recovered trees must match"
    assert state1["recovered_notes_content"] == state2["recovered_notes_content"] == "alpha\nbeta\n"
    assert state1["todo_exists_after_recovery"] == state2["todo_exists_after_recovery"] == False

    # Save results
    results_data = {
        "status": "PASS",
        "assertions_verified": [
            {
                "fact": "ORIG_HEAD captures pre-rebase commit B",
                "expected": state1["saved_topic_commit"],
                "actual": state1["orig_head_ref"],
                "passed": True,
            },
            {
                "fact": "topic@{1} captures pre-rebase commit B",
                "expected": state1["saved_topic_commit"],
                "actual": state1["reflog_prev_ref"],
                "passed": True,
            },
            {
                "fact": "Rebase advanced topic to commit C (demonstrating reversible mistake)",
                "expected": state1["commit_c_hash"],
                "actual": state1["rebased_topic_commit"],
                "passed": True,
            },
            {
                "fact": "Recovered topic tree matches saved tree hash at commit B exactly",
                "expected": state1["saved_topic_tree"],
                "actual": state1["recovered_topic_tree"],
                "passed": True,
            },
            {
                "fact": "Recovered topic commit matches saved commit B",
                "expected": state1["saved_topic_commit"],
                "actual": state1["recovered_topic_commit"],
                "passed": True,
            },
            {
                "fact": "Recovered notes.txt content matches pre-rebase content ('alpha\\nbeta\\n')",
                "expected": "alpha\nbeta\n",
                "actual": state1["recovered_notes_content"],
                "passed": True,
            },
            {
                "fact": "todo.txt absent on recovered topic branch",
                "expected": False,
                "actual": state1["todo_exists_after_recovery"],
                "passed": True,
            },
            {
                "fact": "Working tree and index are clean after recovery",
                "expected": "",
                "actual": state1["status_porcelain_after"],
                "passed": True,
            },
            {
                "fact": "Branch main is untouched and remains at commit C",
                "expected": state1["commit_c_hash"],
                "actual": state1["main_commit_after"],
                "passed": True,
            },
            {
                "fact": "Two independent runs across separate temporary directories match identical tree and state recovery",
                "expected": True,
                "actual": True,
                "passed": True,
            },
        ],
        "recovery_point": {
            "saved_commit": state1["saved_topic_commit"],
            "saved_tree": state1["saved_topic_tree"],
            "orig_head": state1["orig_head_ref"],
            "reflog_entry": state1["reflog_prev_ref"],
        },
        "recovered_state": {
            "commit": state1["recovered_topic_commit"],
            "tree": state1["recovered_topic_tree"],
            "notes_txt": state1["recovered_notes_content"],
            "todo_txt_exists": state1["todo_exists_after_recovery"],
            "status_porcelain": state1["status_porcelain_after"],
        },
        "unrecoverable_boundaries": [
            "Uncommitted working tree changes present at the time of reset --hard",
            "Unstaged file edits never captured by Git commits or stash",
            "Reflog entries expired or garbage-collected past gc.reflogExpire",
            "ORIG_HEAD overwritten by subsequent rebase/merge/reset commands",
        ],
    }

    with open(os.path.join(work_dir, "results.json"), "w") as f:
        json.dump(results_data, f, indent=2)

    print("All assertions PASSED successfully across two independent temporary directory runs!")
    print(f"Pre-rebase topic commit: {state1['saved_topic_commit']}")
    print(f"Pre-rebase topic tree:   {state1['saved_topic_tree']}")
    print(f"Rebased topic commit:    {state1['rebased_topic_commit']}")
    print(f"ORIG_HEAD reference:     {state1['orig_head_ref']}")
    print(f"Recovered topic commit:  {state1['recovered_topic_commit']}")
    print(f"Recovered topic tree:    {state1['recovered_topic_tree']}")
    print("Tree hash verification: EXACT MATCH")


if __name__ == "__main__":
    main()
