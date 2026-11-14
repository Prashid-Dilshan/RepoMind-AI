import os
import shutil
import stat


def _on_rm_error(func, path, _exc_info):
    # Windows marks files inside .git as read-only; clear the flag and retry.
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def remove_dir(path):
    if os.path.exists(path):
        shutil.rmtree(path, onerror=_on_rm_error)


def dir_size_bytes(path, skip=(".git",)):
    total = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in skip]
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total
