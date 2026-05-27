"""Paginates the EU SEDIA search API to collect open/forthcoming English-language calls."""

import json
import logging
import time
from pathlib import Path

import requests

from data_processing.config import (
    EU_STATUS_FORTHCOMING,
    EU_STATUS_OPEN,
    EU_ACTIVE_STATUS_CODES,
)

logger = logging.getLogger(__name__)


class EuFundingFetcher:
    """Paginates the EU SEDIA search API and collects open/forthcoming English-language calls.

    Only OPEN and FORTHCOMING calls are requested; CLOSED calls are excluded at the query
    level to avoid unbounded pagination. Non-English results are dropped client-side.

    Args:
        api_url (str): Base URL of the SEDIA search endpoint.
        api_key (str): API key passed as the `apiKey` query parameter.
        timeout_seconds (float, default=30): HTTP request timeout in seconds.
        page_delay_seconds (float, default=0.2): Sleep between paginated requests
            to avoid rate-limiting.

    Example:
        fetcher = EuFundingFetcher(api_url="https://...", api_key="SEDIA")
        calls = fetcher.fetch_open_and_forthcoming_calls(page_size=50)
        EuFundingFetcher.save(calls, Path("data/eu_open_calls.json"))
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout_seconds: float = 30,
        page_delay_seconds: float = 0.2,
    ):
        """Initialise an EuFundingFetcher for the given endpoint and credentials.

        Args:
            api_url (str): Base URL of the SEDIA search endpoint.
            api_key (str): API key passed as the ``apiKey`` query parameter.
            timeout_seconds (float, optional): HTTP request timeout in seconds.
                Defaults to 30.
            page_delay_seconds (float, optional): Sleep between paginated requests
                to avoid rate-limiting. Defaults to 0.2.
        """
        self._api_url = api_url
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._page_delay_seconds = page_delay_seconds

    @staticmethod
    def _get_meta_value(meta: dict, key: str) -> str | None:
        """Extract and normalise a single string value from a metadata dict by `key`."""
        value = meta.get(key)
        return EuFundingFetcher._first_string(value)

    @staticmethod
    def _first_string(value: object) -> str | None:
        """Recursively extract the first non-empty string from a scalar, dict, or list."""
        if value is None:
            return None

        if isinstance(value, (str, int, float)):
            normalized = str(value).strip()
            return normalized or None

        if isinstance(value, dict):
            for key in ("code", "id", "value", "label", "text", "name", "content"):
                nested = EuFundingFetcher._first_string(value.get(key))
                if nested is not None:
                    return nested
            return None

        if isinstance(value, list):
            for item in value:
                nested = EuFundingFetcher._first_string(item)
                if nested is not None:
                    return nested

        return None

    @staticmethod
    def _normalize_meta_list(meta: dict, key: str) -> list[str]:
        """Return all non-empty string entries for `key` from a metadata dict."""
        value = meta.get(key)
        if value is None:
            return []

        values = value if isinstance(value, list) else [value]
        normalized_values: list[str] = []
        for entry in values:
            normalized = EuFundingFetcher._first_string(entry)
            if normalized is not None:
                normalized_values.append(normalized)
        return normalized_values

    @staticmethod
    def _build_portal_topic_url(identifier: str | None) -> str | None:
        """Construct the EU Funding & Tenders portal URL for a topic `identifier`."""
        if not identifier:
            return None

        return (
            "https://ec.europa.eu/info/funding-tenders/opportunities/portal/"
            f"screen/opportunities/topic-details/{identifier}"
        )

    @staticmethod
    def _is_english(result_language: str | None, metadata_languages: list[str]) -> bool:
        """Return ``True`` when the result or its metadata indicates an English-language call."""
        if result_language and result_language.lower().startswith("en"):
            return True

        return any(language.lower().startswith("en") for language in metadata_languages)

    @staticmethod
    def _is_allowed_status(status_code: str | None) -> bool:
        """Return ``True`` when `status_code` is OPEN or FORTHCOMING."""
        return status_code in EU_ACTIVE_STATUS_CODES

    def _fetch_page(self, page_number: int, page_size: int) -> list[dict]:
        """Request one page of OPEN/FORTHCOMING calls from the SEDIA search endpoint.

        Args:
            page_number (int): 1-based page index to request.
            page_size (int): Number of results per page.

        Returns:
            list[dict]: Raw result dicts from the `results` key of the API response.

        Raises:
            requests.HTTPError: If the server returns a non-2xx status code.
        """
        params = {
            "apiKey": self._api_key,
            "pageNumber": page_number,
            "pageSize": page_size,
            "text": "***",
        }

        # The search endpoint expects multipart form-data values for
        # `query`, `languages`, and `sort`.
        query = {
            "bool": {
                "must": [
                    {"terms": {"type": ["1", "2"]}},
                    {
                        "terms": {
                            "status": [
                                EU_STATUS_FORTHCOMING,
                                EU_STATUS_OPEN,
                            ]
                        }
                    },
                ]
            }
        }
        languages = ["en"]
        sort = {"field": "sortStatus", "order": "ASC"}

        response = requests.post(
            self._api_url,
            params=params,
            files={
                "query": ("blob", json.dumps(query), "application/json"),
                "languages": ("blob", json.dumps(languages), "application/json"),
                "sort": ("blob", json.dumps(sort), "application/json"),
            },
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()

        data = response.json()
        return data.get("results", [])

    def fetch_open_and_forthcoming_calls(
        self,
        page_size: int = 50,
        max_pages: int | None = None,
    ) -> list[dict]:
        """Fetch all open and forthcoming English EU calls by paginating the API.

        Stops when a page returns no results or `max_pages` is reached.

        Args:
            page_size (int, default=50): Number of results to request per API page.
            max_pages (int | None, default=None): Maximum number of pages to fetch.
                ``None`` means no limit. Use this as a safety guard against
                runaway pagination if the API changes behaviour.

        Returns:
            list[dict]: Normalised call records filtered to OPEN/FORTHCOMING + English.
        """
        results: list[dict] = []
        page = 1

        while True:
            if max_pages is not None and page > max_pages:
                logger.warning(
                    "EU fetch: reached max_pages=%s, stopping pagination.", max_pages
                )
                break
            items = self._fetch_page(page, page_size)
            if not items:
                break

            kept_for_page = 0
            dropped_status = 0
            dropped_language = 0

            for item in items:
                meta = item.get("metadata", {})
                identifier = self._get_meta_value(meta, "identifier")
                status_code = self._get_meta_value(meta, "status")
                result_language = self._first_string(item.get("language"))
                metadata_languages = self._normalize_meta_list(meta, "language")

                if not self._is_allowed_status(status_code):
                    dropped_status += 1
                    continue
                if not self._is_english(result_language, metadata_languages):
                    dropped_language += 1
                    continue

                call = {
                    "id": identifier,
                    "title": self._get_meta_value(meta, "title"),
                    "call_id": self._get_meta_value(meta, "callIdentifier"),
                    "programme": self._get_meta_value(meta, "programmePeriod"),
                    "status_code": status_code,
                    "start_date": self._get_meta_value(meta, "startDate"),
                    "deadline": self._get_meta_value(meta, "deadlineDate"),
                    "url": self._build_portal_topic_url(identifier),
                    "summary": item.get("summary"),
                    "description_html": self._get_meta_value(meta, "descriptionByte"),
                    "keywords": self._normalize_meta_list(meta, "keywords"),
                    "language": result_language,
                    "metadata_languages": metadata_languages,
                }
                results.append(call)
                kept_for_page += 1

            logger.info(
                "EU fetch page %s: raw=%s kept=%s dropped_status=%s dropped_language=%s",
                page,
                len(items),
                kept_for_page,
                dropped_status,
                dropped_language,
            )

            page += 1
            time.sleep(self._page_delay_seconds)

        return results

    @staticmethod
    def load(path: Path) -> list[dict]:
        """Load previously saved calls from a JSON file (cache fallback).

        Args:
            path (Path): Path to the JSON file written by `save`.

        Returns:
            list[dict]: Deserialized call records.
        """
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def save(calls: list[dict], target_path: Path) -> None:
        """Persist call records as a pretty-printed JSON file.

        Args:
            calls (list[dict]): Records to serialise.
            target_path (Path): Destination file path; parent directories are created
                automatically.
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            json.dumps(calls, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
