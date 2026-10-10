# `fastapi.utils.job_runner`

Bridges APScheduler's worker threads to the asyncio event loop and logs scheduled jobs that fail.

APScheduler calls its jobs from a worker thread, so a coroutine has to be handed back to the running loop. If the future that hands it over is discarded, a scheduled refresh that raises — a failed download, or Ollama going away during an embedding run — leaves no trace and the index stops updating without notice. The functions here keep that future and log its outcome.

`main.py` uses `make_scheduler_fn` for every cron job it registers and registers `log_scheduler_error` for `EVENT_JOB_ERROR`.

---

## Functions

### `make_scheduler_fn(loop, coro_fn, job_name=None) -> Callable[[], None]`

Return a thread-safe callable that schedules `coro_fn` on `loop`.

The future returned by `asyncio.run_coroutine_threadsafe` is kept and given `log_job_failure` as a done-callback, so a job that raises is logged.

**Parameters:**

- `loop` (`asyncio.AbstractEventLoop`): The loop the app is running on. It is passed in because APScheduler calls the returned function from a worker thread, where there is no running loop to discover.
- `coro_fn`: Zero-argument coroutine function to run.
- `job_name` (`str | None`): Name used in the failure log line. Falls back to the coroutine's `__name__`.

**Returns:** `Callable[[], None]` — the function to hand to `scheduler.add_job`.

---

### `log_job_failure(job_name: str, future) -> None`

Log the outcome of a finished scheduled job when it did not succeed.

Attached as a done-callback to the future from `asyncio.run_coroutine_threadsafe`. APScheduler's own error event only sees the wrapper return, so it does not report an exception raised inside the coroutine.

**Parameters:**

- `job_name` (`str`): Name of the job, for the log line.
- `future` (`concurrent.futures.Future`): The completed future.

---

### `log_scheduler_error(event) -> None`

Log job errors raised inside APScheduler itself, such as misfires and faults in the wrapper.

Registered for `EVENT_JOB_ERROR`. It covers faults on APScheduler's side of the handover; `log_job_failure` covers faults inside the coroutine.
