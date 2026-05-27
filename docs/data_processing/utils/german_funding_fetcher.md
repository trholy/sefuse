# `data_processing.utils.german_funding_fetcher`

HTTP file downloader for the German federal funding dataset ZIP.

---

## Class `FileDownloader`

Downloads a remote file via HTTP GET and writes it to disk.

### `download(url: str, target_path: Path) -> None`

Fetch a URL and save the response body to `target_path`.

**Parameters:**

- `url` (`str`): HTTP/HTTPS URL to download.
- `target_path` (`Path`): Local path where the downloaded content is written; parent directories are created automatically.

**Returns:** `None`

**Raises:** `requests.HTTPError` — If the server returns a non-2xx status code (via `response.raise_for_status()`).
