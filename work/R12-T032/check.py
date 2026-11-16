#!/usr/bin/env python3
"""
Verification check for Task R12-T032:
Before/after state diagram and explanation for "Stash with message" in git-flight-rules.

Verifies:
1. Setup of a temporary repository with branch main, author Course Student <student@example.invalid>,
   and three commits:
   - Commit A creates notes.txt with "alpha\n"
   - Commit B appends "beta\n" to notes.txt
   - Commit C adds todo.txt with "one\n"
   - Branch topic created at commit B
   - Second local bare repository used as remote with file:// URL
2. Preparation of staged and working-tree changes:
   - Staged change: append "two\n" to todo.txt and git add todo.txt
   - Working tree change: append "gamma\n" to notes.txt
3. Stash operation using command anchors:
   - git stash push -m "WIP on main"
   - git stash save "WIP on main"
4. Verification of state transitions:
   - Refs: refs/stash (stash@{0}) created; HEAD and branch refs (main, topic) unchanged.
   - Commit ancestry: refs/stash^1 == HEAD (commit C); refs/stash^2 == index commit recording staged state.
   - Index: staged modifications reverted to HEAD state (clean index).
   - Working tree: working tree modifications reverted to HEAD state (clean working tree).
   - Content: refs/stash^2 contains staged todo.txt; refs/stash contains working tree notes.txt.
5. Verification that setup runs twice in separate temporary directories with matching results.
6. Saves inputs, results, and tool versions to work/R12-T032/.
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


def setup_and_run(base_dir, stash_command="push"):
    """
    Sets up the repository, introduces staged and unstaged changes, runs stash,
    and returns captured state facts before and after the operation.
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

    # Add remote
    run_cmd(["git", "remote", "add", "origin", f"file://{bare_repo}"], cwd=work_repo)

    # Introduce staged change: append "two\n" to todo.txt and stage
    with open(todo_path, "a") as f:
        f.write("two\n")
    run_cmd(["git", "add", "todo.txt"], cwd=work_repo)

    # Introduce unstaged change: append "gamma\n" to notes.txt
    with open(notes_path, "a") as f:
        f.write("gamma\n")

    # Capture BEFORE state
    before_head = run_cmd(["git", "rev-parse", "HEAD"], cwd=work_repo)
    before_main = run_cmd(["git", "rev-parse", "refs/heads/main"], cwd=work_repo)
    before_topic = run_cmd(["git", "rev-parse", "refs/heads/topic"], cwd=work_repo)
    before_status = run_cmd(["git", "status", "--porcelain"], cwd=work_repo)
    before_diff_staged = run_cmd(["git", "diff", "--cached"], cwd=work_repo)
    before_diff_unstaged = run_cmd(["git", "diff"], cwd=work_repo)
    with open(notes_path, "r") as f:
        before_notes_content = f.read()
    with open(todo_path, "r") as f:
        before_todo_content = f.read()

    # Execute stash command anchor
    stash_msg_input = "WIP on main with message"
    if stash_command == "push":
        stash_output = run_cmd(["git", "stash", "push", "-m", stash_msg_input], cwd=work_repo)
    else:
        stash_output = run_cmd(["git", "stash", "save", stash_msg_input], cwd=work_repo)

    # Capture AFTER state
    after_head = run_cmd(["git", "rev-parse", "HEAD"], cwd=work_repo)
    after_main = run_cmd(["git", "rev-parse", "refs/heads/main"], cwd=work_repo)
    after_topic = run_cmd(["git", "rev-parse", "refs/heads/topic"], cwd=work_repo)
    after_status = run_cmd(["git", "status", "--porcelain"], cwd=work_repo)
    after_diff_staged = run_cmd(["git", "diff", "--cached"], cwd=work_repo)
    after_diff_unstaged = run_cmd(["git", "diff"], cwd=work_repo)
    with open(notes_path, "r") as f:
        after_notes_content = f.read()
    with open(todo_path, "r") as f:
        after_todo_content = f.read()

    # Inspect stash commit and ancestry
    stash_ref = run_cmd(["git", "rev-parse", "refs/stash"], cwd=work_repo)
    stash_parent1 = run_cmd(["git", "rev-parse", "refs/stash^1"], cwd=work_repo)
    stash_parent2 = run_cmd(["git", "rev-parse", "refs/stash^2"], cwd=work_repo)
    stash_commit_msg = run_cmd(["git", "log", "-1", "--format=%s", "refs/stash"], cwd=work_repo)
    stash_notes_content = run_cmd(["git", "show", "refs/stash:notes.txt"], cwd=work_repo, strip=False)
    stash_p2_todo_content = run_cmd(["git", "show", "refs/stash^2:todo.txt"], cwd=work_repo, strip=False)

    state = {
        "bare_repo": bare_repo,
        "work_repo": work_repo,
        "stash_command": stash_command,
        "commit_a_hash": commit_a_hash,
        "commit_a_tree": commit_a_tree,
        "commit_b_hash": commit_b_hash,
        "commit_b_tree": commit_b_tree,
        "commit_c_hash": commit_c_hash,
        "commit_c_tree": commit_c_tree,
        "before_head": before_head,
        "before_main": before_main,
        "before_topic": before_topic,
        "before_status": before_status,
        "before_diff_staged": before_diff_staged,
        "before_diff_unstaged": before_diff_unstaged,
        "before_notes_content": before_notes_content,
        "before_todo_content": before_todo_content,
        "stash_output": stash_output,
        "after_head": after_head,
        "after_main": after_main,
        "after_topic": after_topic,
        "after_status": after_status,
        "after_diff_staged": after_diff_staged,
        "after_diff_unstaged": after_diff_unstaged,
        "after_notes_content": after_notes_content,
        "after_todo_content": after_todo_content,
        "stash_ref": stash_ref,
        "stash_parent1": stash_parent1,
        "stash_parent2": stash_parent2,
        "stash_commit_msg": stash_commit_msg,
        "stash_notes_content": stash_notes_content,
        "stash_p2_todo_content": stash_p2_todo_content,
    }
    return state


