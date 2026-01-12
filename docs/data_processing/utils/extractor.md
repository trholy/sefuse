# Zip Extractor Module

Utility class for extracting files from ZIP archives. This module handles the extraction of specific files from compressed data packages in the data processing pipeline.

---

## ZipExtractor

Class for extracting specific files from ZIP archives to local storage.

### Methods

#### extract_file

Extracts a specific file from a ZIP archive and saves it to the target location.

##### Parameters

- `zip_path` (Path): The path to the ZIP archive file.
- `filename` (str): The name of the file to extract from the archive.
- `target_path` (Path): The local file path where the extracted content should be saved.

##### Returns

- `None`: This method performs file I/O operations but returns nothing.
