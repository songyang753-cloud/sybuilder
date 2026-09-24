"""Cooperating mutation tools share tree + canonical-target locks and private state.

Not a hostile-user sandbox: editors outside this protocol may still race a write.
Never recover content whose current hash is not a recorded original/mutated hash.
"""
from contextlib import ExitStack, contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


def state_path(kind, target):
    root = Path(tempfile.gettempdir()) / ('sybuilder-mutations-' + str(os.getuid()))
    root.mkdir(mode=0o700, exist_ok=True)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError('UNABLE: mutation state directory is not private/owned')
    key = hashlib.sha256(str(Path(target).resolve()).encode()).hexdigest()
    return root / (kind + '-' + key)


def safe_open(path, flags):
    fd = os.open(path, flags | os.O_NOFOLLOW, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
        os.close(fd)
        raise RuntimeError('UNABLE: untrusted mutation state file')
    return os.fdopen(fd, 'r+' if flags & os.O_RDWR else 'r')


def tree_root(target):
    path = Path(target).resolve()
    start = path if path.is_dir() else path.parent
    for parent in (start, *start.parents):
        if (parent / 'SKILL.md').is_file() or (parent / '.git').exists():
            return parent
    return start


@contextmanager
def locked_targets(targets):
    targets = [Path(p).resolve() for p in targets]
    trees = {tree_root(p) for p in targets}
    # Stable order: all tree locks first, then canonical target locks.
    paths = sorted({state_path('tree', p) for p in trees}) + sorted({state_path('target', p) for p in targets})
    with ExitStack() as stack:
        for path in paths:
            handle = stack.enter_context(safe_open(path, os.O_RDWR | os.O_CREAT))
            fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def save_journal(target, original, mutated):
    path = state_path('journal', target)
    record = {'version': 1, 'target': str(Path(target).resolve()), 'orig': original,
              'originalHash': text_hash(original), 'mutatedHash': text_hash(mutated)}
    fd, temp = tempfile.mkstemp(prefix='.journal-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(record, stream, ensure_ascii=False)
            stream.flush(); os.fsync(stream.fileno())
        os.link(temp, path)  # complete publication, no overwrite of previous recovery evidence
    finally:
        os.unlink(temp)


def recover(target):
    target = Path(target).resolve()
    path = state_path('journal', target)
    if not path.exists() and not path.is_symlink():
        # Old, unauthenticated journals need human review, never auto-import them.
        legacy = Path(tempfile.gettempdir()) / ('product-flow-rt-journal-' + hashlib.sha1(str(target).encode()).hexdigest()[:16] + '.json')
        if legacy.exists() or legacy.is_symlink():
            raise RuntimeError('UNABLE: legacy recovery journal needs manual review; target unchanged')
        return
    with safe_open(path, os.O_RDONLY) as stream:
        record = json.load(stream)
    if (record.get('version') != 1 or record.get('target') != str(target)
            or not isinstance(record.get('orig'), str)
            or text_hash(record['orig']) != record.get('originalHash')):
        raise RuntimeError('UNABLE: recovery target/content binding mismatch; journal retained')
    current = target.read_text(encoding='utf-8')
    if text_hash(current) not in (record['originalHash'], record.get('mutatedHash')):
        raise RuntimeError('UNABLE: target changed outside mutation; journal retained, no overwrite')
    if current != record['orig']:
        with target.open('w', encoding='utf-8') as stream:
            stream.write(record['orig']); stream.flush(); os.fsync(stream.fileno())
        if text_hash(target.read_text(encoding='utf-8')) != record['originalHash']:
            raise RuntimeError('UNABLE: recovery verification failed; journal retained')
    path.unlink()


if __name__ == '__main__':
    import sys
    if '--self-test' not in sys.argv:
        sys.exit('Use --self-test; this is a shared internal module.')
    import runpy
    import unittest
    from _workflow import suite_script
    try:
        tests = runpy.run_path(str(suite_script('test-review-boundaries.py')))
        suite = unittest.TestSuite(tests['Boundaries'](name) for name in (
            'test_recovery_binding_and_user_changes_never_overwritten',
            'test_shared_tree_lock_serializes_different_targets_and_hard_kill_recovers'))
        class Results(unittest.TextTestResult):
            def addSuccess(self, test):
                super().addSuccess(test)
                print('  ✅ ' + test._testMethodName + '（含反例）', flush=True)
        result = unittest.TextTestRunner(resultclass=Results).run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
    except (ValueError, OSError) as exc:
        print('UNABLE: ' + str(exc), file=sys.stderr)
        sys.exit(2)
