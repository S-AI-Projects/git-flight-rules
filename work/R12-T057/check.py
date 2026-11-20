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


def setup_repos(root_dir):
    # Step 2: Use a temporary repository with branch main, author Course Student student@example.invalid,
    # and three commits: A creates notes.txt with "alpha\n"; B appends "beta\n";
    # C adds todo.txt with "one\n". Create branch topic at B.
    # If a remote is needed, use a second local bare repository and a file:// URL.
    bare_dir = os.path.join(root_dir, "remote.git")
    git(root_dir, "init", "--bare", "-b", "main", bare_dir)

    work_dir = os.path.join(root_dir, "repo")
    git(root_dir, "init", "-b", "main", work_dir)
    git(work_dir, "config", "user.name", "Course Student")
    git(work_dir, "config", "user.email", "student@example.invalid")

    write(work_dir, "notes.txt", "alpha\n")
    git(work_dir, "add", "notes.txt")
    git(work_dir, "commit", "-m", "A")
    a = git(work_dir, "rev-parse", "HEAD")[0]

    git(work_dir, "remote", "add", "origin", f"file://{bare_dir}")
    git(work_dir, "push", "-u", "origin", "main")

    write(work_dir, "notes.txt", "beta\n", "a")
    git(work_dir, "commit", "-am", "B")
    b = git(work_dir, "rev-parse", "HEAD")[0]
    git(work_dir, "branch", "topic")
    git(work_dir, "push", "origin", "topic")

    write(work_dir, "todo.txt", "one\n")
    git(work_dir, "add", "todo.txt")
    git(work_dir, "commit", "-m", "C")
    c = git(work_dir, "rev-parse", "HEAD")[0]

    return work_dir, bare_dir, a, b, c


def run_once(root_dir):
    work_dir, bare_dir, a, b, c = setup_repos(root_dir)

    # State fact 1: Initial ref state
    assert git(work_dir, "rev-parse", "main")[0] == c
    assert git(work_dir, "rev-parse", "topic")[0] == b
    assert git(bare_dir, "rev-parse", "main")[0] == a
    assert git(bare_dir, "rev-parse", "topic")[0] == b

    # Precondition violation construction:
    # A tag named 'topic' is created on the remote repository with the same name as branch 'topic'.
    # This creates a collision between refs/heads/topic and refs/tags/topic.
    git(bare_dir, "tag", "topic", a)

    # Also on local work repository, create tag 'topic' at commit A
    git(work_dir, "tag", "topic", a)

    # Advance branch topic locally with a new commit D
    git(work_dir, "switch", "topic")
    write(work_dir, "notes.txt", "gamma\n", "a")
    git(work_dir, "commit", "-am", "D")
    d_commit = git(work_dir, "rev-parse", "HEAD")[0]

    # Command anchor 1 (violated precondition / failed push):
    # Running `git push origin topic` fails with a non-zero exit code because 'topic' matches both refs
    out, err, code = git(work_dir, "push", "origin", "topic", check=False)
    assert code != 0
    # Must capture nonzero exit and not rely on strict byte-for-byte wording:
    assert "matches more than one" in err
    assert "failed to push some refs" in err

    # Verify that remote branch topic remained at B (push failed)
    assert git(bare_dir, "rev-parse", "refs/heads/topic")[0] == b

    # Command anchor 2 (repaired push using smallest correction):
    # Explicitly specify the full ref path: `git push origin refs/heads/topic`
    out_rep, err_rep, code_rep = git(work_dir, "push", "origin", "refs/heads/topic")
    assert code_rep == 0

    # Done when assertions:
    # 1. Bad case failed for the stated reason (ref collision), repaired case succeeded.
    # 2. Assert at least three meaningful state facts:
    # Fact 1: Remote branch was updated to D
    assert git(bare_dir, "rev-parse", "refs/heads/topic")[0] == d_commit
    # Fact 2: Remote tag 'topic' stayed fixed at original commit A
    assert git(bare_dir, "rev-parse", "refs/tags/topic")[0] == a
    # Fact 3: Unrelated ref 'main' on remote and local stayed fixed
    assert git(bare_dir, "rev-parse", "refs/heads/main")[0] == a
    assert git(work_dir, "rev-parse", "refs/heads/main")[0] == c

    summary = (
        f"Initial IDs: A={a[:7]}, B={b[:7]}, C={c[:7]}, D={d_commit[:7]}\n"
        f"Collision: both refs/heads/topic and refs/tags/topic exist\n"
        f"Unqualified push 'git push origin topic' exited with non-zero ({code})\n"
        f"Stderr captured: matches more than one; failed to push some refs\n"
        f"Repaired push 'git push origin refs/heads/topic' succeeded (exit {code_rep})\n"
        f"Remote refs/heads/topic updated to {d_commit[:7]}, while refs/tags/topic stays at {a[:7]}\n"
    )
    return summary


def main():
    out = os.path.dirname(os.path.abspath(__file__))
    results = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as root_dir:
            results.append(run_once(root_dir))

    with open(os.path.join(out, "evidence.txt"), "w") as f:
        f.write(subprocess.run(["git", "--version"], capture_output=True, text=True).stdout)
        f.write("python: " + sys.version.split()[0] + "\n\n")
        f.write("expected: Pushing a branch when a tag shares the same name fails with "
                "'matches more than one'; specifying refs/heads/<branch> resolves the ambiguity "
                "and updates the branch while leaving the tag and other refs intact.\n\n")
        f.write("actual:\n" + results[0])
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
