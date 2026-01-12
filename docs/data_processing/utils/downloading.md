# File Downloader Module

Utility class for downloading files from URLs and saving them to local storage. This module handles the initial data acquisition phase of the data processing pipeline.

## FileDownloader

Class for downloading files from HTTP URLs and saving them to specified local paths.

### Methods

#### download

Downloads a file from a given URL and saves it to the specified local path.

##### Parameters

- `url` (str): The URL from which to download the file.
- `target_path` (Path): The local file path where the downloaded content should be saved.

##### Returns

- `None`: This method performs file I/O operations but returns nothing.
