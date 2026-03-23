import json
import logging
import time
from pathlib import Path

import requests


EU_STATUS_FORTHCOMING = "31094501"
EU_STATUS_OPEN = "31094502"
EU_STATUS_CLOSED = "31094503"
EU_ALLOWED_STATUS_CODES = {EU_STATUS_FORTHCOMING, EU_STATUS_OPEN}

logger = logging.getLogger(__name__)


class EuFundingFetcher:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout_seconds: float = 30,
        page_delay_seconds: float = 0.2,
    ):
        self._api_url = api_url
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._page_delay_seconds = page_delay_seconds

    @staticmethod
    def _get_meta_value(meta: dict, key: str) -> str | None:
        value = meta.get(key)
        return EuFundingFetcher._first_string(value)

    @staticmethod
    def _first_string(value: object) -> str | None:
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
        if not identifier:
            return None

        return (
            "https://ec.europa.eu/info/funding-tenders/opportunities/portal/"
            f"screen/opportunities/topic-details/{identifier}"
        )

    @staticmethod
    def _is_english(result_language: str | None, metadata_languages: list[str]) -> bool:
        if result_language and result_language.lower().startswith("en"):
            return True

        return any(language.lower().startswith("en") for language in metadata_languages)

    @staticmethod
    def _is_allowed_status(status_code: str | None) -> bool:
        return status_code in EU_ALLOWED_STATUS_CODES

    def _fetch_page(self, page_number: int, page_size: int) -> list[dict]:
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
        max_pages: int = 100,
    ) -> list[dict]:
        results: list[dict] = []
        page = 1

        while page <= max_pages:
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
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def save(calls: list[dict], target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            json.dumps(calls, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