def assert_state_facts(state):
    """Assert at least three meaningful state facts on the repository state transitions."""
    # State Fact 1: HEAD and branch refs (main, topic) are unchanged by the stash operation
    assert state["before_head"] == state["after_head"] == state["commit_c_hash"], (
        f"HEAD moved unexpectedly: before={state['before_head']}, after={state['after_head']}"
    )
    assert state["before_main"] == state["after_main"] == state["commit_c_hash"], (
        f"Branch ref main moved unexpectedly"
    )
    assert state["before_topic"] == state["after_topic"] == state["commit_b_hash"], (
        f"Branch ref topic moved unexpectedly"
    )

    # State Fact 2: Commit ancestry of refs/stash: parent 1 is HEAD (commit C), parent 2 is index commit
    assert state["stash_parent1"] == state["after_head"], (
        f"Stash parent 1 ({state['stash_parent1']}) does not equal HEAD ({state['after_head']})"
    )
    assert state["stash_parent2"] != state["after_head"], (
        "Stash parent 2 (index commit) should be a distinct commit recording staged changes"
    )

    # State Fact 3: Stash parent 2 contains the staged state (todo.txt with 'one\ntwo\n')
    assert state["stash_p2_todo_content"] == "one\ntwo\n", (
        f"Stash parent 2 does not contain expected staged todo.txt content: '{state['stash_p2_todo_content']}'"
    )

    # State Fact 4: refs/stash working tree commit contains unstaged state (notes.txt with 'alpha\nbeta\ngamma\n')
    assert state["stash_notes_content"] == "alpha\nbeta\ngamma\n", (
        f"Stash commit does not contain working tree notes.txt content: '{state['stash_notes_content']}'"
    )

    # State Fact 5: Working tree and index are reverted/reset to clean state matching Commit C
    assert state["after_status"] == "", (
        f"Working tree is not clean after stash: {state['after_status']}"
    )
    assert state["after_diff_staged"] == "", (
        f"Staged diff is not empty after stash"
    )
    assert state["after_diff_unstaged"] == "", (
        f"Unstaged diff is not empty after stash"
    )
    assert state["after_notes_content"] == "alpha\nbeta\n", (
        f"notes.txt in working tree not reverted to commit C/B state: '{state['after_notes_content']}'"
    )
    assert state["after_todo_content"] == "one\n", (
        f"todo.txt in working tree not reverted to commit C state: '{state['after_todo_content']}'"
    )

    # State Fact 6: The custom message is preserved in refs/stash
    assert "WIP on main with message" in state["stash_commit_msg"], (
        f"Stash message does not contain custom message: '{state['stash_commit_msg']}'"
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
        "task": "R12-T032",
        "guide_section": "Stash with message",
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
        "staged_change": {
            "file": "todo.txt",
            "action": "append 'two\\n' and git add todo.txt",
        },
        "working_tree_change": {
            "file": "notes.txt",
            "action": "append 'gamma\\n' (unstaged)",
        },
        "command_anchors": [
            "git stash push -m <message>",
            "git stash save <message>",
        ],
    }

    with open(os.path.join(work_dir, "inputs.json"), "w") as f:
        json.dump(inputs_data, f, indent=2)

    # Run 1: testing git stash push -m
    with tempfile.TemporaryDirectory(prefix="gfr_stash_run1_") as td1:
        state1 = setup_and_run(td1, stash_command="push")
        assert_state_facts(state1)

    # Run 2: testing git stash save (both command anchors verified across temporary directories)
    with tempfile.TemporaryDirectory(prefix="gfr_stash_run2_") as td2:
        state2 = setup_and_run(td2, stash_command="save")
        assert_state_facts(state2)

    # Cross-run consistency assertions
    assert state1["commit_a_tree"] == state2["commit_a_tree"], "Commit A tree hashes must match"
    assert state1["commit_b_tree"] == state2["commit_b_tree"], "Commit B tree hashes must match"
    assert state1["commit_c_tree"] == state2["commit_c_tree"], "Commit C tree hashes must match"
    assert state1["after_status"] == state2["after_status"] == "", "Clean status after stash must match"
    assert state1["after_notes_content"] == state2["after_notes_content"] == "alpha\nbeta\n"
    assert state1["after_todo_content"] == state2["after_todo_content"] == "one\n"
    assert state1["stash_p2_todo_content"] == state2["stash_p2_todo_content"] == "one\ntwo\n"
    assert state1["stash_notes_content"] == state2["stash_notes_content"] == "alpha\nbeta\ngamma\n"

    # Save results
    results_data = {
        "status": "PASS",
        "assertions_verified": [
            {
                "fact": "HEAD and branch ref main unchanged by stash (points to Commit C)",
                "expected": state1["commit_c_hash"],
                "actual": state1["after_head"],
                "passed": True,
            },
            {
                "fact": "Branch ref topic unchanged by stash (points to Commit B)",
                "expected": state1["commit_b_hash"],
                "actual": state1["after_topic"],
                "passed": True,
            },
            {
                "fact": "refs/stash parent 1 matches HEAD (Commit C)",
                "expected": state1["after_head"],
                "actual": state1["stash_parent1"],
                "passed": True,
            },
            {
                "fact": "refs/stash parent 2 (index commit) contains staged todo.txt ('one\\ntwo\\n')",
                "expected": "one\ntwo\n",
                "actual": state1["stash_p2_todo_content"],
                "passed": True,
            },
            {
                "fact": "refs/stash working tree commit contains unstaged notes.txt ('alpha\\nbeta\\ngamma\\n')",
                "expected": "alpha\nbeta\ngamma\n",
                "actual": state1["stash_notes_content"],
                "passed": True,
            },
            {
                "fact": "Working tree and index are reverted to clean state matching Commit C",
                "expected": "",
                "actual": state1["after_status"],
                "passed": True,
            },
            {
                "fact": "Stash commit message preserves custom message",
                "expected_substring": "WIP on main with message",
                "actual": state1["stash_commit_msg"],
                "passed": True,
            },
            {
                "fact": "Two independent runs across separate temporary directories match identical tree and state transitions",
                "expected": True,
                "actual": True,
                "passed": True,
            },
        ],
        "state_transitions": {
            "refs": {
                "HEAD": "Unchanged (points to Commit C)",
                "refs/heads/main": "Unchanged (points to Commit C)",
                "refs/heads/topic": "Unchanged (points to Commit B)",
                "refs/stash": f"Created (points to stash commit {state1['stash_ref']})",
            },
            "commit_ancestry": {
                "stash_commit": state1["stash_ref"],
                "parent_1_HEAD": state1["stash_parent1"],
                "parent_2_index": state1["stash_parent2"],
            },
            "index": {
                "before": "M  todo.txt (staged modification 'two\\n')",
                "after": "Clean (reverted to Commit C)",
            },
            "working_tree": {
                "before": " M notes.txt (unstaged modification 'gamma\\n')",
                "after": "Clean (reverted to Commit C)",
            },
        },
    }

    with open(os.path.join(work_dir, "results.json"), "w") as f:
        json.dump(results_data, f, indent=2)

    print("All assertions PASSED successfully across two independent temporary directory runs!")
    print(f"HEAD commit C: {state1['commit_c_hash']}")
    print(f"refs/stash: {state1['stash_ref']}")
    print(f"  Parent 1 (HEAD): {state1['stash_parent1']}")
    print(f"  Parent 2 (Index commit): {state1['stash_parent2']}")
    print(f"Index & Working Tree status after stash: clean ('{state1['after_status']}')")


if __name__ == "__main__":
    main()
