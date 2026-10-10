# `data_processing.utils.german_funding_fetcher`

HTTP file downloader for the German federal funding dataset ZIP.

---

## Class `FileDownloader`

Downloads a remote file via HTTP GET and writes it to disk.

### `download(url: str, target_path: Path) -> None`

Fetch a URL and stream the response body to `target_path`.

Sends a browser-like `User-Agent`/`Accept` header set and streams the response to disk in 64 KiB chunks (`stream=True`), so a large export is never buffered entirely in memory. Request timeout is 120 seconds.

**Parameters:**

- `url` (`str`): HTTP/HTTPS URL to download.
- `target_path` (`Path`): Local path where the downloaded content is written; parent directories are created automatically.

**Returns:** `None`

**Raises:** `requests.HTTPError` — If the server returns a non-2xx status code (via `response.raise_for_status()`).
