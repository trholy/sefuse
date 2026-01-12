from dataclasses import dataclass
from pathlib import Path
import os


DOWNLOAD_FILE = os.getenv('DOWNLOAD_FILE')

@dataclass(frozen=True)
class DataConfig:
    data_dir: Path = Path("data")
    zip_url: str = DOWNLOAD_FILE

    zip_path: Path = data_dir / "parquet_data.zip"
    raw_parquet: Path = data_dir / "parquet_data.parquet"
    cleaned_parquet: Path = data_dir / "parquet_data_cleaned.parquet"
    uuid_parquet: Path = data_dir / "parquet_data_uuid.parquet"
