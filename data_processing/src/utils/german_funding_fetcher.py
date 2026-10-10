"""HTTP file downloader for the German federal funding dataset."""

import os
from pathlib import Path

import requests


class FileDownloader:
    """Downloads a remote file via HTTP GET and writes it to disk."""

    def download(self, url: str, target_path: Path) -> None:
        """Fetch a URL and save the response body to `target_path`.

        Written to a sibling ``.part`` file and moved into place only once the stream
        has completed. Streaming straight onto the target would leave a truncated but
        still parseable CSV behind when a connection drops mid-transfer, and the
        caller's "download failed, continuing with the existing file" fallback would
        then parse those remains as if they were the full dataset.

        Args:
            url (str): HTTP/HTTPS URL to download.
            target_path (Path): Local path where the downloaded content is written.
                Parent directories are created automatically.

        Raises:
            requests.HTTPError: If the server returns a non-2xx status code.
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)
        part_path = target_path.with_name(f"{target_path.name}.part")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/csv,*/*",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }
        try:
            # Stream to disk so a large export is not buffered entirely in memory.
            with requests.get(url, headers=headers, timeout=120, stream=True) as response:
                response.raise_for_status()
                with open(part_path, "wb") as out_file:
                    for chunk in response.iter_content(chunk_size=1 << 16):
                        if chunk:
                            out_file.write(chunk)
            os.replace(part_path, target_path)
        except BaseException:
            part_path.unlink(missing_ok=True)
            raise
