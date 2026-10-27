"""Keeps a fork from landing while another thread of this process is inside a matrix product.

The numpy in this environment links OpenBLAS with a pool of threads. When a process forks while another of
its threads is inside a BLAS call, the fork can hang for good: measured 2026-10-27 with a thread that
multiplies a 1,000 by 1,000 matrix every 50 ms and a main thread that forks, which stalled within the first
forks. A web worker has several request threads, and the semantic channel multiplies large blocks of
embeddings, so a comparison that starts worker processes (backend/fusion.py) or channel pools could fork
at such a moment.

Code that multiplies large matrices holds `shared()` for the length of the product. Code that forks holds
`exclusive()` for the length of the fork. A fork waits for the products running and keeps new ones from
starting until it is done, so it cannot be starved. Products overlap each other freely.
"""
import contextlib
import os
import threading


class _Gate:
    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._active = 0
        self._forking = False

    def reset(self):
        """In a forked child: no product is running there and no fork is in progress."""
        self._cond = threading.Condition(threading.Lock())
        self._active = 0
        self._forking = False

    @contextlib.contextmanager
    def shared(self):
        with self._cond:
            while self._forking:
                self._cond.wait()
            self._active += 1
        try:
            yield
        finally:
            with self._cond:
                self._active -= 1
                if self._active == 0:
                    self._cond.notify_all()

    @contextlib.contextmanager
    def exclusive(self):
        with self._cond:
            while self._forking:
                self._cond.wait()
            self._forking = True
            while self._active:
                self._cond.wait()
        try:
            yield
        finally:
            with self._cond:
                self._forking = False
                self._cond.notify_all()


gate = _Gate()
shared = gate.shared
exclusive = gate.exclusive

if hasattr(os, 'register_at_fork'):
    os.register_at_fork(after_in_child=gate.reset)
