# Streamlit App

The application provides a user-friendly interface for searching funding opportunities by entering project descriptions and applying filters. It integrates with a FastAPI backend service to perform semantic searches and displays results with detailed information about each funding opportunity.

---

## Streamlit Components

### Main Content Area

#### Text Input
- **Label**: "Enter your project description:"
- **Height**: 100 pixels
- **Max Characters**: 5000
- **Placeholder**: "Start typing..."

### Sidebar Filters

#### Funding Location
- **Widget**: Multiselect dropdown
- **Options**: Loaded from `data/funding_location.txt`

#### Type of Funding
- **Widget**: Multiselect dropdown
- **Options**: Loaded from `data/funding_type.txt`

#### Eligible Applicants
- **Widget**: Multiselect dropdown
- **Options**: Loaded from `data/eligible_applicants.txt`

#### Funding Area
- **Widget**: Multiselect dropdown
- **Options**: Loaded from `data/funding_area.txt`

#### Search Limit
- **Widget**: Number input
- **Range**: 5-50
- **Default**: 20
- **Step**: 5

#### Drop N/A
- **Widget**: Checkbox
- **Default**: Checked (True)

### Search Button

Triggers the search operation when clicked and query text is provided.
