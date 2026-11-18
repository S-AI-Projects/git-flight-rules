"""
R12-T008 check: Make the guide executable as a test: I want to find by author/committer
Guide: I want to find by author/committer
Commands: git log --author= | git log --committer=
Asserts:
1. Filters accurately by author (distinguishing author from committer)
2. Filters accurately by committer
3. Returns zero results for non-existent author
4. Propagates failures and fails when filter flag is deliberately omitted
"""
import subprocess, tempfile, os

def run(cmd, cwd, check=True):
    result = subprocess.run(
        cmd, cwd=cwd, shell=True, check=check,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return result.stdout.strip()

def main():
    temp_dir = tempfile.mkdtemp()
    try:
        repo = temp_dir
        run("git init", repo)
        run('git config user.name "Course Student"', repo)
        run('git config user.email "student@example.invalid"', repo)
        run('git config commit.gpgsign false', repo)

        # Commit A: authored by Course Student
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

        # Commit D: authored by "External Contributor", committed by "Course Student"
        with open(os.path.join(repo, "contrib.txt"), "w") as f:
            f.write("external contribution\n")
        run("git add contrib.txt", repo)
        run('git commit --author="External Contributor <external@example.invalid>" -m "D: external contribution"', repo)

        # Assert 1: git log --author="External Contributor" finds exactly 1 commit
        author_log = run('git log --author="External Contributor" --oneline', repo)
        author_commits = [l for l in author_log.splitlines() if l.strip()]
        assert len(author_commits) == 1, \
            f"FAIL: Expected 1 commit by External Contributor, got: {author_commits}"
        assert "D: external contribution" in author_commits[0], \
            f"FAIL: Wrong commit found: {author_commits[0]}"
        print("PASS 1: git log --author correctly isolates commit by author name")

        # Assert 2: git log --committer="Course Student" finds all 4 commits (Course Student committed all)
        committer_log = run('git log --committer="Course Student" --oneline', repo)
        committer_commits = [l for l in committer_log.splitlines() if l.strip()]
        assert len(committer_commits) == 4, \
            f"FAIL: Expected 4 commits committed by Course Student, got: {len(committer_commits)}"
        print(f"PASS 2: git log --committer correctly finds all {len(committer_commits)} commits committed by Course Student")

        # Assert 3: Filtering for non-existent author returns empty output (0 commits)
        none_log = run('git log --author="NonExistentAuthor" --oneline', repo)
        assert none_log == "", \
            f"FAIL: Expected empty output for non-existent author, got: {none_log!r}"
        print("PASS 3: git log --author with unknown author yields empty result as expected")

        # Assert 4: Verify test failure when the decisive filter command is omitted
        unfiltered_log = run("git log --oneline", repo)
        unfiltered_count = len(unfiltered_log.splitlines())
        # An unfiltered query returns all 4 commits, whereas the author query returns only 1
        assert unfiltered_count > len(author_commits), \
            "FAIL: Omitting --author filter must return full commit set, not filtered subset"
        print(f"PASS 4: Decisive test: omitting --author yields {unfiltered_count} commits instead of {len(author_commits)}")

        print("\nAll checks passed for R12-T008!")
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
