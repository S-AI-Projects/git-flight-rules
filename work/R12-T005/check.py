"""
R12-T005 check: Handle paths and quoting accurately: What did I just commit?
Guide: What did I just commit?
Commands: git show | git log -n1 -p | git show :filename
Verifies paths with spaces ("release notes.txt", "sample data/") and ambiguity resolution
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

        # Now commit with "release notes.txt" and directory "sample data"
        with open(os.path.join(repo, "release notes.txt"), "w") as f:
            f.write("v1.0.0 release notes content\n")
        os.makedirs(os.path.join(repo, "sample data"), exist_ok=True)
        with open(os.path.join(repo, "sample data", "item.txt"), "w") as f:
            f.write("sample payload data\n")
        run('git add "release notes.txt" "sample data"', repo)
        run('git commit -m "D: add release notes and sample data"', repo)

        # Assert 1: git show HEAD:filename with quotes extracts exact file content
        content = run('git show "HEAD:release notes.txt"', repo)
        assert content == "v1.0.0 release notes content", \
            f"FAIL: git show HEAD:release notes.txt content mismatch: {content!r}"
        print("PASS 1: git show HEAD:\"release notes.txt\" correctly extracts file content")

        # Assert 2: git show HEAD -- "release notes.txt" outputs diff for only that file
        show_output = run('git show HEAD -- "release notes.txt"', repo)
        assert "diff --git a/release notes.txt" in show_output and "v1.0.0 release notes content" in show_output, \
            "FAIL: git show with path filter should contain diff for release notes.txt"
        assert "diff --git a/sample data" not in show_output, \
            "FAIL: git show with file filter should NOT include sample data diff"
        print("PASS 2: git show HEAD -- \"release notes.txt\" scopes diff cleanly with spaces preserved")

        # Assert 3: git log -n1 -p -- "sample data/" scopes diff to directory with space
        log_output = run('git log -n1 -p -- "sample data/"', repo)
        assert "diff --git a/sample data/item.txt" in log_output, \
            "FAIL: git log with directory filter should include item.txt"
        assert "diff --git a/release notes.txt" not in log_output, \
            "FAIL: git log scoped to directory should NOT show release notes.txt diff"
        print("PASS 3: git log -n1 -p -- \"sample data/\" correctly filters to directory with spaces")

        # Assert 4: Verify disambiguation: create file that matches branch name
        # Using -- disambiguates path from revision
        with open(os.path.join(repo, "topic"), "w") as f:
            f.write("topic file content\n")
        run('git add topic && git commit -m "E: add file named topic"', repo)
        # Without --, git log could be ambiguous; with --, it treats 'topic' as a path
        disambig_output = run('git log -n1 --oneline -- topic', repo)
        assert "E: add file named topic" in disambig_output, \
            "FAIL: git log -- topic should resolve as a file path"
        print("PASS 4: Ambiguity resolved using -- separator for filename matching branch name")

        print("\nAll checks passed for R12-T005!")

if __name__ == "__main__":
    main()
