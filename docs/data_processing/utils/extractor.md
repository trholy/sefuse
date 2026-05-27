# `data_processing.utils.extractor`

ZIP archive extraction utility for the German funding pipeline.

---

## Class `ZipExtractor`

Extracts a single named file from a ZIP archive to a target path.

### `extract_file(zip_path: Path, filename: str, target_path: Path) -> None`

Extract one file from a ZIP archive and write it to `target_path`.

**Parameters:**

- `zip_path` (`Path`): Path to the ZIP archive.
- `filename` (`str`): Name of the file to extract from within the archive.
- `target_path` (`Path`): Destination path where the extracted bytes are written; parent directories are created automatically.

**Returns:** `None`

**Raises:**

- `FileNotFoundError` — If the ZIP archive at `zip_path` does not exist.
- `ValueError` — If `filename` is not found inside the archive (error message lists available files).
