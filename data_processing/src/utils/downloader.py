import requests
from pathlib import Path


class FileDownloader:
    def download(self, url: str, target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        target_path.write_bytes(response.content)
