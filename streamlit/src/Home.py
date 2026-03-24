import streamlit as st

st.set_page_config(
    page_title="SeFuSe",
    layout="centered",
    page_icon="favicon.jpg",
)

st.title("Semantic Funding Search (SeFuSe)")
st.set_page_config(page_title="SeFuSe", layout="centered", page_icon="favicon.jpg")

description = (
    "Use **SeFuSE** to semantically search two funding sources:\n"
    "- **[Federal Funding Database:](https://www.foerderdatenbank.de/FDB/DE/Foerderprogramme/foerderprogramme.html)** Search German federal funding programs with optional filters (funding location, funding type, eligible applicants, funding area).\n"
    "- **[EU Funding Programs:](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home)** Search EU calls, with EU-specific fields such as description, deadline date, and publication date.\n\n"
    "On both pages, enter your project idea in natural language to get the most relevant funding calls ranked by similarity.\n"
)
st.write(description)

st.space(size="medium")
info = (
    "Source code available on [GitHub](https://github.com/trholy/sefuse)."
    " Read the [Docs](https://to82lod.gitpages.uni-jena.de/sefuse/)."
    " Licensed under [MIT](https://github.com/trholy/sefuse/blob/main/LICENSE)."
    " Developed by [Thomas R. Holy](https://thomas-robert-holy.de/)."
)
st.write(info)
