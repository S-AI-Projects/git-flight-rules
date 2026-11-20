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
    git(d, "init", "-b", "main")
    git(d, "config", "user.name", "Course Student")
    git(d, "config", "user.email", "student@example.invalid")

    write(d, "notes.txt", "alpha\n")
    git(d, "add", "notes.txt")
    git(d, "commit", "-m", "A")
    a = git(d, "rev-parse", "HEAD")[0]

    write(d, "notes.txt", "beta\n", "a")
    git(d, "commit", "-am", "B")
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
    tree_c = git(d, "rev-parse", "HEAD^{tree}")[0]

    # Prediction and verification exercise for `git log -S "string to find"`:
    # 1. Search for "alpha":
    # Prediction: Matches commit A (introduced "alpha\n" in notes.txt); does not match B or C.
    # Ref/index/worktree state: Read-only inspection; index and working tree are clean.
    out_alpha, _, _ = git(d, "log", "--format=%H %s", "-S", "alpha")
    assert f"{a} A" in out_alpha
    assert b not in out_alpha
    assert c not in out_alpha

    # 2. Search for "beta":
    # Prediction: Matches commit B (appended "beta\n" to notes.txt); does not match A or C.
    out_beta, _, _ = git(d, "log", "--format=%H %s", "-S", "beta")
    assert f"{b} B" in out_beta
    assert a not in out_beta
    assert c not in out_beta

    # 3. Search for "one":
    # Prediction: Matches commit C (added "one\n" in todo.txt); does not match A or B.
    out_one, _, _ = git(d, "log", "--format=%H %s", "-S", "one")
    assert f"{c} C" in out_one
    assert a not in out_one
    assert b not in out_one

    # 4. Search on topic branch:
    # On `topic`, commit C is not reachable.
    # Prediction: `git log -S "one"` on `topic` yields empty output.
    # With `--all`, commit C is discovered.
    git(d, "switch", "topic")
    out_topic_one, _, _ = git(d, "log", "--oneline", "-S", "one")
    assert out_topic_one == ""

    out_all_one, _, _ = git(d, "log", "--format=%H %s", "--all", "-S", "one")
    assert f"{c} C" in out_all_one

    git(d, "switch", "main")

    # State facts:
    # Fact 1: Read-only query leaves repository tree hash unchanged
    assert git(d, "rev-parse", "HEAD^{tree}")[0] == tree_c
    # Fact 2: Working tree and index remain clean
    assert git(d, "status", "--porcelain")[0] == ""
    # Fact 3: Branches remain fixed at expected commits
    assert git(d, "rev-parse", "main")[0] == c
    assert git(d, "rev-parse", "topic")[0] == b

    summary = (
        f"Initial IDs: A={a[:7]}, B={b[:7]}, C={c[:7]}\n"
        f"git log -S 'alpha' identified commit {a[:7]} (Commit A)\n"
        f"git log -S 'beta' identified commit {b[:7]} (Commit B)\n"
        f"git log -S 'one' identified commit {c[:7]} (Commit C)\n"
        f"On branch 'topic', -S 'one' is empty; with --all it identifies {c[:7]}\n"
        f"Working tree, index, and refs remained clean and unmodified\n"
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
        f.write("expected: git log -S <string> accurately identifies the exact commit introducing "
                "or removing the target string; read-only inspection leaves working tree, index, "
                "and refs unmodified.\n\n")
        f.write("actual:\n" + results[0])
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
