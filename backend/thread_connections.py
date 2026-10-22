"""A per-thread cache of sqlite3 connections, used where a module kept one connection per language.

Apache runs each process with several threads (eight since 2026-10-22). One sqlite3 connection shared
by threads that read at the same moment fails now and then with "bad parameter or other API misuse":
twelve Line Searches at once gave one HTTP 500 on 2026-10-22. Each thread now opens its own connection,
which costs a file open the first time a thread reads a language.

PerThreadConnections behaves like the dict it replaces. clear() empties the cache of every thread (a
swapped index is reopened everywhere; a thread's old connections are released when that thread next reads,
and closed by sqlite3 when they are garbage collected), pop() and del drop the calling thread's connection.
There is no iteration or len(): no caller needs them, so a copy with dict() fails loudly instead of
silently copying one thread's view.
"""
import threading


class PerThreadConnections:
    def __init__(self):
        self._local = threading.local()
        self._generation = 0

    def _own(self):
        local = self._local
        if getattr(local, 'generation', None) != self._generation:
            local.conns = {}
            local.generation = self._generation
        return local.conns

    def __contains__(self, key):
        return key in self._own()

    def __getitem__(self, key):
        return self._own()[key]

    def __setitem__(self, key, value):
        self._own()[key] = value

    def __delitem__(self, key):
        del self._own()[key]

    def get(self, key, default=None):
        return self._own().get(key, default)

    def pop(self, key, default=None):
        return self._own().pop(key, default)

    def clear(self):
        self._generation += 1
