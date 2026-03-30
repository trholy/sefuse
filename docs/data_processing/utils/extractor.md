# `data_processing.utils.extractor`

Contains ZIP archive extraction utilities used by the German funding ingestion flow.

## Class `ZipExtractor`

### `extract_file(zip_path, filename, target_path)`

Extracts a specific file from a ZIP archive and writes it to a target path.

#### Behavior

- Raises `FileNotFoundError` if the ZIP archive does not exist.
- Opens the archive and verifies that `filename` is present.
- Raises `ValueError` with the available archive contents when the requested file is missing.
- Writes the extracted file bytes to `target_path`, creating parent directories as needed.
