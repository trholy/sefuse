# `data_processing.utils.german_funding_fetcher`

Provides a simple HTTP download helper for the German funding source archive.

## Class `FileDownloader`

### `download(url, target_path)`

Downloads a file from `url` and stores it at `target_path`.

#### Behavior

- Creates parent directories for the target file.
- Executes an HTTP GET request with a 30-second timeout.
- Raises an exception for non-success HTTP responses.
- Writes the downloaded response body to disk.
