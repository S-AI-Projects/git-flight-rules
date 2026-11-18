"""
R12-T007 check: Explain a real command failure: Stash while keeping unstaged edits
Guide: Stash while keeping unstaged edits
Commands: git stash create | git stash store -m CREATED_SHA1
Tests precondition violation (clean working tree -> empty SHA -> stash store fails) and the minimal fix
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
        run('git config user.name "Course Student"', repo)
        run('git config user.email "student@example.invalid"', repo)
        run('git config commit.gpgsign false', repo)

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

        # --- TRIGGER PRECONDITION FAILURE ---
        # Working directory is clean: git stash create outputs empty string
        empty_sha = run("git stash create", repo)
        assert empty_sha == "", \
            f"FAIL: git stash create should output empty string on clean tree, got: {empty_sha!r}"
        print("PASS 1: Clean tree causes 'git stash create' to output empty string")

        # Calling git stash store with empty string fails with non-zero exit
        proc = subprocess.run(
            'git stash store -m "failing stash" ""',
            cwd=repo, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        assert proc.returncode != 0, \
            f"FAIL: git stash store with empty SHA must exit non-zero, got exit code {proc.returncode}"
        print(f"PASS 2: 'git stash store' failed with non-zero exit code ({proc.returncode}) as expected")

        # --- SMALLEST CORRECTION ---
        # Introduce uncommitted change
        with open(os.path.join(repo, "notes.txt"), "a") as f:
            f.write("unstaged work in progress\n")

        valid_sha = run("git stash create", repo)
        assert len(valid_sha) == 40, \
            f"FAIL: git stash create should return 40-char commit SHA, got: {valid_sha!r}"
        print(f"PASS 3: With edits present, 'git stash create' produced valid SHA ({valid_sha[:7]})")

        # Stash store now succeeds
        run(f'git stash store -m "repaired stash" {valid_sha}', repo)
        stash_list = run("git stash list", repo)
        assert "repaired stash" in stash_list, \
            f"FAIL: Stash list should contain 'repaired stash', got: {stash_list!r}"
        print("PASS 4: 'git stash store' succeeded and stash appears in git stash list")

        # Assert 5: The unstaged edit is STILL present in working tree (preserving unstaged edits)
        notes_content = open(os.path.join(repo, "notes.txt")).read()
        assert "unstaged work in progress" in notes_content, \
            "FAIL: Unstaged edits should be preserved in working tree after stash create + store"
        print("PASS 5: Working tree retains unstaged edits (guide objective confirmed)")

        print("\nAll checks passed for R12-T007!")

if __name__ == "__main__":
    main()
