import os
import logging
from abc import ABC, abstractmethod
from typing import Any

import streamlit as st

from utils import (
    aggregate_chunks,
    apply_filters,
    fetch_german_taxonomy,
    render_eu_project_result,
    render_german_project_result,
    search_projects,
    _friendly_search_error,
)

logger = logging.getLogger(__name__)


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
        st.set_page_config(
            page_title=f"SeFuSe - {self.page_title}",
            layout="centered",
            page_icon="favicon.jpg",
        )

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
                    filters=context.get("filters"),
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
                logger.exception("Search request failed: %s", error)
                st.error(_friendly_search_error(error))


class GermanFundingSearchPage(BaseFundingSearchPage):
    FIELD_CONFIG = [
        ("funding_location", "Funding location", "federal_locations"),
        ("funding_type", "Type of funding", "federal_funding_type"),
        ("eligible_applicants", "Eligible applicants", "federal_eligible"),
        ("funding_area", "Funding area", "federal_funding_area"),
    ]

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
        options_by_field: dict[str, list[str]] = {}
        labels_by_field: dict[str, dict[str, str]] = {}
        taxonomy_columns: dict[str, Any] = {}
        taxonomy_error: Exception | None = None

        try:
            taxonomy = fetch_german_taxonomy(self.fastapi_url)
            raw_columns = taxonomy.get("columns", {})
            if isinstance(raw_columns, dict):
                taxonomy_columns = raw_columns
        except Exception as error:
            taxonomy_error = error
            taxonomy_columns = {}

        for field, _, _ in self.FIELD_CONFIG:
            entries = taxonomy_columns.get(field, []) if isinstance(taxonomy_columns, dict) else []
            options_by_field[field] = [entry.get("key", "") for entry in entries if entry.get("key")]
            labels_by_field[field] = {
                entry.get("key", ""): entry.get("canonical", entry.get("key", ""))
                for entry in entries
                if entry.get("key")
            }

        st.sidebar.header("Filter Options")
        selected_filters: dict[str, list[str]] = {}
        for field, label, widget_key in self.FIELD_CONFIG:
            selected_filters[field] = st.sidebar.multiselect(
                label,
                options_by_field.get(field, []),
                format_func=lambda key, f=field: labels_by_field.get(f, {}).get(key, key),
                key=widget_key,
            )

        if taxonomy_error is not None:
            logger.warning("Failed to fetch German taxonomy: %s", taxonomy_error)
            st.sidebar.warning("Filters are unavailable (taxonomy could not be loaded).")

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
            **selected_filters,
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
        render_german_project_result(result)


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
