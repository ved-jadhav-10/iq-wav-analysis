"""An order-preserving thread map for the decode chain's independent cells.

The cells of the hypothesis walk (one code at one phase, one stream's autocorrelation screen) do
not depend on one another, and their heavy parts (the Viterbi kernel, FFTs, the CRC and sync
kernels) run with the GIL released, so a small pool of threads runs them side by side. Results
come back in submission order, so what a caller builds from them is the same as from a plain loop
(no result depends on which thread ran a cell or when).

`SANKET_THREADS` sets the pool size (1 turns the pool off); the default is the logical core count
up to 8. A cell that is itself running on a pool thread maps serially, so nesting cannot deadlock.
"""

import os
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from functools import cache, partial

_inside = threading.local()


@cache
def workers() -> int:
    """Threads the pool runs: `SANKET_THREADS` if set, else the logical cores, at most 8."""
    try:
        return max(1, int(os.environ["SANKET_THREADS"]))
    except (KeyError, ValueError):
        return max(1, min(8, os.cpu_count() or 1))


@cache
def _pool() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(workers(), thread_name_prefix="sanket-cell")


def _in_pool[T, R](fn: Callable[[T], R], item: T) -> R:
    _inside.active = True
    try:
        return fn(item)
    finally:
        _inside.active = False


def pmap[T, R](fn: Callable[[T], R], items: Iterable[T]) -> list[R]:
    """`[fn(x) for x in items]`, run on the pool when there is more than one item and more than
    one worker; the results in the order of `items`."""
    work = list(items)
    if len(work) < 2 or workers() < 2 or getattr(_inside, "active", False):
        return [fn(x) for x in work]
    return list(_pool().map(partial(_in_pool, fn), work))
