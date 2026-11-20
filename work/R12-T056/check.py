import os
import subprocess
import sys
import tempfile

FIXED_ENV = {
    "GIT_AUTHOR_NAME": "Course Student",
    "GIT_AUTHOR_EMAIL": "student@example.invalid",
    "GIT_COMMITTER_NAME": "Course Student",
    "GIT_COMMITTER_EMAIL": "student@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}


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
    git(work_dir, "commit", "-m", "A", env=FIXED_ENV)
    a = git(work_dir, "rev-parse", "HEAD")[0]

    # Add remote and push commit A as upstream tracking branch
    git(work_dir, "remote", "add", "origin", f"file://{bare_dir}")
    git(work_dir, "push", "-u", "origin", "main")

    # Commit B and branch topic at B
    write(work_dir, "notes.txt", "beta\n", "a")
    git(work_dir, "commit", "-am", "B", env=FIXED_ENV)
    b = git(work_dir, "rev-parse", "HEAD")[0]
    git(work_dir, "branch", "topic")

    # Commit C
    write(work_dir, "todo.txt", "one\n")
    git(work_dir, "add", "todo.txt")
    git(work_dir, "commit", "-m", "C", env=FIXED_ENV)
    c = git(work_dir, "rev-parse", "HEAD")[0]

    return work_dir, bare_dir, a, b, c


def run_comparison(root_dir):
    # Method 1: (main)$ git rebase -i @{u} (squashing C into B)
    work_dir_1 = os.path.join(root_dir, "method1")
    os.makedirs(work_dir_1)
    w1, b1, a1, b1_id, c1 = setup_repos(work_dir_1)

    tree_c1 = git(w1, "rev-parse", "HEAD^{tree}")[0]

    # Squash C into B using interactive rebase (put editor script outside work tree)
    editor_script = os.path.join(root_dir, "ed.py")
    with open(editor_script, "w") as fp:
        fp.write("import sys\n"
                 "with open(sys.argv[1], 'r') as f:\n"
                 "    lines = f.readlines()\n"
                 "with open(sys.argv[1], 'w') as f:\n"
                 "    for l in lines:\n"
                 "        if ' C' in l:\n"
                 "            f.write(l.replace('pick ', 'squash '))\n"
                 "        else:\n"
                 "            f.write(l)\n")

    git(w1, "rebase", "-i", "@{u}", env={"GIT_SEQUENCE_EDITOR": f"python3 {editor_script}", "GIT_EDITOR": "true"})

    tree_1 = git(w1, "rev-parse", "HEAD^{tree}")[0]
    head_1 = git(w1, "rev-parse", "HEAD")[0]
    parent_1 = git(w1, "rev-parse", "HEAD~1")[0]
    upstream_1 = git(w1, "rev-parse", "@{u}")[0]
    topic_1 = git(w1, "rev-parse", "topic")[0]
    msg_1 = git(w1, "log", "-1", "--format=%B")[0]
    status_1 = git(w1, "status", "--porcelain")[0]

    # Method 2: (main)$ git reset --soft @{u} && git commit -m "B and C combined"
    work_dir_2 = os.path.join(root_dir, "method2")
    os.makedirs(work_dir_2)
    w2, b2, a2, b2_id, c2 = setup_repos(work_dir_2)

    tree_c2 = git(w2, "rev-parse", "HEAD^{tree}")[0]

    # Execute reset --soft @{u}
    git(w2, "reset", "--soft", "@{u}")
    # Observable difference during execution:
    # `git reset --soft @{u}` immediately stages all unpushed changes into the index
    status_soft = git(w2, "status", "--porcelain")[0]
    assert "M  notes.txt" in status_soft
    assert "A  todo.txt" in status_soft

    git(w2, "commit", "-m", "B and C combined", env=FIXED_ENV)

    tree_2 = git(w2, "rev-parse", "HEAD^{tree}")[0]
    head_2 = git(w2, "rev-parse", "HEAD")[0]
    parent_2 = git(w2, "rev-parse", "HEAD~1")[0]
    upstream_2 = git(w2, "rev-parse", "@{u}")[0]
    topic_2 = git(w2, "rev-parse", "topic")[0]
    msg_2 = git(w2, "log", "-1", "--format=%B")[0]
    status_2 = git(w2, "status", "--porcelain")[0]

    # Done when assertions:
    # 1. Equivalent starting fixtures:
    assert a1 == a2
    assert b1_id == b2_id
    assert c1 == c2
    assert tree_c1 == tree_c2

    # 2. Both workflows end up with equivalent final trees matching original commit C tree
    assert tree_1 == tree_c1
    assert tree_2 == tree_c2
    assert tree_1 == tree_2

    # 3. Both combined commits sit directly on top of upstream @{u} (commit A)
    assert parent_1 == upstream_1 == a1
    assert parent_2 == upstream_2 == a2

    # 4. Unrelated refs (topic) stayed fixed at commit B in both fixtures
    assert topic_1 == b1_id
    assert topic_2 == b2_id

    # 5. Index & working tree clean at completion
    assert status_1 == ""
    assert status_2 == ""

    # 6. Observable differences demonstrated:
    # - In method 1 (rebase -i), commit log message retains combined messages of B and C
    assert "B" in msg_1 and "C" in msg_1
    # - In method 2 (reset --soft), the index is populated with unpushed changes before a new single commit is authored
    assert "M  notes.txt" in status_soft and "A  todo.txt" in status_soft
    assert msg_2 == "B and C combined"

    summary = (
        f"Fixture Initial: A={a1[:7]} (pushed @{{u}}), B={b1_id[:7]}, C={c1[:7]}\n"
        f"Unpushed commits before: C, B\n"
        f"Method 1 (git rebase -i @{{u}}):\n"
        f"  Combined commit: {head_1[:7]}, parent: {parent_1[:7]} (@{{u}})\n"
        f"  Tree: {tree_1[:7]} (matches C)\n"
        f"  Preserved messages of both B and C in commit log\n"
        f"Method 2 (git reset --soft @{{u}}):\n"
        f"  Staged index before commit: 'M notes.txt', 'A todo.txt'\n"
        f"  Combined commit: {head_2[:7]}, parent: {parent_2[:7]} (@{{u}})\n"
        f"  Tree: {tree_2[:7]} (matches C)\n"
        f"Unrelated ref 'topic' stayed fixed at {b1_id[:7]} in both workflows\n"
    )
    return summary


def main():
    out = os.path.dirname(os.path.abspath(__file__))
    results = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as root_dir:
            results.append(run_comparison(root_dir))

    with open(os.path.join(out, "evidence.txt"), "w") as f:
        f.write(subprocess.run(["git", "--version"], capture_output=True, text=True).stdout)
        f.write("python: " + sys.version.split()[0] + "\n\n")
        f.write("expected: Both git rebase -i @{u} and git reset --soft @{u} combine unpushed commits "
                "into a single commit atop @{u} with matching trees; rebase preserves commit history "
                "messages while reset --soft stages changes directly into index.\n\n")
        f.write("actual:\n" + results[0])
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
