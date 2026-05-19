import sys
import os

os.environ.setdefault('TERM', 'dumb')
os.environ.setdefault('NO_COLOR', '1')
os.environ.setdefault('FORCE_COLOR', '0')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONDONTWRITEBYTECODE', '1')


class _PyiDummyStream:
    def write(self, s):
        return len(s) if s else 0

    def flush(self):
        pass

    def isatty(self):
        return False

    def fileno(self):
        return -1

    @property
    def closed(self):
        return False

    def close(self):
        pass

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False

    def read(self, size=-1):
        return ''

    def readline(self, size=-1):
        return ''

    def readlines(self, sizehint=-1):
        return []


if sys.stdout is None:
    sys.stdout = _PyiDummyStream()
if sys.stderr is None:
    sys.stderr = _PyiDummyStream()
if sys.stdin is None:
    sys.stdin = _PyiDummyStream()
