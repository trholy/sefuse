# Unique Value Extractor Module

Utility class for extracting unique values from Polars DataFrames and saving them to files. This module is used to gather filter options from the funding data for the Streamlit application.

---

## UniqueValueExtractor

Class for extracting normalized, deduplicated unique values from DataFrame columns and saving them to text files.

### Methods

#### extract

Extracts unique, normalized values from a specified column in a Polars DataFrame while removing semantic duplicates and handling invalid entries.

##### Parameters

- `df` (pl.DataFrame): Input DataFrame containing the data to process.
- `column` (str): Name of the column from which to extract unique values.

##### Returns

- `list[str]`: List of cleaned, deduplicated string values from the specified column.

##### Processing Logic

1. **List Column Handling**: If the column contains list data types, it first explodes the column to flatten nested structures, then processes the values.
2. **Regular Column Handling**: For regular columns, it directly processes the values.
3. **Null Handling**: Drops null values before further processing.
4. **Normalization**:
   - Converts values to lowercase
   - Replaces German umlauts (`ä → ae`, `ö → oe`, `ü → ue`, `ß → ss`)
   - Removes accents and diacritics
   - Normalizes separators (spaces, hyphens, etc.) to underscores
   - Removes non-alphanumeric characters
   
5. **Deduplication**:
   - Uses normalized values as keys to identify semantic duplicates
   - Ensures values like `Berlin` and `berlin`, or `Öffentliche Einrichtung` and `oeffentliche_einrichtung`, are treated as the same

6. **Best Value Selection**:
   -Retains the most human-readable version using a scoring system:
     - Prefers values with uppercase letters
     - Prefers values with spaces over snake_case
     - Penalizes machine-like formats (e.g., lowercase or underscore-heavy values)
   
7.**Fallback Handling**:
   - Invalid or unprocessable values (e.g., `None`, `nan`, very short or empty values) are grouped into a fallback category (`"Unknown"`)
   - The fallback category is added if such values are encountered

8.**Final Output**:
   - Returns a sorted list of unique, cleaned values

---

#### save

Saves a list of unique values to a text file, one value per line.

##### Parameters

- `values` (list[str]): List of string values to save.
- `target_path` (Path): Path object specifying where to save the file.

##### Returns

- `None`: This method performs file I/O operations but returns nothing.
