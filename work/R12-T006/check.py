"""
R12-T006 check: Compare two ways to reach the state: I accidentally committed and pushed files containing sensitive data
Guide: I accidentally committed and pushed files containing sensitive data
Commands: git add edited_file | git commit --amend --no-edit | git push --force-with-lease origin [branch]
Compares amend (history rewrite) vs forward fix (append new commit)
"""
import subprocess, tempfile, os

def run(cmd, cwd, check=True):
    result = subprocess.run(
        cmd, cwd=cwd, shell=True, check=check,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return result.stdout.strip()

def build_fixture(path):
    run("git init", path)
    run('git config user.name "Course Student"', path)
    run('git config user.email "student@example.invalid"', path)
    run('git config commit.gpgsign false', path)

    # Commit A: notes.txt with "alpha\n"
    with open(os.path.join(path, "notes.txt"), "w") as f:
        f.write("alpha\n")
    run("git add notes.txt", path)
    run('git commit -m "A: add notes.txt with alpha"', path)

    # Commit B: append "beta\n"
    with open(os.path.join(path, "notes.txt"), "a") as f:
        f.write("beta\n")
    run("git add notes.txt", path)
    run('git commit -m "B: append beta"', path)
    sha_b = run("git rev-parse HEAD", path)

    # Commit C: add todo.txt with "one\n" + accidentally added secret.txt
    with open(os.path.join(path, "todo.txt"), "w") as f:
        f.write("one\n")
    with open(os.path.join(path, "secret.txt"), "w") as f:
        f.write("SUPER_SECRET_TOKEN=xyz123\n")
    run("git add todo.txt secret.txt", path)
    run('git commit -m "C: add todo.txt and accidental secret"', path)

    # Create branch topic at B
    run(f"git checkout -b topic {sha_b}", path)
    run("git checkout -", path)

def main():
    with tempfile.TemporaryDirectory() as base_dir:
        dir_amend = os.path.join(base_dir, "repo_amend")
        dir_forward = os.path.join(base_dir, "repo_forward")
        os.makedirs(dir_amend)
        os.makedirs(dir_forward)

        # Set up identical fixtures in both directories
        build_fixture(dir_amend)
        build_fixture(dir_forward)

        sha_c_amend_orig = run("git rev-parse HEAD", dir_amend)
        sha_c_fwd_orig = run("git rev-parse HEAD", dir_forward)
        assert sha_c_amend_orig == sha_c_fwd_orig, "Fixtures must start at identical state"
        print(f"PASS 1: Both fixtures start with identical state (Commit C SHA: {sha_c_amend_orig[:7]})")

        # Approach 1: Amend (Guide approach)
        # Remove secret.txt and amend commit
        run("git rm secret.txt", dir_amend)
        run("git commit --amend --no-edit", dir_amend)
        sha_c_amend_new = run("git rev-parse HEAD", dir_amend)
        log_amend = run("git log --oneline", dir_amend)
        count_amend = len(log_amend.splitlines())

        # Approach 2: Forward Fix (New commit)
        # Remove secret.txt and commit as new commit
        run("git rm secret.txt", dir_forward)
        run('git commit -m "fix: remove sensitive secret.txt"', dir_forward)
        sha_c_fwd_preserved = run("git rev-parse HEAD~1", dir_forward)
        log_fwd = run("git log --oneline", dir_forward)
        count_fwd = len(log_fwd.splitlines())

        # Assert 2: Amend rewrites commit SHA, count stays 3
        assert sha_c_amend_new != sha_c_amend_orig, \
            "FAIL: Amend should produce a new SHA for commit C"
        assert count_amend == 3, \
            f"FAIL: Amend commit count should remain 3, got {count_amend}"
        print(f"PASS 2: Approach 1 (Amend) rewrote commit SHA ({sha_c_amend_new[:7]}), commit count remains {count_amend}")

        # Assert 3: Forward fix preserves original commit SHA, count increases to 4
        assert sha_c_fwd_preserved == sha_c_fwd_orig, \
            "FAIL: Forward fix should preserve original commit C SHA"
        assert count_fwd == 4, \
            f"FAIL: Forward fix commit count should be 4, got {count_fwd}"
        print(f"PASS 3: Approach 2 (Forward Fix) preserved commit C SHA ({sha_c_fwd_orig[:7]}), commit count grew to {count_fwd}")

        # Assert 4: secret.txt is not in working tree of either repo
        assert not os.path.exists(os.path.join(dir_amend, "secret.txt")), "FAIL: secret.txt should be gone"
        assert not os.path.exists(os.path.join(dir_forward, "secret.txt")), "FAIL: secret.txt should be gone"
        print("PASS 4: Working tree clean: secret.txt successfully removed in both approaches")

        # Assert 5: secret.txt is NOT in git history of amend, but IS in history of forward fix
        amend_history = run("git log -p", dir_amend)
        fwd_history = run("git log -p", dir_forward)
        assert "SUPER_SECRET_TOKEN" not in amend_history, \
            "FAIL: Sensitive token should be completely erased from git history in amend approach"
        assert "SUPER_SECRET_TOKEN" in fwd_history, \
            "FAIL: Sensitive token remains in git history in forward-fix approach (key trade-off)"
        print("PASS 5: Key distinction verified: amend erased secret from history, forward fix left it in prior commit")

        print("\nAll checks passed for R12-T006!")

if __name__ == "__main__":
    main()
