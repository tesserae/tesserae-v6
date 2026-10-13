"""File operations that give the same result under any server locale.

The web process may run with an ASCII filesystem encoding (Apache starts it
with LANG set to C, and the encoding is fixed when the interpreter starts), in
which a str path holding Greek letters cannot be encoded and any os call on it
raises UnicodeEncodeError. Thirty-six Greek texts have Greek letters in their
file names. Every helper here turns the path into UTF-8 bytes first and calls
the operating system with bytes, which no locale can break.

Names read from a directory are returned as ordinary Unicode str (decoded as
UTF-8), the same under every locale. A name that is not valid UTF-8 is returned
with surrogateescape, so it can still be turned back into the original bytes.
Under a UTF-8 locale every helper behaves exactly like the os function it wraps.
"""
import glob as _glob
import os
import shutil as _shutil


def fs_path(p):
    """Return p as bytes (UTF-8, surrogate escapes restored), for any os call."""
    if isinstance(p, bytes):
        return p
    return os.fspath(p).encode('utf-8', 'surrogateescape')


def fs_name(b):
    """Return a name or path read from the file system as str, the same under every locale."""
    if isinstance(b, str):
        return b
    return b.decode('utf-8', 'surrogateescape')


def fs_join(*parts):
    """os.path.join for str parts, returning str."""
    return os.path.join(*[fs_name(p) for p in parts])


def exists(p):
    """os.path.exists on a path that may hold non-ASCII letters."""
    return os.path.exists(fs_path(p))


def isfile(p):
    """os.path.isfile on a path that may hold non-ASCII letters."""
    return os.path.isfile(fs_path(p))


def isdir(p):
    """os.path.isdir on a path that may hold non-ASCII letters."""
    return os.path.isdir(fs_path(p))


def getsize(p):
    """os.path.getsize on a path that may hold non-ASCII letters."""
    return os.path.getsize(fs_path(p))


def getmtime(p):
    """os.path.getmtime on a path that may hold non-ASCII letters."""
    return os.path.getmtime(fs_path(p))


def stat(p):
    """os.stat on a path that may hold non-ASCII letters."""
    return os.stat(fs_path(p))


def realpath(p):
    """os.path.realpath returning str, for a path that may hold non-ASCII letters."""
    return fs_name(os.path.realpath(fs_path(p)))


def listdir_text(d):
    """The names in directory d as Unicode str, decoded as UTF-8 under every locale."""
    return [fs_name(n) for n in os.listdir(fs_path(d))]


def scandir_text(d):
    """(name, is_file) pairs for directory d, names as Unicode str."""
    with os.scandir(fs_path(d)) as it:
        return [(fs_name(e.name), e.is_file()) for e in it]


def walk(top):
    """os.walk over top, yielding (dirpath, dirnames, filenames) as Unicode str."""
    for root, dirs, files in os.walk(fs_path(top)):
        yield fs_name(root), [fs_name(d) for d in dirs], [fs_name(f) for f in files]


def glob(pattern):
    """glob.glob returning Unicode str, for a pattern that may hold non-ASCII letters."""
    return [fs_name(p) for p in _glob.glob(fs_path(pattern))]


def open_text(path, mode='r', encoding='utf-8', errors=None, **kw):
    """open() through the bytes path; text modes default to UTF-8 so the locale never matters."""
    if 'b' in mode:
        return open(fs_path(path), mode, **kw)
    return open(fs_path(path), mode, encoding=encoding, errors=errors, **kw)


def copyfile(src, dst):
    """shutil.copyfile through bytes paths."""
    return _shutil.copyfile(fs_path(src), fs_path(dst))


def native_path(p):
    """Return p as the str this process's own os calls accept (os.fsdecode of the bytes).

    Use it for a path handed to code that calls open() on a plain str. Under an
    ASCII file system encoding a Greek name comes back with surrogate escapes,
    which open() turns back into the original bytes; under UTF-8 it is just the name."""
    return os.fsdecode(fs_path(p))
