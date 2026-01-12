# Data Processing Pipeline Module

Main execution module for the data processing pipeline. This module orchestrates the complete workflow from downloading raw data to producing cleaned, enriched datasets ready for semantic search.

## data_processing_pipeline

Main function that executes the complete data processing pipeline in sequential steps.

### Processing Workflow

The pipeline executes the following sequential steps:

1. **Configuration Setup**: Initializes data configuration with default paths and URLs
2. **Data Acquisition**: Downloads raw data from remote source and extracts from ZIP archive
3. **Data Cleaning**: Processes and sanitizes the raw data
4. **Filter Option Extraction**: Generates lookup files for Streamlit filters
5. **UUID Generation**: Adds unique identifiers to data records
6. **Data Persistence**: Saves processed data to parquet files

### Detailed Processing Steps

#### 1. Configuration Initialization
- Creates `DataConfig` instance with default paths
- Sets up all necessary file paths for the pipeline

#### 2. Data Download and Extraction
- **Download**: Uses `FileDownloader` to fetch compressed data from `zip_url`
- **Extract**: Uses `ZipExtractor` to extract `data.parquet` from the archive
- **Validate**: Ensures both download and extraction succeed

#### 3. Data Cleaning
- **Load**: Reads raw parquet data into Polars DataFrame
- **Process**: Applies `DataCleaner` with `HtmlCleaner` to:
  - Extract structured descriptions (short and full text)
  - Remove HTML tags from text fields
  - Handle null/empty values consistently
- **Save**: Writes cleaned data to `cleaned_parquet` file

#### 4. Filter Option Generation
- **Extract**: Uses `UniqueValueExtractor` to gather unique values from key columns
- **Export**: Saves unique values to text files for Streamlit filter options
- **Columns Processed**: 
  - `funding_type`
  - `funding_area`
  - `funding_location`
  - `eligible_applicants`

#### 5. UUID Generation
- **Initialize**: Creates `UuidGenerator` with fixed namespace UUID
- **Add UUIDs**: Generates and adds unique identifiers to data records
- **Preserve**: Maintains original data structure while adding UUID column

#### 6. Final Data Storage
- **Save**: Writes final dataset with UUIDs to `uuid_parquet` file
