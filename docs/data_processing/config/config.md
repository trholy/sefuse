# Data Configuration Module

Configuration class for managing data paths and URLs used throughout the data processing pipeline.

## DataConfig

Data configuration class that defines all necessary file paths and URLs for the data processing workflow.

### Constructor Parameters

- `data_dir` (Path, optional): Base directory for all data files. Default is `"data"`.
- `zip_url` (str, optional): URL for downloading the compressed parquet data.
- `zip_path` (Path, optional): Path to the downloaded zip file.
- `raw_parquet` (Path, optional): Path to the raw parquet file after extraction.
- `cleaned_parquet` (Path, optional): Path to the cleaned parquet file. 
- `uuid_parquet` (Path, optional): Path to the parquet file with UUIDs added.

### Default Values

- `data_dir`: `"data"`
- `zip_url`: `"https://foerderdatenbankdump.fra1.cdn.digitaloceanspaces.com/data/parquet_data.zip"`
- `zip_path`: `"data/parquet_data.zip"`
- `raw_parquet`: `"data/parquet_data.parquet"`
- `cleaned_parquet`: `"data/parquet_data_cleaned.parquet"`
- `uuid_parquet`: `"data/parquet_data_uuid.parquet"`
