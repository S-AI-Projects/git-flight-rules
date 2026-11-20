import os
import subprocess
import sys
import tempfile

WRONG = ("Wrong Name", "wrong@example.invalid")
RIGHT = ("Course Student", "student@example.invalid")


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, check=True,
                       capture_output=True, text=True)
    return r.stdout.strip()


def write(cwd, name, text, mode="w"):
    with open(os.path.join(cwd, name), mode) as f:
        f.write(text)


def set_user(d, who):
    git(d, "config", "user.name", who[0])
    git(d, "config", "user.email", who[1])


def build(d):
    git(d, "init", "-b", "main")
    set_user(d, RIGHT)
    write(d, "notes.txt", "alpha\n")
    git(d, "add", "notes.txt")
    git(d, "commit", "-m", "A")
    write(d, "notes.txt", "beta\n", "a")
    git(d, "commit", "-am", "B")
    git(d, "branch", "topic")
    b = git(d, "rev-parse", "HEAD")
    set_user(d, WRONG)
    write(d, "todo.txt", "one\n")
    git(d, "add", "todo.txt")
    git(d, "commit", "-m", "C")
    return b


def run_once(d, variant):
    b = build(d)
    c_old = git(d, "rev-parse", "HEAD")
    tree_old = git(d, "rev-parse", "HEAD^{tree}")
    assert git(d, "log", "-1", "--format=%an <%ae>") == "Wrong Name <wrong@example.invalid>"

    set_user(d, RIGHT)
    if variant == "reset-author":
        git(d, "commit", "--amend", "--reset-author", "--no-edit")
    else:
        git(d, "commit", "--amend", "--no-edit",
            "--author", "Course Student <student@example.invalid>")

    c_new = git(d, "rev-parse", "HEAD")
    before = f"main -> {c_old[:7]} (author: Wrong Name)"
    after = f"main -> {c_new[:7]} (author: Course Student)"

    # refs
    assert c_new != c_old
    assert git(d, "rev-parse", "main") == c_new
    assert git(d, "rev-parse", "topic") == b
    assert git(d, "symbolic-ref", "HEAD") == "refs/heads/main"
    # ancestry
    assert git(d, "rev-parse", "HEAD~1") == b
    assert subprocess.run(["git", "merge-base", "--is-ancestor", c_old, "main"],
                          cwd=d).returncode == 1
    git(d, "cat-file", "-e", c_old)
    # author
    assert git(d, "log", "-1", "--format=%an <%ae>") == "Course Student <student@example.invalid>"
    # index and working tree
    assert git(d, "rev-parse", "HEAD^{tree}") == tree_old
    assert git(d, "status", "--porcelain") == ""
    assert open(os.path.join(d, "notes.txt")).read() == "alpha\nbeta\n"
    assert open(os.path.join(d, "todo.txt")).read() == "one\n"
    log = git(d, "log", "--oneline", "--graph", "--all", "--decorate")
    return before, after, log


def main():
    out = os.path.dirname(os.path.abspath(__file__))
    lines = []
    for variant in ("reset-author", "author-flag"):
        for _ in range(2):
            with tempfile.TemporaryDirectory() as d:
                before, after, log = run_once(d, variant)
        lines.append(f"[{variant}]\nbefore: {before}\nafter:  {after}\n{log}\n")
    with open(os.path.join(out, "evidence.txt"), "w") as f:
        f.write(subprocess.run(["git", "--version"], capture_output=True, text=True).stdout)
        f.write("python: " + sys.version.split()[0] + "\n\n")
        f.write("expected: new commit ID for C; main moves; topic stays at B; "
                "HEAD stays on main; tree, index and files unchanged\n\n")
        f.write("actual:\n" + "\n".join(lines))
    print("ALL CHECKS PASSED")


main()
	
