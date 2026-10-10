"""Bridging APScheduler's threads to the asyncio loop, and logging what goes wrong.

APScheduler calls its jobs from a worker thread, so a coroutine has to be handed
back to the running loop. The future that hands it over used to be discarded, which
meant a scheduled refresh that raised — a failed download, Ollama going away
mid-embed — left no trace at all and the index silently stopped updating. Everything
here exists to make that impossible.

Split out of ``lifespan``, where ``_make_scheduler_fn`` was a closure over the loop.
Taking the loop as an argument is the only change: nothing else was captured, which
is what makes this testable without booting the app.
"""

import asyncio
import functools
import logging
from typing import Callable

logger = logging.getLogger(__name__)


def log_job_failure(job_name: str, future) -> None:
    """Log the outcome of a finished scheduled job when it did not succeed.

    Attached as a done-callback to the future returned by
    ``asyncio.run_coroutine_threadsafe``. APScheduler's own error event only sees the
    wrapper return, so without this a job that raised would be swallowed entirely.

    Args:
        job_name (str): Name of the job, for the log line.
        future (concurrent.futures.Future): The completed future.
    """
    # `cancelled()` is checked first because `exception()` *raises* on a cancelled
    # future, and `concurrent.futures.CancelledError` is not the same class as
    # `asyncio.CancelledError` — catching only the latter would let the error escape
    # the callback, where it would surface as an unhandled exception in the loop.
    if future.cancelled():
        logger.warning("Scheduled job cancelled: %s", job_name)
        return
    error = future.exception()
    if error is not None:
        logger.error("Scheduled job failed: %s", job_name, exc_info=error)


def log_scheduler_error(event) -> None:
    """Log job errors raised inside APScheduler itself (misfires, wrapper faults).

    Registered for ``EVENT_JOB_ERROR``. This covers faults on APScheduler's side of
    the handover; `log_job_failure` covers faults inside the coroutine.
    """
    logger.error(
        "APScheduler job '%s' raised", event.job_id, exc_info=event.exception
    )


def make_scheduler_fn(
    loop: asyncio.AbstractEventLoop,
    coro_fn,
    job_name: str | None = None,
) -> Callable[[], None]:
    """Return a thread-safe callable that schedules ``coro_fn`` on ``loop``.

    The future is kept and given a done-callback, so a job that raises is logged
    rather than discarded — see `log_job_failure`.

    Args:
        loop (asyncio.AbstractEventLoop): The loop the app is running on. Passed in
            rather than fetched here because APScheduler calls the returned function
            from a worker thread, where there is no running loop to discover.
        coro_fn: Zero-argument coroutine function to run.
        job_name (str | None): Name used in the failure log line. Falls back to the
            coroutine's ``__name__``.

    Returns:
        Callable[[], None]: The function to hand to ``scheduler.add_job``.
    """
    name = job_name or getattr(coro_fn, "__name__", "scheduled job")

    def wrapper():
        future = asyncio.run_coroutine_threadsafe(coro_fn(), loop)
        future.add_done_callback(functools.partial(log_job_failure, name))

    return wrapper
