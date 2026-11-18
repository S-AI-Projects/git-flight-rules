#!/usr/bin/env python3
"""
Verification check for Task R12-T034:
Branch and remote semantics for "I want to move my unstaged edits to a different, existing branch"
in git-flight-rules.

Verifies:
1. Setup of a temporary repository with branch main, author Course Student <student@example.invalid>,
   and three commits:
   - Commit A creates notes.txt with "alpha\n"
   - Commit B appends "beta\n" to notes.txt
   - Branch topic created at commit B
   - Commit C adds todo.txt with "one\n"
   - Second local bare repository used as remote with file:// URL
2. Moving unstaged edits from topic to main:
   - Current branch is topic with unstaged edits in notes.txt ("alpha\nbeta\ngamma\n")
   - Command sequence:
     (topic)$ git stash
     (topic)$ git checkout main
     (main)$ git stash pop
3. Ref and branch semantics verification:
   - Intended ref changed: HEAD changed from refs/heads/topic to refs/heads/main
   - Unrelated refs stayed fixed:
     - refs/heads/topic remains at commit B
     - refs/heads/main remains at commit C
     - refs/remotes/origin/main remains at commit C
     - refs/remotes/origin/topic remains at commit B
   - refs/stash dropped after pop
   - Working tree on main contains unstaged edits in notes.txt
   - todo.txt on main remains at "one\n"
4. Runs twice across separate temporary directories with matching results.
5. Saves inputs, results, and tool versions to work/R12-T034/.
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
    Sets up the repository, moves unstaged edits from topic to main,
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

    # Commit C: adds todo.txt with "one\n"
    todo_path = os.path.join(work_repo, "todo.txt")
    with open(todo_path, "w") as f:
        f.write("one\n")
    run_cmd(["git", "add", "todo.txt"], cwd=work_repo)
    run_cmd(["git", "commit", "-m", "Commit C: add todo.txt"], cwd=work_repo)
    commit_c_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=work_repo)
    commit_c_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=work_repo)

    # Configure remote and push branches to bare remote
    run_cmd(["git", "remote", "add", "origin", f"file://{bare_repo}"], cwd=work_repo)
    run_cmd(["git", "push", "origin", "main"], cwd=work_repo)
    run_cmd(["git", "push", "origin", "topic"], cwd=work_repo)

    # Switch to branch topic
    run_cmd(["git", "checkout", "topic"], cwd=work_repo)

    # Record BEFORE state on topic
    before_head_ref = run_cmd(["git", "symbolic-ref", "HEAD"], cwd=work_repo)
    before_topic_commit = run_cmd(["git", "rev-parse", "refs/heads/topic"], cwd=work_repo)
    before_main_commit = run_cmd(["git", "rev-parse", "refs/heads/main"], cwd=work_repo)
    before_remote_main = run_cmd(["git", "rev-parse", "refs/remotes/origin/main"], cwd=work_repo)
    before_remote_topic = run_cmd(["git", "rev-parse", "refs/remotes/origin/topic"], cwd=work_repo)

    # Introduce unstaged edits on topic
    with open(notes_path, "a") as f:
        f.write("gamma\n")

    status_before_stash = run_cmd(["git", "status", "--porcelain"], cwd=work_repo)

    # Command anchor 1: git stash
    run_cmd(["git", "stash"], cwd=work_repo)
    status_after_stash = run_cmd(["git", "status", "--porcelain"], cwd=work_repo)
    stash_ref_exists = (subprocess.run(["git", "rev-parse", "--verify", "refs/stash"], cwd=work_repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0)

    # Command anchor 2: git checkout main
    run_cmd(["git", "checkout", "main"], cwd=work_repo)
    checkout_head_ref = run_cmd(["git", "symbolic-ref", "HEAD"], cwd=work_repo)

    # Command anchor 3: git stash pop
    pop_out = run_cmd(["git", "stash", "pop"], cwd=work_repo)

    # Record AFTER state on main
    after_head_ref = run_cmd(["git", "symbolic-ref", "HEAD"], cwd=work_repo)
    after_topic_commit = run_cmd(["git", "rev-parse", "refs/heads/topic"], cwd=work_repo)
    after_main_commit = run_cmd(["git", "rev-parse", "refs/heads/main"], cwd=work_repo)
    after_remote_main = run_cmd(["git", "rev-parse", "refs/remotes/origin/main"], cwd=work_repo)
    after_remote_topic = run_cmd(["git", "rev-parse", "refs/remotes/origin/topic"], cwd=work_repo)
    status_after_pop = run_cmd(["git", "status", "--porcelain"], cwd=work_repo)

    # Check stash dropped
    stash_dropped = (subprocess.run(["git", "rev-parse", "--verify", "refs/stash"], cwd=work_repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode != 0)

    with open(notes_path, "r") as f:
        notes_on_main = f.read()
    with open(todo_path, "r") as f:
        todo_on_main = f.read()

    state = {
        "bare_repo": bare_repo,
        "work_repo": work_repo,
        "commit_a_hash": commit_a_hash,
        "commit_a_tree": commit_a_tree,
        "commit_b_hash": commit_b_hash,
        "commit_b_tree": commit_b_tree,
        "commit_c_hash": commit_c_hash,
        "commit_c_tree": commit_c_tree,
        "before_head_ref": before_head_ref,
        "before_topic_commit": before_topic_commit,
        "before_main_commit": before_main_commit,
        "before_remote_main": before_remote_main,
        "before_remote_topic": before_remote_topic,
        "status_before_stash": status_before_stash,
        "status_after_stash": status_after_stash,
        "stash_ref_exists": stash_ref_exists,
        "checkout_head_ref": checkout_head_ref,
        "after_head_ref": after_head_ref,
        "after_topic_commit": after_topic_commit,
        "after_main_commit": after_main_commit,
        "after_remote_main": after_remote_main,
        "after_remote_topic": after_remote_topic,
        "status_after_pop": status_after_pop,
        "stash_dropped": stash_dropped,
        "notes_on_main": notes_on_main,
        "todo_on_main": todo_on_main,
    }
    return state


def assert_state_facts(state):
    """Assert meaningful state facts verifying ref changes and fixed refs."""
    # State Fact 1: Intended ref changed (HEAD switched from refs/heads/topic to refs/heads/main)
    assert state["before_head_ref"] == "refs/heads/topic", (
        f"Initial HEAD should be refs/heads/topic, got {state['before_head_ref']}"
    )
    assert state["after_head_ref"] == "refs/heads/main", (
        f"Final HEAD should be refs/heads/main, got {state['after_head_ref']}"
    )

    # State Fact 2: Unrelated local refs stayed completely fixed
    assert state["before_topic_commit"] == state["after_topic_commit"] == state["commit_b_hash"], (
        f"refs/heads/topic moved: before={state['before_topic_commit']}, after={state['after_topic_commit']}"
    )
    assert state["before_main_commit"] == state["after_main_commit"] == state["commit_c_hash"], (
        f"refs/heads/main moved: before={state['before_main_commit']}, after={state['after_main_commit']}"
    )

    # State Fact 3: Remote tracking refs stayed completely fixed (no remote push/fetch occurred)
    assert state["before_remote_main"] == state["after_remote_main"] == state["commit_c_hash"], (
        "Remote ref origin/main changed unexpectedly"
    )
    assert state["before_remote_topic"] == state["after_remote_topic"] == state["commit_b_hash"], (
        "Remote ref origin/topic changed unexpectedly"
    )

    # State Fact 4: Stash was popped and dropped
    assert state["stash_ref_exists"] == True, "refs/stash should have existed after stash"
    assert state["stash_dropped"] == True, "refs/stash should be dropped after stash pop"

    # State Fact 5: Working tree on main contains the moved unstaged edits
    assert "M notes.txt" in state["status_after_pop"], (
        f"Expected 'notes.txt' modified, got '{state['status_after_pop']}'"
    )
    assert state["notes_on_main"] == "alpha\nbeta\ngamma\n", (
        f"notes.txt content on main does not match: '{state['notes_on_main']}'"
    )
    assert state["todo_on_main"] == "one\n", (
        f"todo.txt content on main altered: '{state['todo_on_main']}'"
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
        "task": "R12-T034",
        "guide_section": "I want to move my unstaged edits to a different, existing branch",
        "repository_author": {
            "name": "Course Student",
            "email": "student@example.invalid",
        },
        "default_branch": "main",
        "source_branch": "topic",
        "target_branch": "main",
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
        "unstaged_edit_on_topic": {
            "file": "notes.txt",
            "edit": "append 'gamma\\n'",
        },
        "command_anchors": [
            "git stash",
            "git checkout my-branch",
            "git stash pop",
        ],
        "intended_ref_changed": "HEAD (from refs/heads/topic to refs/heads/main)",
        "unrelated_refs_fixed": [
            "refs/heads/topic",
            "refs/heads/main",
            "refs/remotes/origin/main",
            "refs/remotes/origin/topic",
        ],
    }

    with open(os.path.join(work_dir, "inputs.json"), "w") as f:
        json.dump(inputs_data, f, indent=2)

    # Run 1 in temporary directory 1
    with tempfile.TemporaryDirectory(prefix="gfr_move_edits_run1_") as td1:
        state1 = setup_and_run(td1)
        assert_state_facts(state1)

    # Run 2 in temporary directory 2
    with tempfile.TemporaryDirectory(prefix="gfr_move_edits_run2_") as td2:
        state2 = setup_and_run(td2)
        assert_state_facts(state2)

    # Cross-run consistency assertions
    assert state1["commit_a_tree"] == state2["commit_a_tree"]
    assert state1["commit_b_tree"] == state2["commit_b_tree"]
    assert state1["commit_c_tree"] == state2["commit_c_tree"]
    assert state1["notes_on_main"] == state2["notes_on_main"] == "alpha\nbeta\ngamma\n"
    assert state1["todo_on_main"] == state2["todo_on_main"] == "one\n"
    assert state1["status_after_pop"] == state2["status_after_pop"]
    assert "M notes.txt" in state1["status_after_pop"]
    assert state1["before_head_ref"] == state2["before_head_ref"] == "refs/heads/topic"
    assert state1["after_head_ref"] == state2["after_head_ref"] == "refs/heads/main"

    # Save results
    results_data = {
        "status": "PASS",
        "assertions_verified": [
            {
                "fact": "Intended ref changed: HEAD changed from refs/heads/topic to refs/heads/main",
                "expected": "refs/heads/main",
                "actual": state1["after_head_ref"],
                "passed": True,
            },
            {
                "fact": "Unrelated ref refs/heads/topic stayed fixed at Commit B",
                "expected": state1["commit_b_hash"],
                "actual": state1["after_topic_commit"],
                "passed": True,
            },
            {
                "fact": "Unrelated ref refs/heads/main stayed fixed at Commit C",
                "expected": state1["commit_c_hash"],
                "actual": state1["after_main_commit"],
                "passed": True,
            },
            {
                "fact": "Remote ref refs/remotes/origin/main stayed fixed at Commit C",
                "expected": state1["commit_c_hash"],
                "actual": state1["after_remote_main"],
                "passed": True,
            },
            {
                "fact": "Remote ref refs/remotes/origin/topic stayed fixed at Commit B",
                "expected": state1["commit_b_hash"],
                "actual": state1["after_remote_topic"],
                "passed": True,
            },
            {
                "fact": "refs/stash created during stash and dropped after pop",
                "expected": True,
                "actual": state1["stash_dropped"],
                "passed": True,
            },
            {
                "fact": "Working tree on main contains moved unstaged edits (M notes.txt)",
                "expected": " M notes.txt",
                "actual": state1["status_after_pop"],
                "passed": True,
            },
            {
                "fact": "notes.txt on main contains 'alpha\\nbeta\\ngamma\\n'",
                "expected": "alpha\nbeta\ngamma\n",
                "actual": state1["notes_on_main"],
                "passed": True,
            },
            {
                "fact": "todo.txt on main preserved as 'one\\n'",
                "expected": "one\n",
                "actual": state1["todo_on_main"],
                "passed": True,
            },
            {
                "fact": "Two independent runs across separate temporary directories match identical states",
                "expected": True,
                "actual": True,
                "passed": True,
            },
        ],
        "ref_transitions": {
            "HEAD": {
                "before": state1["before_head_ref"],
                "after": state1["after_head_ref"],
                "changed": True,
            },
            "refs/heads/topic": {
                "before": state1["before_topic_commit"],
                "after": state1["after_topic_commit"],
                "changed": False,
            },
            "refs/heads/main": {
                "before": state1["before_main_commit"],
                "after": state1["after_main_commit"],
                "changed": False,
            },
            "refs/remotes/origin/main": {
                "before": state1["before_remote_main"],
                "after": state1["after_remote_main"],
                "changed": False,
            },
            "refs/remotes/origin/topic": {
                "before": state1["before_remote_topic"],
                "after": state1["after_remote_topic"],
                "changed": False,
            },
        },
    }

    with open(os.path.join(work_dir, "results.json"), "w") as f:
        json.dump(results_data, f, indent=2)

    print("All assertions PASSED successfully across two independent temporary directory runs!")
    print(f"HEAD transitioned: {state1['before_head_ref']} -> {state1['after_head_ref']}")
    print(f"refs/heads/topic fixed at: {state1['after_topic_commit']}")
    print(f"refs/heads/main fixed at:  {state1['after_main_commit']}")
    print(f"Working tree status on main: {state1['status_after_pop']}")


if __name__ == "__main__":
    main()
