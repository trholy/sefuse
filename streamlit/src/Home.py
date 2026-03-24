import streamlit as st

st.set_page_config(
    page_title="SeFuSe",
    layout="centered",
    page_icon="favicon.jpg",
)

st.title("Semantic Funding Search (SeFuSe)")
st.set_page_config(page_title="SeFuSe", layout="centered", page_icon="favicon.jpg")

description_text = (
    "Use **SeFuSE** to semantically search two funding sources:\n"
    "- **[Federal Funding Database:](https://www.foerderdatenbank.de/FDB/DE/Foerderprogramme/foerderprogramme.html)** Search German federal funding programs with optional filters (funding location, funding type, eligible applicants, funding area).\n"
    "- **[EU Funding Programs:](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home)** Search EU calls, with EU-specific fields such as description, deadline date, and publication date.\n\n"
    "On both pages, enter your project idea in natural language to get the most relevant funding calls ranked by similarity."
)
st.write(description_text)

st.space(size="small")
info_text = (
    "**Development Background:** This tool was developed in response to an urgent need and, following the positive feedback it received, is now being advanced at the Center for Applied Artificial Intelligence (ZAKI) at Ernst Abbe University of Applied Sciences Jena. The aim of this initiative is to simplify and streamline the search for suitable funding programs for interested users, such as staff in transfer centers and researchers.\n\n"
    "**Data Processing:** When the tool is operated on local infrastructure, no data is stored long-term. No data leaves the local system, and there is no access to external APIs or any other form of external data transfer.\n\n "
)
st.write(info_text)

st.space(size="large")
about_text = (
    "Source code available on [GitHub](https://github.com/trholy/sefuse)."
    " Read the [Docs](https://to82lod.gitpages.uni-jena.de/sefuse/)."
    " Licensed under [MIT](https://github.com/trholy/sefuse/blob/main/LICENSE)."
    " Developed by [Thomas R. Holy](https://thomas-robert-holy.de/)."
)
st.write(about_text)
