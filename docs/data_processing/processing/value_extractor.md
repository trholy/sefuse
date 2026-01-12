# Unique Value Extractor Module

Utility class for extracting unique values from Polars DataFrames and saving them to files. This module is used to gather filter options from the funding data for the Streamlit application.

---

## UniqueValueExtractor

Class for extracting unique values from DataFrame columns and saving them to text files.

### Methods

#### extract

Extracts unique values from a specified column in a Polars DataFrame.

##### Parameters

- `df` (pl.DataFrame): Input DataFrame containing the data to process.
- `column` (str): Name of the column from which to extract unique values.

##### Returns

- `list[str]`: List of unique string values from the specified column.

##### Processing Logic

1. **List Column Handling**: If the column contains list data types, it first explodes the column to flatten nested structures, then extracts unique values.
2. **Regular Column Handling**: For regular columns, it directly extracts unique values.
3. **Type Conversion**: Converts all values to strings and returns them as a list.

#### save

Saves a list of unique values to a text file, one value per line.

##### Parameters

- `values` (list[str]): List of string values to save.
- `target_path` (Path): Path object specifying where to save the file.

##### Returns

- `None`: This method performs file I/O operations but returns nothing.
