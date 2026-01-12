# Streamlit Utils Module

This module provides utility functions for the Streamlit application, including data processing, filtering, and aggregation operations. These utilities help in safely handling data structures, reading configuration files, applying filters to search results, and aggregating chunked data.

---

## Functions

### safe_join

Safely joins list-like objects or returns a default value for empty inputs.

#### Parameters

- `value` (Union[List[Any], None]): The value to join. Can be a list, tuple, set, or single value.
- `sep` (str, optional): Separator string used to join elements. Default is `", "`.
- `default` (str, optional): Default value returned when input is empty or None. Default is `"N/A"`.

#### Returns

- `str`: Joined string or default value.

---

### normalize_list

Ensures the input value is converted into a list of strings.

#### Parameters

- `value` (Any): Input value that may be a string, list, tuple, set, or other type.

#### Returns

- `List[str]`: A list containing string representations of the input values, excluding None values.

---

### read_extracted_filter_options

Reads filter options from a text file with retry logic.

#### Parameters

- `file_path` (str): Path to the file containing filter options, one per line.
- `retries` (int, optional): Maximum number of retry attempts. Default is `10`.
- `delay` (float, optional): Initial delay between retries in seconds. Default is `1`.

#### Returns

- `List[str]`: List of stripped non-empty lines from the file.

---

### apply_filters

Filters API results based on selected criteria from the sidebar.

#### Parameters

- `matches` (List[Dict]): List of dictionaries representing search results.
- `filters` (Dict[str, List[str]]): Dictionary mapping filter categories to selected values.

#### Returns

- `List[Dict]`: Filtered list of results matching all active filters.

---

### aggregate_chunks

Aggregates multiple chunk results per project into a single entry.

#### Parameters

- `matches` (List[Dict]): List of dictionaries representing chunked search results.

#### Returns

- `List[Dict]`: Aggregated list where each project appears once with maximum matching score.
