"""
R12-T003 check: Teach recovery from the operation: PowerShell on Windows
Guide: PowerShell on Windows — git rebase -i HEAD~N
Demonstrates a reversible mistake and recovery using git reflog/reset
"""
import subprocess, tempfile, os, sys

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

        # Commit A: notes.txt with "alpha"
        with open(os.path.join(repo, "notes.txt"), "w") as f:
            f.write("alpha\n")
        run("git add notes.txt", repo)
        run('git commit -m "A: add notes.txt with alpha"', repo)

        # Commit B: append "beta"
        with open(os.path.join(repo, "notes.txt"), "a") as f:
            f.write("beta\n")
        run("git add notes.txt", repo)
        run('git commit -m "B: append beta"', repo)
        sha_b = run("git rev-parse HEAD", repo)

        # Commit C: add todo.txt with "one"
        with open(os.path.join(repo, "todo.txt"), "w") as f:
            f.write("one\n")
        run("git add todo.txt", repo)
        run('git commit -m "C: add todo.txt with one"', repo)
        sha_c_before = run("git rev-parse HEAD", repo)

        # Create branch topic at B
        run(f"git checkout -b topic {sha_b}", repo)
        run("git checkout -", repo)

        # Assert 1: Before mistake — 3 commits and notes.txt has both lines
        log_before = run("git log --oneline", repo)
        assert len(log_before.splitlines()) == 3, \
            f"FAIL: Expected 3 commits before mistake, got {len(log_before.splitlines())}"
        notes_before = open(os.path.join(repo, "notes.txt")).read()
        assert "beta" in notes_before, "FAIL: notes.txt should contain 'beta' before mistake"
        print("PASS 1: Before mistake — 3 commits present and notes.txt contains 'beta'")

        # Simulate the mistake: use rebase --onto to skip (drop) commit B
        sha_a = run(f"git log --oneline | tail -3 | head -1", repo).split()[0]
        run(f"git rebase --onto {sha_b} {sha_b}~1 HEAD", repo, check=False)
        # Actually simulate dropping B by rebasing onto A, skipping B
        run(f"git reset --hard {sha_b}~1", repo)  # go to A
        # Re-apply C on top of A, skipping B (simulates dropping B in interactive rebase)
        run(f"git cherry-pick {sha_c_before}", repo)
        sha_bad = run("git rev-parse HEAD", repo)

        # Assert 2: After mistake — notes.txt has ONLY "alpha" (beta is gone)
        notes_after_mistake = open(os.path.join(repo, "notes.txt")).read()
        assert "beta" not in notes_after_mistake, \
            f"FAIL: After bad rebase, notes.txt should NOT contain 'beta', got: {notes_after_mistake!r}"
        print("PASS 2: After mistake — 'beta' is gone from notes.txt (commit B dropped)")

        # Assert 3: Reflog contains the pre-mistake state
        reflog = run("git reflog", repo)
        assert sha_c_before[:7] in reflog or sha_c_before in reflog, \
            "FAIL: reflog should contain the pre-mistake commit SHA"
        print("PASS 3: git reflog records the pre-mistake state (recovery is possible)")

        # Recovery: reset to the state before the bad operation
        run(f"git reset --hard {sha_c_before}", repo)

        # Assert 4: After recovery — notes.txt restored with both lines
        notes_recovered = open(os.path.join(repo, "notes.txt")).read()
        assert notes_recovered == "alpha\nbeta\n", \
            f"FAIL: After recovery, notes.txt should be 'alpha\\nbeta\\n', got: {notes_recovered!r}"
        print("PASS 4: Recovery successful — notes.txt restored with 'alpha' and 'beta'")

        # Assert 5: After recovery — 3 commits present again
        log_recovered = run("git log --oneline", repo)
        assert len(log_recovered.splitlines()) == 3, \
            f"FAIL: After recovery, expected 3 commits, got {len(log_recovered.splitlines())}"
        print("PASS 5: After recovery — all 3 commits (A, B, C) are present")

        # Assert 6: HEAD points back to sha_c_before
        head_after = run("git rev-parse HEAD", repo)
        assert head_after == sha_c_before, \
            f"FAIL: HEAD should be {sha_c_before}, got {head_after}"
        print(f"PASS 6: HEAD correctly restored to commit C ({sha_c_before[:7]})")

        print("\nAll checks passed for R12-T003!")

if __name__ == "__main__":
    main()
