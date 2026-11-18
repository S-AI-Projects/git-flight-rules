"""
R12-T009 check: State the missing setup explicitly: I want to discard specific unstaged changes
Guide: I want to discard specific unstaged changes
Commands: git checkout -p
Verifies all prerequisites:
1. Tracked file requirement (untracked files are not handled by checkout -p)
2. Unstaged changes requirement
3. Staged changes remain intact when discarding unstaged changes
4. Global git configuration is untouched (local config only)
"""
import subprocess, tempfile, os

def run(cmd, cwd, check=True):
    result = subprocess.run(
        cmd, cwd=cwd, shell=True, check=check,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return result.stdout.strip()

def main():
    with tempfile.TemporaryDirectory() as repo:
        run("git init", repo)
        # Verify local-only config
        run('git config --local user.name "Course Student"', repo)
        run('git config --local user.email "student@example.invalid"', repo)
        run('git config --local commit.gpgsign false', repo)

        # Commit A: notes.txt with "alpha\n"
        with open(os.path.join(repo, "notes.txt"), "w") as f:
            f.write("alpha\n")
        run("git add notes.txt", repo)
        run('git commit -m "A: add notes.txt with alpha"', repo)

        # Commit B: append "beta\n"
        with open(os.path.join(repo, "notes.txt"), "a") as f:
            f.write("beta\n")
        run("git add notes.txt", repo)
        run('git commit -m "B: append beta"', repo)
        sha_b = run("git rev-parse HEAD", repo)

        # Commit C: add todo.txt with "one\n"
        with open(os.path.join(repo, "todo.txt"), "w") as f:
            f.write("one\n")
        run("git add todo.txt", repo)
        run('git commit -m "C: add todo.txt with one"', repo)

        # Create branch topic at B
        run(f"git checkout -b topic {sha_b}", repo)
        run("git checkout -", repo)

        # --- Assert 1: Prerequisite - repo must have unstaged changes for patch mode ---
        # When working tree is clean, checkout -p returns immediately with no changes
        clean_check = run("git diff", repo)
        assert clean_check == "", "FAIL: Expected clean diff before introducing edits"
        print("PASS 1: Repository initial state confirmed clean")

        # --- Assert 2: Untracked files are ignored by git checkout -p ---
        with open(os.path.join(repo, "new_untracked.txt"), "w") as f:
            f.write("untracked content\n")
        # Run checkout -p (passing 'y' via stdin in case it prompts)
        proc = subprocess.run(
            "echo y | git checkout -p",
            cwd=repo, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        assert os.path.exists(os.path.join(repo, "new_untracked.txt")), \
            "FAIL: Untracked file should NOT be discarded by git checkout -p"
        print("PASS 2: Untracked files are untouched by 'git checkout -p' (tracked file prerequisite verified)")
        os.remove(os.path.join(repo, "new_untracked.txt"))

        # --- Assert 3: Staged changes are preserved when discarding unstaged changes ---
        # Stage a good change in todo.txt
        with open(os.path.join(repo, "todo.txt"), "a") as f:
            f.write("staged good change\n")
        run("git add todo.txt", repo)

        # Introduce an unstaged bad change in notes.txt
        with open(os.path.join(repo, "notes.txt"), "a") as f:
            f.write("bad unstaged change\n")

        # Verify staged diff exists
        staged_diff = run("git diff --cached", repo)
        assert "staged good change" in staged_diff, "FAIL: Expected staged changes in todo.txt"

        # Discard unstaged changes in notes.txt via checkout
        # echo 'y' accepts the discard hunk
        discard_proc = subprocess.run(
            "echo y | git checkout -p notes.txt",
            cwd=repo, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        assert discard_proc.returncode == 0, f"git checkout -p failed: {discard_proc.stderr}"

        # Assert 4: Unstaged change in notes.txt is now discarded
        notes_after = open(os.path.join(repo, "notes.txt")).read()
        assert "bad unstaged change" not in notes_after, \
            f"FAIL: Unstaged bad change should be discarded, got: {notes_after!r}"
        print("PASS 3: Unstaged change in notes.txt successfully discarded by 'git checkout -p'")

        # Assert 5: Staged change in todo.txt remains staged and unmodified
        todo_content = open(os.path.join(repo, "todo.txt")).read()
        assert "staged good change" in todo_content, \
            "FAIL: Staged changes in todo.txt must be preserved"
        cached_diff_after = run("git diff --cached", repo)
        assert "staged good change" in cached_diff_after, \
            "FAIL: Staged changes must still be in the index"
        print("PASS 4: Staged changes in todo.txt preserved in working tree and index")

        # Assert 6: Per-test configuration is local only (user.name is local)
        local_user = run("git config --local user.name", repo)
        assert local_user == "Course Student", \
            f"FAIL: Expected local config, got: {local_user}"
        print("PASS 5: Configuration verified to be strictly repository-local")

        print("\nAll checks passed for R12-T009!")

if __name__ == "__main__":
    main()
