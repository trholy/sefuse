import requests
from pathlib import Path


class FileDownloader:
    """Downloads a remote file via HTTP GET and writes it to disk."""

    def download(self, url: str, target_path: Path) -> None:
        """Fetch a URL and save the response body to `target_path`.

        Args:
            url (str): HTTP/HTTPS URL to download.
            target_path (Path): Local path where the downloaded content is written.
                Parent directories are created automatically.

        Raises:
            requests.HTTPError: If the server returns a non-2xx status code.
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        target_path.write_bytes(response.content)
