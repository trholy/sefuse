import zipfile
from pathlib import Path


class ZipExtractor:
    def extract_file(
        self,
        zip_path: Path,
        filename: str,
        target_path: Path,
    ) -> None:
        if not zip_path.exists():
            raise FileNotFoundError(f"Zip file not found: {zip_path}")

        with zipfile.ZipFile(zip_path, "r") as archive:
            available_files = archive.namelist()

            if filename not in available_files:
                raise ValueError(
                    f"Required file '{filename}' not found in archive. "
                    f"Available files: {available_files}"
                )

            with archive.open(filename) as source:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(source.read())
