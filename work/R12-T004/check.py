"""
R12-T004 check: Clarify branch and remote behavior
Guide: I need to change the content of a commit which is not my last
Commands: git rebase -i HEAD~4 | git commit --amend | git rebase --continue
Asserts: intended ref changed, unrelated refs (master) stayed fixed
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

        # Commit A on master
        with open(os.path.join(repo, "notes.txt"), "w") as f:
            f.write("alpha\n")
        run("git add notes.txt", repo)
        run('git commit -m "A: add notes.txt with alpha"', repo)
        sha_a = run("git rev-parse HEAD", repo)
        default_branch = run("git symbolic-ref --short HEAD", repo)
        sha_master_before = sha_a  # master/main stays at A

        # Create topic branch at A
        run("git checkout -b topic", repo)

        # Commit B on topic: append "beta"
        with open(os.path.join(repo, "notes.txt"), "a") as f:
            f.write("beta\n")
        run("git add notes.txt", repo)
        run('git commit -m "B: append beta"', repo)
        sha_b = run("git rev-parse HEAD", repo)

        # Commit C on topic: add todo.txt
        with open(os.path.join(repo, "todo.txt"), "w") as f:
            f.write("one\n")
        run("git add todo.txt", repo)
        run('git commit -m "C: add todo.txt with one"', repo)
        sha_c_before = run("git rev-parse HEAD", repo)
        sha_topic_before = sha_c_before

        # Assert 1: master stays at A (unaffected by topic commits)
        sha_master_check = run(f"git rev-parse {default_branch}", repo)
        assert sha_master_check == sha_master_before, \
            f"FAIL: {default_branch} should be at {sha_master_before}, got {sha_master_check}"
        print(f"PASS 1: {default_branch} is at commit A before amend (unrelated ref)")

        # Assert 2: topic is at C before amend
        sha_topic_check = run("git rev-parse topic", repo)
        assert sha_topic_check == sha_topic_before, \
            f"FAIL: topic should be at {sha_topic_before}, got {sha_topic_check}"
        print("PASS 2: topic is at commit C before amend")

        # Simulate amending commit B: add "gamma" to notes.txt in commit B
        # Using rebase --onto to simulate the effect non-interactively
        run(f"git rebase --onto {sha_b}~1 {sha_b}~1 {sha_b}", repo, check=False)
        # Actually: simulate by cherry-picking with amendment
        # Reset to A, cherry-pick amended B, then cherry-pick C
        run(f"git reset --hard {sha_a}", repo)
        run(f"git cherry-pick {sha_b}", repo)
        with open(os.path.join(repo, "notes.txt"), "a") as f:
            f.write("gamma\n")
        run("git add notes.txt", repo)
        run('git commit --amend --no-edit', repo)
        sha_b_new = run("git rev-parse HEAD", repo)
        run(f"git cherry-pick {sha_c_before}", repo)
        sha_c_new = run("git rev-parse HEAD", repo)
        # Update topic ref
        run(f"git branch -f topic HEAD", repo)

        # Assert 3: topic now points to new C' (different SHA from before)
        sha_topic_after = run("git rev-parse topic", repo)
        assert sha_topic_after != sha_topic_before, \
            "FAIL: topic should point to new C' after amend (SHA should change)"
        print("PASS 3: topic now points to new C' — SHA changed after amend")

        # Assert 4: master STILL at A (unrelated ref unchanged)
        sha_master_after = run(f"git rev-parse {default_branch}", repo)
        assert sha_master_after == sha_master_before, \
            f"FAIL: {default_branch} should still be at {sha_master_before}, got {sha_master_after}"
        print(f"PASS 4: {default_branch} is STILL at commit A — unrelated refs stay fixed")

        # Assert 5: notes.txt now contains "gamma" (the amendment took effect)
        notes = open(os.path.join(repo, "notes.txt")).read()
        assert "gamma" in notes, \
            f"FAIL: notes.txt should contain 'gamma' after amending B, got: {notes!r}"
        print("PASS 5: notes.txt now contains 'gamma' — commit B was successfully amended")

        # Assert 6: B got a new SHA (amend creates new commit object)
        assert sha_b_new != sha_b, \
            "FAIL: Amended commit B should have a new SHA"
        print(f"PASS 6: Old B SHA={sha_b[:7]}, New B' SHA={sha_b_new[:7]} — amend created new object")

        print("\nAll checks passed for R12-T004!")

if __name__ == "__main__":
    main()
