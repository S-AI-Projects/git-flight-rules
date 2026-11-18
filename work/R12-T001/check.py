"""
R12-T001 check: Make the command example reproducible
Guide: Delete/remove arbitrary commit
Commands: git rebase --onto SHA1_OF_BAD_COMMIT^ SHA1_OF_BAD_COMMIT
"""
import subprocess, tempfile, os, sys

def run(cmd, cwd, check=True, capture=True):
    result = subprocess.run(
        cmd, cwd=cwd, shell=True, check=check,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return result.stdout.strip()

def main():
    with tempfile.TemporaryDirectory() as repo:
        # Setup repo with author Course Student
        run("git init", repo)
        run('git config user.name "Course Student"', repo)
        run('git config user.email "student@example.invalid"', repo)
        run('git config commit.gpgsign false', repo)

        # Commit A: notes.txt with "alpha"
        with open(os.path.join(repo, "notes.txt"), "w") as f:
            f.write("alpha\n")
        run("git add notes.txt", repo)
        run('git commit -m "A: add notes.txt with alpha"', repo)
        sha_a = run("git rev-parse HEAD", repo)

        # Commit B (BAD): append "beta"
        with open(os.path.join(repo, "notes.txt"), "a") as f:
            f.write("beta\n")
        run("git add notes.txt", repo)
        run('git commit -m "B: append beta BAD commit"', repo)
        sha_b = run("git rev-parse HEAD", repo)

        # Commit C: add todo.txt with "one"
        with open(os.path.join(repo, "todo.txt"), "w") as f:
            f.write("one\n")
        run("git add todo.txt", repo)
        run('git commit -m "C: add todo.txt with one"', repo)
        sha_c_before = run("git rev-parse HEAD", repo)

        # Create branch topic at B
        run(f"git checkout -b topic {sha_b}", repo)
        # Go back to default branch (master or main)
        default_branch = run("git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || git branch --show-current", repo)
        run("git checkout -", repo)

        # Assert 1: Before rebase, notes.txt has two lines (alpha + beta)
        notes_before = open(os.path.join(repo, "notes.txt")).read()
        assert "alpha" in notes_before and "beta" in notes_before, \
            f"FAIL: notes.txt should contain both alpha and beta before rebase, got: {notes_before!r}"
        print("PASS 1: notes.txt contains both 'alpha' and 'beta' before rebase")

        # Assert 2: There are exactly 3 commits before rebase
        log_before = run("git log --oneline", repo)
        commit_count_before = len(log_before.strip().splitlines())
        assert commit_count_before == 3, \
            f"FAIL: Expected 3 commits before rebase, got {commit_count_before}"
        print(f"PASS 2: Exactly 3 commits before rebase")

        # Perform rebase: delete commit B
        run(f"git rebase --onto {sha_b}^ {sha_b}", repo)

        # Assert 3: After rebase, notes.txt contains only "alpha\n" (beta removed)
        notes_after = open(os.path.join(repo, "notes.txt")).read()
        assert notes_after == "alpha\n", \
            f"FAIL: notes.txt should be 'alpha\\n' after removing commit B, got: {notes_after!r}"
        print("PASS 3: After rebase, notes.txt contains only 'alpha' (commit B deleted)")

        # Assert 4: todo.txt still exists with correct content (commit C preserved)
        todo_after = open(os.path.join(repo, "todo.txt")).read()
        assert todo_after == "one\n", \
            f"FAIL: todo.txt should be 'one\\n' after rebase, got: {todo_after!r}"
        print("PASS 4: todo.txt still contains 'one' (commit C preserved)")

        # Assert 5: Now exactly 2 commits (A and C, B deleted)
        log_after = run("git log --oneline", repo)
        commit_count_after = len(log_after.strip().splitlines())
        assert commit_count_after == 2, \
            f"FAIL: Expected 2 commits after deleting B, got {commit_count_after}"
        print(f"PASS 5: Exactly 2 commits after rebase (commit B deleted)")

        print("\nAll checks passed for R12-T001!")

if __name__ == "__main__":
    main()
