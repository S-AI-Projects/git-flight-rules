"""
R12-T002 check: Show the Git state transition
Guide: I want to create a new remote branch from current local one
Commands: git push HEAD | git push -u HEAD | git push
"""
import subprocess, tempfile, os, sys

def run(cmd, cwd, check=True):
    result = subprocess.run(
        cmd, cwd=cwd, shell=True, check=check,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return result.stdout.strip()

def main():
    with tempfile.TemporaryDirectory() as base:
        # Create bare remote repo
        remote_path = os.path.join(base, "remote.git")
        os.makedirs(remote_path)
        run("git init --bare", remote_path)
        remote_url = f"file://{remote_path}"

        # Clone into local repo
        local_path = os.path.join(base, "local")
        run(f"git clone {remote_url} local", base)
        run('git config user.name "Course Student"', local_path)
        run('git config user.email "student@example.invalid"', local_path)
        run('git config commit.gpgsign false', local_path)

        # Commit A
        with open(os.path.join(local_path, "notes.txt"), "w") as f:
            f.write("alpha\n")
        run("git add notes.txt", local_path)
        run('git commit -m "A: add notes.txt with alpha"', local_path)

        # Commit B
        with open(os.path.join(local_path, "notes.txt"), "a") as f:
            f.write("beta\n")
        run("git add notes.txt", local_path)
        run('git commit -m "B: append beta"', local_path)
        sha_b = run("git rev-parse HEAD", local_path)

        # Commit C
        with open(os.path.join(local_path, "todo.txt"), "w") as f:
            f.write("one\n")
        run("git add todo.txt", local_path)
        run('git commit -m "C: add todo.txt with one"', local_path)

        # Push master to remote first
        run("git push origin master 2>/dev/null || git push origin HEAD", local_path, check=False)

        # Create branch topic at B
        run(f"git checkout -b topic {sha_b}", local_path)

        # Assert 1: Before push, origin/topic does NOT exist
        remote_branches_before = run("git branch -r", local_path)
        assert "origin/topic" not in remote_branches_before, \
            f"FAIL: origin/topic should not exist before push, got: {remote_branches_before}"
        print("PASS 1: origin/topic does not exist before push")

        # Assert 2: Before push, topic tracking upstream is not set
        upstream_before = run("git rev-parse --abbrev-ref topic@{upstream}", local_path, check=False)
        assert "origin/topic" not in upstream_before, \
            "FAIL: topic should have no upstream before push -u"
        print("PASS 2: No upstream tracking set for topic before push")

        # Execute: push -u origin topic
        run("git push -u origin topic", local_path)

        # Assert 3: After push, origin/topic now exists and points to sha_b
        remote_branches_after = run("git branch -r", local_path)
        assert "origin/topic" in remote_branches_after, \
            f"FAIL: origin/topic should exist after push, got: {remote_branches_after}"
        print("PASS 3: origin/topic now exists after 'git push -u origin topic'")

        # Assert 4: Upstream tracking is now set to origin/topic
        upstream_after = run("git rev-parse --abbrev-ref topic@{upstream}", local_path)
        assert "origin/topic" in upstream_after, \
            f"FAIL: upstream should be origin/topic, got: {upstream_after}"
        print("PASS 4: topic upstream is now set to origin/topic (via -u flag)")

        # Assert 5: Working tree and index are clean (push does not touch working tree)
        status = run("git status --porcelain", local_path)
        assert status == "", \
            f"FAIL: Working tree should be clean after push, got: {status!r}"
        print("PASS 5: Index and working tree are clean after push (push only changes refs)")

        # Assert 6: origin/topic points to sha_b
        remote_topic_sha = run("git rev-parse origin/topic", local_path)
        assert remote_topic_sha == sha_b, \
            f"FAIL: origin/topic should point to {sha_b}, got {remote_topic_sha}"
        print(f"PASS 6: origin/topic correctly points to commit B ({sha_b[:7]})")

        print("\nAll checks passed for R12-T002!")

if __name__ == "__main__":
    main()
