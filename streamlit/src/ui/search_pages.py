import os
from abc import ABC, abstractmethod
from typing import Any

import streamlit as st

from utils import (
    aggregate_chunks,
    apply_filters,
    read_extracted_filter_options,
    render_eu_project_result,
    render_project_result,
    search_projects,
)


class BaseFundingSearchPage(ABC):
    def __init__(
        self,
        model: str | None = None,
        fastapi_url: str | None = None,
    ):
        self.model = model or os.getenv("MODEL", "nomic-embed-text")
        self.fastapi_url = fastapi_url or os.getenv(
            "FASTAPI_URL",
            "http://fastapi:8000",
        )

    @property
    @abstractmethod
    def page_title(self) -> str:
        pass

    @property
    @abstractmethod
    def search_endpoint(self) -> str:
        pass

    @property
    @abstractmethod
    def search_button_key(self) -> str:
        pass

    @property
    @abstractmethod
    def query_key(self) -> str:
        pass

    @property
    def search_limit_key(self) -> str:
        return f"{self.search_button_key}_limit"

    @property
    def no_results_message(self) -> str:
        return "No projects found."

    @abstractmethod
    def render_sidebar(self) -> tuple[int, dict[str, Any]]:
        pass

    @abstractmethod
    def render_result(self, result: dict[str, Any]) -> None:
        pass

    def process_results(
        self,
        results: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return results

    def render(self) -> None:
        st.title(self.page_title)

        query = st.text_area(
            "Enter your project description:",
            height=100,
            max_chars=5000,
            placeholder="Start typing...",
            key=self.query_key,
        )
        search_limit, context = self.render_sidebar()

        if st.button("Search", key=self.search_button_key) and query:
            try:
                matches = search_projects(
                    fastapi_url=self.fastapi_url,
                    model=self.model,
                    query=query,
                    search_limit=search_limit,
                    endpoint=self.search_endpoint,
                )
                results = aggregate_chunks(matches)
                results = self.process_results(results, context)

                if results:
                    st.success(f"Found {len(results)} matching projects")
                    for result in results:
                        self.render_result(result)
                else:
                    st.warning(self.no_results_message)
            except Exception as error:
                st.error(f"Error: {error}")


class GermanFundingSearchPage(BaseFundingSearchPage):
    @property
    def page_title(self) -> str:
        return "Federal Funding Database"

    @property
    def search_endpoint(self) -> str:
        return "/v1/search/german"

    @property
    def search_button_key(self) -> str:
        return "search_federal"

    @property
    def query_key(self) -> str:
        return "federal_query"

    @property
    def no_results_message(self) -> str:
        return "No projects match your selected filters."

    def render_sidebar(self) -> tuple[int, dict[str, Any]]:
        location_options = read_extracted_filter_options("data/german_funding_location.txt")
        funding_type_options = read_extracted_filter_options("data/german_funding_type.txt")
        eligible_options = read_extracted_filter_options("data/german_eligible_applicants.txt")
        funding_area_options = read_extracted_filter_options("data/german_funding_area.txt")

        st.sidebar.header("Filter Options")
        selected_locations = st.sidebar.multiselect(
            "Funding location",
            location_options,
            key="federal_locations",
        )
        selected_funding_type = st.sidebar.multiselect(
            "Type of funding",
            funding_type_options,
            key="federal_funding_type",
        )
        selected_eligible = st.sidebar.multiselect(
            "Eligible applicants",
            eligible_options,
            key="federal_eligible",
        )
        selected_funding_area = st.sidebar.multiselect(
            "Funding area",
            funding_area_options,
            key="federal_funding_area",
        )
        search_limit = st.sidebar.number_input(
            "Search limit",
            min_value=5,
            max_value=50,
            value=20,
            step=5,
            key=self.search_limit_key,
        )
        drop_na = st.sidebar.checkbox("Drop N/A", value=True, key="federal_drop_na")

        filters = {
            "locations": selected_locations,
            "funding_type": selected_funding_type,
            "eligible": selected_eligible,
            "funding_area": selected_funding_area,
            "drop_na": drop_na,
        }
        return int(search_limit), {"filters": filters}

    def process_results(
        self,
        results: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return apply_filters(results, context["filters"])

    def render_result(self, result: dict[str, Any]) -> None:
        render_project_result(result)


class EuFundingSearchPage(BaseFundingSearchPage):
    @property
    def page_title(self) -> str:
        return "EU Funding Programs"

    @property
    def search_endpoint(self) -> str:
        return "/v1/search/eu"

    @property
    def search_button_key(self) -> str:
        return "search_eu"

    @property
    def query_key(self) -> str:
        return "eu_query"

    def render_sidebar(self) -> tuple[int, dict[str, Any]]:
        search_limit = st.sidebar.number_input(
            "Search limit",
            min_value=5,
            max_value=50,
            value=20,
            step=5,
            key=self.search_limit_key,
        )
        return int(search_limit), {}

    def render_result(self, result: dict[str, Any]) -> None:
        render_eu_project_result(result)
