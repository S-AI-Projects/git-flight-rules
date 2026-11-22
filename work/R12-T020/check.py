import subprocess, os, tempfile, json, sys

def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, shell=True, check=True, capture_output=True, text=True)

def git_init_repo(repo_path):
    run('git init -q', cwd=repo_path)
    run('git config user.name "Course Student"', cwd=repo_path)
    run('git config user.email "student@example.invalid"', cwd=repo_path)

def make_commit(repo_path, message, actions):
    for action in actions:
        with open(os.path.join(repo_path, action['path']), 'a') as f:
            f.write(action['content'])
        run(f'git add {action["path"]}', cwd=repo_path)
    run(f'git commit -q -m "{message}"', cwd=repo_path)

def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Step 1: create source repo with commits A, B, C and branch topic at B
        src = os.path.join(temp_dir, 'src')
        os.mkdir(src)
        git_init_repo(src)
        # Commit A
        make_commit(src, 'A create notes.txt', [
            {'path': 'notes.txt', 'content': 'alpha\n'}
        ])
        # Commit B
        make_commit(src, 'B append beta', [
            {'path': 'notes.txt', 'content': 'beta\n'}
        ])
        # Create branch topic at this point (B)
        run('git checkout -b topic', cwd=src)
        # Commit C on main (need to switch back to main first)
        run('git checkout main', cwd=src)
        make_commit(src, 'C add todo.txt', [
            {'path': 'todo.txt', 'content': 'one\n'}
        ])
        # Step 2: create bare remote and push all refs
        bare = os.path.join(temp_dir, 'remote.git')
        run('git clone --bare . ' + bare, cwd=src)
        # Step 3: clone the remote into a new directory (exercise)
        clone_dir = os.path.join(temp_dir, 'clone')
        run(f'git clone {bare} {clone_dir}')
        # Assertions
        # 3a: HEAD points to refs/heads/main
        head_ref = run('git rev-parse --abbrev-ref HEAD', cwd=clone_dir).stdout.strip()
        assert head_ref == 'main', f'HEAD is {head_ref}, expected main'
        # 3b: notes.txt contains both lines
        notes = open(os.path.join(clone_dir, 'notes.txt')).read()
        assert notes == 'alpha\nbeta\n', f'notes.txt content mismatch: {notes!r}'
        # 3c: todo.txt exists with correct content
        todo = open(os.path.join(clone_dir, 'todo.txt')).read()
        assert todo == 'one\n', f'todo.txt content mismatch: {todo!r}'
        # 3d: branch topic exists locally after clone (should be remote tracking)
        branches = run('git branch -a', cwd=clone_dir).stdout
        assert 'remotes/origin/topic' in branches, 'topic branch missing in clone'
        # Capture dynamic object IDs for evidence
        head_hash = run('git rev-parse HEAD', cwd=clone_dir).stdout.strip()
        # Save evidence
        evidence_dir = os.path.join(os.getcwd(), 'work', 'R12-T020')
        os.makedirs(evidence_dir, exist_ok=True)
        with open(os.path.join(evidence_dir, 'evidence.log'), 'w') as f:
            json.dump({
                'head_ref': head_ref,
                'head_hash': head_hash,
                'notes_content': notes,
                'todo_content': todo,
                'branches': branches,
            }, f, indent=2)
        # Save tool versions
        with open(os.path.join(evidence_dir, 'tool_versions.txt'), 'w') as f:
            f.write('git --version\n')
            f.write(subprocess.run('git --version', shell=True, capture_output=True, text=True).stdout)
            f.write('python --version\n')
            f.write(subprocess.run('python --version', shell=True, capture_output=True, text=True).stdout)
        # Summary JSON
        with open(os.path.join(evidence_dir, 'check_summary.json'), 'w') as f:
            json.dump({'status': 'pass'}, f)

if __name__ == '__main__':
    main()
