"""
R12-T010 check: Add a prediction-and-verification exercise: I want to add aliases for some Git commands
Guide: I want to add aliases for some Git commands
Commands: git alias definition and execution
Verifies:
1. Exact ref deleted (refs/heads/merged-feature)
2. Underlying commit objects preserved in object database
3. Index and working tree remain clean
4. HEAD and master ref remain unchanged
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
        sha_c = run("git rev-parse HEAD", repo)

        # Create branch topic at B
        run(f"git checkout -b topic {sha_b}", repo)
        run("git checkout -", repo)

        # Create merged-feature at B (which is an ancestor of C/master)
        run(f"git branch merged-feature {sha_b}", repo)

        # Configure the alias locally
        run("git config alias.cleanup \"!f() { git branch --merged | grep -v '^\\*' | xargs -n 1 git branch -d; }; f\"", repo)

        # --- PREDICTION VERIFICATION ---
        # Assert 1: Before execution, refs/heads/merged-feature exists and points to commit B
        branches_before = run("git branch", repo)
        assert "merged-feature" in branches_before, "FAIL: merged-feature branch should exist before cleanup"
        sha_merged_feature = run("git rev-parse refs/heads/merged-feature", repo)
        assert sha_merged_feature == sha_b, f"FAIL: merged-feature should point to {sha_b}"
        print(f"PASS 1: Before alias execution, ref 'refs/heads/merged-feature' exists pointing to commit B ({sha_b[:7]})")

        # Execute the alias
        alias_output = run("git cleanup", repo)
        print(f"Alias execution output: {alias_output}")

        # Assert 2: After execution, refs/heads/merged-feature is deleted
        branches_after = run("git branch", repo)
        assert "merged-feature" not in branches_after, \
            "FAIL: merged-feature should be deleted by the alias"
        proc = subprocess.run("git rev-parse --verify refs/heads/merged-feature", cwd=repo, shell=True, stderr=subprocess.PIPE)
        assert proc.returncode != 0, "FAIL: refs/heads/merged-feature ref must no longer resolve"
        print("PASS 2: Specific ref 'refs/heads/merged-feature' was deleted as predicted")

        # Assert 3: Commit B still exists in the object store (commits are not deleted when branch refs are removed)
        cat_file_proc = subprocess.run(f"git cat-file -e {sha_b}", cwd=repo, shell=True)
        assert cat_file_proc.returncode == 0, \
            f"FAIL: Commit object {sha_b} should still exist in the object database"
        print(f"PASS 3: Commit object B ({sha_b[:7]}) remains preserved in object database")

        # Assert 4: master still points to commit C and working tree is clean
        sha_master_after = run("git rev-parse HEAD", repo)
        assert sha_master_after == sha_c, "FAIL: Current branch should still point to commit C"
        status = run("git status --porcelain", repo)
        assert status == "", f"FAIL: Working tree and index must remain completely clean, got: {status!r}"
        print("PASS 4: HEAD/master ref unchanged (commit C) and working tree/index remain clean")

        print("\nAll checks passed for R12-T010!")

if __name__ == "__main__":
    main()
