# Data Cleaner Module

Data cleaning utilities for processing and sanitizing data in the data processing pipeline. This module handles HTML content cleaning and DataFrame preprocessing for funding data.

---

## HtmlCleaner

Utility class for cleaning HTML content from text fields.

### Constructor (__init__ method)

The `__init__` method initializes the HTML cleaner with no required parameters.

### Methods

#### clean

Safely cleans HTML content from a string value.

##### Parameters

- `value` (str | None): The string value to clean. Can be None or contain HTML tags.

##### Returns

- `str`: Cleaned text with HTML tags removed, or "N/A" if input is None or empty.

---

## DataCleaner

Main data cleaning class that processes Polars DataFrames for funding data.

### Constructor (__init__ method)

Initializes the DataCleaner with an HTML cleaner instance.

#### Parameters

- `html_cleaner` (HtmlCleaner): Instance of HtmlCleaner for HTML content processing.

### Methods

#### clean_dataframe

Processes and cleans a Polars DataFrame containing funding data.

##### Parameters

- `df` (pl.DataFrame): Input DataFrame containing funding data with a "description" column.

##### Returns

- `pl.DataFrame`: Cleaned DataFrame with extracted descriptions and sanitized text fields.

##### Processing Steps

1. **Description Extraction**: Extracts short and full descriptions from the HTML description field using regex patterns:
   - Short description: Content between `<h3>Kurztext</h3>` and `<h3>Volltext</h3>`
   - Full description: Content after `<h3>Volltext</h3>`

2. **Null Value Handling**: Replaces empty strings with None values and fills nulls with "N/A"

3. **HTML Cleaning**: Applies HTML cleaning to all string columns using the configured HtmlCleaner

4. **Column Processing**: Iterates through all string columns and applies cleaning transformations
