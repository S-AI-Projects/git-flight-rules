import os
import subprocess
import sys
import tempfile


def git(cwd, *args, env=None, check=True):
    e = os.environ.copy()
    if env:
        e.update(env)
    r = subprocess.run(["git", *args], cwd=cwd, check=check,
                       capture_output=True, text=True, env=e)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def write(cwd, name, text, mode="w"):
    path = os.path.join(cwd, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode) as f:
        f.write(text)


def setup_repo(d):
    # Step 2: Use a temporary repository with branch main, author Course Student student@example.invalid,
    # and three commits: A creates notes.txt with "alpha\n"; B appends "beta\n";
    # C adds todo.txt with "one\n". Create branch topic at B.
    # Goal: Exercise this command workflow with a file named "release notes.txt" and a directory named "sample data";
    # identify where path quoting or -- is required.
    git(d, "init", "-b", "main")
    git(d, "config", "user.name", "Course Student")
    git(d, "config", "user.email", "student@example.invalid")

    write(d, "notes.txt", "alpha\n")
    git(d, "add", "notes.txt")
    git(d, "commit", "-m", "A")
    a = git(d, "rev-parse", "HEAD")[0]

    write(d, "notes.txt", "beta\n", "a")
    write(d, "release notes.txt", "v1.0 release notes\n")
    write(d, "sample data/data.txt", "sample data content\n")
    git(d, "add", "notes.txt", "release notes.txt", "sample data/data.txt")
    git(d, "commit", "-m", "B")
    b = git(d, "rev-parse", "HEAD")[0]
    git(d, "branch", "topic")

    write(d, "todo.txt", "one\n")
    git(d, "add", "todo.txt")
    git(d, "commit", "-m", "C")
    c = git(d, "rev-parse", "HEAD")[0]

    return a, b, c


def run_once(d):
    a, b, c = setup_repo(d)

    # Initial state assertions
    assert git(d, "rev-parse", "main")[0] == c
    assert git(d, "rev-parse", "topic")[0] == b

    # Demonstration of filename versus revision ambiguity:
    # If a revision (branch/tag) and a path share the same name,
    # Git produces an ambiguous argument error unless '--' is used.
    git(d, "tag", "notes.txt", a)
    out, err, code = git(d, "reset", "notes.txt", check=False)
    assert code != 0
    assert "both revision and filename" in err
    assert "Use '--' to separate paths from revisions" in err

    # With '--', path vs revision ambiguity is completely resolved
    out, err, code = git(d, "reset", "HEAD", "--", "notes.txt")
    assert code == 0
    git(d, "tag", "-d", "notes.txt")

    # Command anchors: git rebase -i | git reset HEAD~1 file1 | git stash
    # Step into rebase editing commit B
    editor_script = os.path.join(d, "ed.py")
    with open(editor_script, "w") as fp:
        fp.write("import sys\n"
                 "with open(sys.argv[1], 'r') as f:\n"
                 "    lines = f.readlines()\n"
                 "with open(sys.argv[1], 'w') as f:\n"
                 "    for l in lines:\n"
                 "        if ' B' in l:\n"
                 "            f.write(l.replace('pick ', 'edit '))\n"
                 "        else:\n"
                 "            f.write(l)\n")

    git(d, "rebase", "-i", "--root", env={"GIT_SEQUENCE_EDITOR": f"python3 {editor_script}"})
    assert git(d, "log", "-1", "--format=%s")[0] == "B"

    # Command anchor: git reset HEAD~1 <file>
    # When resetting paths with spaces like "release notes.txt" and directory "sample data":
    # 1. Path quoting and '--' are required to preserve spaces and prevent word splitting or ambiguity.
    out, err, code = git(d, "reset", "HEAD~1", "--", "release notes.txt", "sample data/data.txt")
    assert code == 0

    # Unstaged files are now in working tree
    status = git(d, "status", "--porcelain")[0]
    assert "release notes.txt" in status
    assert "sample data/data.txt" in status

    # Amend commit B without those unpinned changes
    git(d, "commit", "--amend", "--no-edit")
    b_new = git(d, "rev-parse", "HEAD")[0]

    # Command anchor: git stash
    # Stash the untracked changes, preserving paths with spaces
    git(d, "stash", "-u")
    assert git(d, "status", "--porcelain")[0] == ""

    # Finish rebase
    git(d, "rebase", "--continue")

    # Done when assertions:
    # 1. Main has new commit IDs for B and C
    c_new = git(d, "rev-parse", "main")[0]
    assert c_new != c
    assert b_new != b

    # 2. Unrelated ref topic stayed fixed at original b
    assert git(d, "rev-parse", "topic")[0] == b

    # 3. Spaced files and paths are preserved in stash and can be popped/applied cleanly
    git(d, "stash", "pop")
    assert os.path.exists(os.path.join(d, "release notes.txt"))
    assert os.path.exists(os.path.join(d, "sample data", "data.txt"))
    assert open(os.path.join(d, "release notes.txt")).read() == "v1.0 release notes\n"
    assert open(os.path.join(d, "sample data", "data.txt")).read() == "sample data content\n"

    summary = (
        f"Initial IDs: A={a[:7]}, B={b[:7]}, C={c[:7]}\n"
        f"After rebase: B'={b_new[:7]}, C'={c_new[:7]}, topic stays at {b[:7]}\n"
        f"Ambiguity verified: tag/path collision triggers 'both revision and filename', solved by '--'\n"
        f"Spaces preserved: 'release notes.txt' and 'sample data/data.txt' handled with quotes and '--'\n"
    )
    return summary


def main():
    out = os.path.dirname(os.path.abspath(__file__))
    results = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as d:
            results.append(run_once(d))

    with open(os.path.join(out, "evidence.txt"), "w") as f:
        f.write(subprocess.run(["git", "--version"], capture_output=True, text=True).stdout)
        f.write("python: " + sys.version.split()[0] + "\n\n")
        f.write("expected: In interactive rebase, paths with spaces must be quoted; "
                "'--' is required to eliminate filename vs revision ambiguity; "
                "unrelated refs remain fixed and spaced files are preserved cleanly.\n\n")
        f.write("actual:\n" + results[0])
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
