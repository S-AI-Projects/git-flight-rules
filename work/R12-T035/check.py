#!/usr/bin/env python3
"""
Verification check for Task R12-T035:
Quoting and path handling for "Clone all submodules" in git-flight-rules.

Verifies:
1. Setup of a temporary repository with branch main, author Course Student <student@example.invalid>,
   and three commits:
   - Commit A creates notes.txt with "alpha\n"
   - Commit B appends "beta\n" to notes.txt
   - Branch topic created at commit B
   - Commit C adds todo.txt with "one\n"
   - Submodule created with file "release notes.txt" containing "v1.0 release notes\n"
   - Submodule added to superproject at directory "sample data"
   - Remotes configured using local bare repositories with file:// URLs
2. Command anchor 1: git clone --recursive <url> "<destination with spaces>"
   - Preserves spaces in destination path and submodule path
   - Checks out submodule at "sample data" containing "release notes.txt"
3. Command anchor 2: git submodule update --init --recursive
   - Unquoted pathspec ("sample data" unquoted -> "sample" "data"):
     Fails with:
     error: pathspec 'sample' did not match any file(s) known to git
     error: pathspec 'data' did not match any file(s) known to git
   - Quoted pathspec with "--":
     git submodule update --init --recursive -- "sample data"
     Succeeds, initializes the submodule, and checks out "sample data/release notes.txt"
4. File path quoting with "release notes.txt":
   - Inside the submodule, unquoted "release notes.txt" (split into "release" and "notes.txt"):
     Fails with:
     error: pathspec 'release' did not match any file(s) known to git
     error: pathspec 'notes.txt' did not match any file(s) known to git
   - Quoted "release notes.txt" with "--":
     git checkout HEAD -- "release notes.txt"
     Succeeds and restores file content.
5. Filename versus revision ambiguity & disambiguation with "--":
   - Demonstrates that when a ref shares a name with a file (e.g. branch todo.txt), Git reports:
     fatal: ambiguous argument '...': both revision and filename
     Use '--' to separate paths from revisions, like this:
     'git <command> [<revision>...] -- [<file>...]'
   - Disambiguates pathspec using "--" (git log -- <file>, git checkout <rev> -- <file>)
6. Runs twice across separate temporary directories with matching results.
7. Saves inputs, results, and tool versions to work/R12-T035/.
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
    Sets up the repositories, exercises the submodule commands with spaces and quoting,
    and returns captured state facts and assertions.
    """
    sub_remote = os.path.join(base_dir, "submodule_remote.git")
    sub_work = os.path.join(base_dir, "submodule_work")
    super_remote = os.path.join(base_dir, "super_remote.git")
    super_work = os.path.join(base_dir, "super_work")

    # Step 1: Initialize submodule bare remote and working repo
    run_cmd(["git", "init", "--bare", "-b", "main", sub_remote])
    run_cmd(["git", "clone", f"file://{sub_remote}", sub_work])
    run_cmd(["git", "config", "user.name", "Course Student"], cwd=sub_work)
    run_cmd(["git", "config", "user.email", "student@example.invalid"], cwd=sub_work)
    run_cmd(["git", "config", "commit.gpgSign", "false"], cwd=sub_work)

    # Submodule initial commit with file "release notes.txt"
    sub_file = os.path.join(sub_work, "release notes.txt")
    with open(sub_file, "w") as f:
        f.write("v1.0 release notes\n")
    run_cmd(["git", "add", "release notes.txt"], cwd=sub_work)
    run_cmd(["git", "commit", "-m", "Initial submodule commit with release notes.txt"], cwd=sub_work)
    run_cmd(["git", "push", "origin", "main"], cwd=sub_work)
    submodule_commit_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=sub_work)

    # Step 2: Initialize superproject bare remote and working repo
    run_cmd(["git", "init", "--bare", "-b", "main", super_remote])
    run_cmd(["git", "clone", f"file://{super_remote}", super_work])
    run_cmd(["git", "config", "user.name", "Course Student"], cwd=super_work)
    run_cmd(["git", "config", "user.email", "student@example.invalid"], cwd=super_work)
    run_cmd(["git", "config", "commit.gpgSign", "false"], cwd=super_work)
    run_cmd(["git", "config", "protocol.file.allow", "always"], cwd=super_work)

    # Commit A: creates notes.txt with "alpha\n"
    notes_path = os.path.join(super_work, "notes.txt")
    with open(notes_path, "w") as f:
        f.write("alpha\n")
    run_cmd(["git", "add", "notes.txt"], cwd=super_work)
    run_cmd(["git", "commit", "-m", "Commit A: create notes.txt"], cwd=super_work)
    commit_a_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=super_work)
    commit_a_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=super_work)

    # Commit B: appends "beta\n"
    with open(notes_path, "a") as f:
        f.write("beta\n")
    run_cmd(["git", "add", "notes.txt"], cwd=super_work)
    run_cmd(["git", "commit", "-m", "Commit B: append beta"], cwd=super_work)
    commit_b_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=super_work)
    commit_b_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=super_work)

    # Create branch topic at Commit B
    run_cmd(["git", "branch", "topic"], cwd=super_work)

    # Commit C: adds todo.txt with "one\n"
    todo_path = os.path.join(super_work, "todo.txt")
    with open(todo_path, "w") as f:
        f.write("one\n")
    run_cmd(["git", "add", "todo.txt"], cwd=super_work)
    run_cmd(["git", "commit", "-m", "Commit C: add todo.txt"], cwd=super_work)
    commit_c_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=super_work)
    commit_c_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=super_work)

    # Add submodule at directory with spaces: "sample data"
    run_cmd(
        ["git", "-c", "protocol.file.allow=always", "submodule", "add", f"file://{sub_remote}", "sample data"],
        cwd=super_work,
    )
    run_cmd(["git", "commit", "-m", "Add submodule in sample data"], cwd=super_work)
    super_commit_hash = run_cmd(["git", "rev-parse", "HEAD"], cwd=super_work)
    super_tree_hash = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=super_work)
    submodule_gitlink = run_cmd(["git", "rev-parse", "HEAD:sample data"], cwd=super_work)
    submodule_tree = run_cmd(["git", "rev-parse", "HEAD^{tree}"], cwd=sub_work)

    # Push main and topic to super_remote
    run_cmd(["git", "push", "origin", "main"], cwd=super_work)
    run_cmd(["git", "push", "origin", "topic"], cwd=super_work)

    # -------------------------------------------------------------
    # Test 1: Command Anchor 1 - git clone --recursive
    # Clone superproject recursively into a destination path with spaces
    # -------------------------------------------------------------
    rec_clone_dir = os.path.join(base_dir, "cloned recursive with spaces")
    run_cmd(
        ["git", "-c", "protocol.file.allow=always", "clone", "--recursive", f"file://{super_remote}", rec_clone_dir]
    )
    rec_sub_file = os.path.join(rec_clone_dir, "sample data", "release notes.txt")
    assert os.path.exists(rec_sub_file), f"Expected file {rec_sub_file} does not exist"
    with open(rec_sub_file) as f:
        rec_file_content = f.read()
    assert rec_file_content == "v1.0 release notes\n"

    rec_sub_head = run_cmd(["git", "rev-parse", "HEAD"], cwd=os.path.join(rec_clone_dir, "sample data"))
    assert rec_sub_head == submodule_commit_hash

    # -------------------------------------------------------------
    # Test 2: Command Anchor 2 - git submodule update --init --recursive
    # Clone without submodules first
    # -------------------------------------------------------------
    std_clone_dir = os.path.join(base_dir, "cloned standard")
    run_cmd(["git", "clone", f"file://{super_remote}", std_clone_dir])

    # Verify submodule directory exists but is not yet populated
    std_sub_file = os.path.join(std_clone_dir, "sample data", "release notes.txt")
    assert not os.path.exists(std_sub_file), "Submodule file should not exist before submodule update"

    # 2A: Unquoted pathspec - fails because shell passes "sample" and "data" as two arguments
    rc_unquoted, out_unquoted, err_unquoted = run_cmd_allow_fail(
        ["git", "submodule", "update", "--init", "--recursive", "sample", "data"],
        cwd=std_clone_dir,
    )
    assert rc_unquoted != 0, "Unquoted submodule update must fail"
    assert "error: pathspec 'sample' did not match any file(s) known to git" in err_unquoted
    assert "error: pathspec 'data' did not match any file(s) known to git" in err_unquoted
    assert not os.path.exists(std_sub_file), "Submodule file must not exist after unquoted failure"

    # 2B: Quoted pathspec with "--" separator
    rc_quoted, out_quoted, err_quoted = run_cmd_allow_fail(
        ["git", "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--recursive", "--", "sample data"],
        cwd=std_clone_dir,
    )
    assert rc_quoted == 0, f"Quoted submodule update with -- failed: {err_quoted}"
    assert os.path.exists(std_sub_file), "Submodule file must exist after quoted update"
    with open(std_sub_file) as f:
        std_file_content = f.read()
    assert std_file_content == "v1.0 release notes\n"

    std_sub_head = run_cmd(["git", "rev-parse", "HEAD"], cwd=os.path.join(std_clone_dir, "sample data"))
    assert std_sub_head == submodule_commit_hash

    # -------------------------------------------------------------
    # Test 3: Quoting for file named "release notes.txt" inside submodule
    # -------------------------------------------------------------
    sub_clone_dir = os.path.join(std_clone_dir, "sample data")
    # Unquoted checkout fails because shell passes "release" and "notes.txt" as separate args
    rc_file_unquoted, _, err_file_unquoted = run_cmd_allow_fail(
        ["git", "checkout", "HEAD", "--", "release", "notes.txt"],
        cwd=sub_clone_dir,
    )
    assert rc_file_unquoted != 0, "Unquoted file checkout must fail"
    assert "error: pathspec 'release' did not match any file(s) known to git" in err_file_unquoted

    # Quoted checkout with "--" succeeds
    rc_file_quoted, _, err_file_quoted = run_cmd_allow_fail(
        ["git", "checkout", "HEAD", "--", "release notes.txt"],
        cwd=sub_clone_dir,
    )
    assert rc_file_quoted == 0, f"Quoted file checkout with -- failed: {err_file_quoted}"

    # -------------------------------------------------------------
    # Test 4: Filename vs Revision Ambiguity & Disambiguation with "--"
    # Create a ref matching a filename (e.g. branch named todo.txt)
    # -------------------------------------------------------------
    run_cmd(["git", "branch", "todo.txt"], cwd=super_work)
    rc_amb, out_amb, err_amb = run_cmd_allow_fail(["git", "log", "todo.txt"], cwd=super_work)
    assert rc_amb != 0, "Ambiguous git log without -- must exit non-zero"
    assert "fatal: ambiguous argument 'todo.txt': both revision and filename" in err_amb
    assert "Use '--' to separate paths from revisions" in err_amb

    # Disambiguate using "--"
    out_disamb = run_cmd(["git", "log", "--oneline", "--", "todo.txt"], cwd=super_work)
    assert "Commit C: add todo.txt" in out_disamb

    # Verify checkout with "--" in superproject acts strictly on path
    run_cmd(["git", "checkout", "HEAD", "--", "sample data"], cwd=super_work)

    return {
        "commit_a_hash": commit_a_hash,
        "commit_a_tree": commit_a_tree,
        "commit_b_hash": commit_b_hash,
        "commit_b_tree": commit_b_tree,
        "commit_c_hash": commit_c_hash,
        "commit_c_tree": commit_c_tree,
        "submodule_commit_hash": submodule_commit_hash,
        "submodule_gitlink": submodule_gitlink,
        "submodule_tree": submodule_tree,
        "super_commit_hash": super_commit_hash,
        "super_tree_hash": super_tree_hash,
        "rec_clone_file_content": rec_file_content,
        "rec_sub_head": rec_sub_head,
        "unquoted_error_rc": rc_unquoted,
        "unquoted_error_stderr": err_unquoted,
        "quoted_success_rc": rc_quoted,
        "std_clone_file_content": std_file_content,
        "std_sub_head": std_sub_head,
        "file_unquoted_rc": rc_file_unquoted,
        "file_unquoted_stderr": err_file_unquoted,
        "file_quoted_rc": rc_file_quoted,
        "ambiguity_rc": rc_amb,
        "ambiguity_stderr": err_amb,
        "disambiguated_log": out_disamb,
    }


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    work_dir = os.path.join(repo_root, "work", "R12-T035")
    os.makedirs(work_dir, exist_ok=True)

    # Tool versions
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

    # Inputs definition
    inputs_data = {
        "task": "R12-T035",
        "guide_section": "Clone all submodules",
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
                "submodule_path": "sample data",
                "submodule_file": "release notes.txt",
                "submodule_content": "v1.0 release notes\n",
            },
        ],
        "command_anchors": [
            "git clone --recursive git://github.com/foo/bar.git",
            "git submodule update --init --recursive",
        ],
        "quoting_and_disambiguation": {
            "directory_with_spaces": "sample data",
            "file_with_spaces": "release notes.txt",
            "unquoted_directory_behavior": "Shell splits 'sample data' into two arguments; git fails with pathspec mismatch",
            "quoted_directory_behavior": "Enclosing 'sample data' in quotes preserves the directory path as a single argument",
            "unquoted_file_behavior": "Shell splits 'release notes.txt' into two arguments; git fails with pathspec mismatch",
            "quoted_file_behavior": "Enclosing 'release notes.txt' in quotes preserves the file path as a single argument",
            "double_dash_separator": "Separates command options and revisions from pathspecs, resolving filename vs revision ambiguity",
        },
    }

    with open(os.path.join(work_dir, "inputs.json"), "w") as f:
        json.dump(inputs_data, f, indent=2)

    # Run 1 in temporary directory
    with tempfile.TemporaryDirectory(prefix="gfr_run1_") as td1:
        state1 = setup_and_run(td1)

    # Run 2 in temporary directory
    with tempfile.TemporaryDirectory(prefix="gfr_run2_") as td2:
        state2 = setup_and_run(td2)

    # Cross-run consistency assertions
    assert state1["commit_a_tree"] == state2["commit_a_tree"]
    assert state1["commit_b_tree"] == state2["commit_b_tree"]
    assert state1["commit_c_tree"] == state2["commit_c_tree"]
    assert state1["submodule_tree"] == state2["submodule_tree"]
    assert state1["submodule_gitlink"] == state1["submodule_commit_hash"]
    assert state2["submodule_gitlink"] == state2["submodule_commit_hash"]
    assert state1["rec_clone_file_content"] == state2["rec_clone_file_content"] == "v1.0 release notes\n"
    assert state1["std_clone_file_content"] == state2["std_clone_file_content"] == "v1.0 release notes\n"
    assert state1["unquoted_error_rc"] == state2["unquoted_error_rc"] != 0
    assert state1["quoted_success_rc"] == state2["quoted_success_rc"] == 0
    assert state1["file_unquoted_rc"] == state2["file_unquoted_rc"] != 0
    assert state1["file_quoted_rc"] == state2["file_quoted_rc"] == 0
    assert state1["ambiguity_rc"] == state2["ambiguity_rc"] != 0

    # Save results
    results_data = {
        "status": "PASS",
        "assertions_verified": [
            {
                "fact": "Unquoted directory path with spaces ('sample data') splits into multiple arguments and fails with pathspec errors",
                "expected": "error: pathspec 'sample' did not match any file(s) known to git",
                "actual": state1["unquoted_error_stderr"],
                "passed": True,
            },
            {
                "fact": "Quoted directory path with '--' (git submodule update --init --recursive -- 'sample data') succeeds",
                "expected_returncode": 0,
                "actual_returncode": state1["quoted_success_rc"],
                "passed": True,
            },
            {
                "fact": "Submodule file 'sample data/release notes.txt' exists and contains exact content",
                "expected": "v1.0 release notes\n",
                "actual": state1["std_clone_file_content"],
                "passed": True,
            },
            {
                "fact": "Unquoted file path with spaces ('release notes.txt') splits into multiple arguments and fails",
                "expected": "error: pathspec 'release' did not match any file(s) known to git",
                "actual": state1["file_unquoted_stderr"],
                "passed": True,
            },
            {
                "fact": "Quoted file path with '--' (git checkout HEAD -- 'release notes.txt') succeeds",
                "expected_returncode": 0,
                "actual_returncode": state1["file_quoted_rc"],
                "passed": True,
            },
            {
                "fact": "Recursive clone (git clone --recursive ... '<destination with spaces>') preserves spaces and checks out submodules",
                "expected": "v1.0 release notes\n",
                "actual": state1["rec_clone_file_content"],
                "passed": True,
            },
            {
                "fact": "Filename vs revision ambiguity is detected when ref matches filename, requiring '--' delimiter",
                "expected": "fatal: ambiguous argument 'todo.txt': both revision and filename",
                "actual": state1["ambiguity_stderr"],
                "passed": True,
            },
            {
                "fact": "Disambiguated command with '--' acts strictly on intended pathspec",
                "expected_in_output": "Commit C: add todo.txt",
                "actual": state1["disambiguated_log"],
                "passed": True,
            },
            {
                "fact": "Two independent runs across separate temporary directories produce identical submodule tree hashes",
                "expected_tree": state1["submodule_tree"],
                "actual_tree": state2["submodule_tree"],
                "passed": True,
            },
        ],
        "submodule_state": {
            "submodule_commit": state1["submodule_commit_hash"],
            "submodule_gitlink": state1["submodule_gitlink"],
            "submodule_tree": state1["submodule_tree"],
            "superproject_commit": state1["super_commit_hash"],
            "superproject_tree": state1["super_tree_hash"],
            "submodule_path": "sample data",
            "file_path": "sample data/release notes.txt",
        },
    }

    with open(os.path.join(work_dir, "results.json"), "w") as f:
        json.dump(results_data, f, indent=2)

    log_message = (
        "All assertions PASSED successfully across two independent temporary directory runs!\n"
        f"Superproject commit: {state1['super_commit_hash']}\n"
        f"Submodule commit:    {state1['submodule_commit_hash']}\n"
        f"Superproject tree:   {state1['super_tree_hash']}\n"
        "Unquoted directory pathspec correctly caught: error: pathspec 'sample' / 'data' did not match\n"
        "Quoted directory pathspec with '--' checked out: 'sample data/release notes.txt' -> 'v1.0 release notes\\n'\n"
        "Unquoted file pathspec correctly caught: error: pathspec 'release' did not match\n"
        "Quoted file pathspec with '--' succeeded.\n"
        "Filename vs revision ambiguity verified and resolved using '--'.\n"
    )

    with open(os.path.join(work_dir, "run_check.log"), "w") as f:
        f.write(log_message)

    print(log_message)


if __name__ == "__main__":
    main()
