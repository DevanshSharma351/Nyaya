"""Serialised access to the local transformer models.

Both the cross-encoder reranker and the entailment pipeline are loaded once and
cached, then called from worker threads via `asyncio.to_thread` so they do not
block the event loop. That combination - one shared model instance, several
threads - is not safe, and on Apple Silicon's Metal backend it does not fail
gracefully: it segfaults the whole process.

It surfaced when this machine moved from an x86-64 Python running under Rosetta
to a native arm64 one. Under Rosetta `torch.backends.mps.is_available()` was
False, everything ran on CPU, and concurrent calls were merely racy rather than
fatal. Native, the same code selects `mps:0` and four concurrent searches kill
the API instantly - which is exactly what the retrieval module produces, since
React double-invokes effects in development and the page seeds a query on mount.

One lock covers both models rather than one each. They contend for the same GPU
regardless, inference here is short, and the two never run concurrently in the
pipeline anyway - retrieval reranks, then the validator checks entailment. A
lock per model would buy nothing and leave two things to reason about.

The lock is held inside the worker thread, so the event loop is never blocked;
other requests continue to be served while one waits its turn.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

_GPU = threading.Lock()


def exclusive[T](call: Callable[[], T]) -> T:
    """Run `call` with exclusive access to the local models."""
    with _GPU:
        return call()


__all__ = ["exclusive"]
