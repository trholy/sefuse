import hashlib
from datetime import date, datetime

import polars as pl

from .cleaner import HtmlCleaner


EU_STATUS_FORTHCOMING = "31094501"
EU_STATUS_OPEN = "31094502"
EU_STATUS_CLOSED = "31094503"
EU_ALLOWED_STATUS_CODES = {EU_STATUS_FORTHCOMING, EU_STATUS_OPEN, EU_STATUS_CLOSED}

UUID_SOURCE_COLUMN = "uuid_source_call_id"
MIN_DESCRIPTION_LENGTH = 25

EU_COMMON_SCHEMA = {
    "id_hash": pl.Utf8,
    "id_url": pl.Utf8,
    "url": pl.Utf8,
    "title": pl.Utf8,
    "description": pl.Utf8,
    "more_info": pl.Utf8,
    "legal_basis": pl.Utf8,
    "contact_info_institution": pl.Utf8,
    "contact_info_street": pl.Utf8,
    "contact_info_city": pl.Utf8,
    "contact_info_fax": pl.Utf8,
    "contact_info_phone": pl.Utf8,
    "contact_info_email": pl.Utf8,
    "contact_info_website": pl.Utf8,
    "funding_type": pl.List(pl.Utf8),
    "funding_area": pl.List(pl.Utf8),
    "funding_location": pl.List(pl.Utf8),
    "eligible_applicants": pl.List(pl.Utf8),
    "funding_body": pl.Utf8,
    "further_links": pl.List(pl.Utf8),
    "checksum": pl.Utf8,
    "license_info": pl.Utf8,
    "previous_update_dates": pl.List(pl.Datetime("us")),
    "last_updated": pl.Datetime("us"),
    "on_website_from": pl.Datetime("us"),
    "deleted": pl.Boolean,
    "project_short_description": pl.Utf8,
    "project_full_description": pl.Utf8,
    UUID_SOURCE_COLUMN: pl.Utf8,
}


class EuFundingProcessor:
    def __init__(self, html_cleaner: HtmlCleaner):
        self._html_cleaner = html_cleaner

    @staticmethod
    def _normalize_string(value: object) -> str | None:
        if value is None:
            return None

        as_text = str(value).strip()
        return as_text or None

    @staticmethod
    def _parse_status(status_code: str) -> bool:
        EU_ACTIVE_STATUS_CODES = {EU_STATUS_FORTHCOMING, EU_STATUS_OPEN}
        return status_code not in EU_ACTIVE_STATUS_CODES

    @staticmethod
    def _normalize_list(value: object) -> list[str]:
        if value is None:
            return []

        if isinstance(value, (list, tuple, set)):
            return [
                str(entry).strip()
                for entry in value
                if entry is not None and str(entry).strip()
            ]

        as_text = str(value).strip()
        return [as_text] if as_text else []

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        raw = EuFundingProcessor._normalize_string(value)
        if raw is None:
            return None

        normalized = raw.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    @staticmethod
    def _build_funding_area(
        keywords: list[str],
        identifier: str | None,
        call_id: str | None,
    ) -> list[str]:
        blocked = {
            value
            for value in (identifier, call_id)
            if value is not None
        }

        filtered_keywords: list[str] = []
        seen: set[str] = set()
        for keyword in keywords:
            if keyword in blocked:
                continue
            if keyword in seen:
                continue
            seen.add(keyword)
            filtered_keywords.append(keyword)

        return filtered_keywords

    @staticmethod
    def _compute_id_hash(uuid_source: str) -> str:
        return hashlib.md5(uuid_source.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_allowed_status(status_code: str | None) -> bool:
        return status_code in EU_ALLOWED_STATUS_CODES

    def _should_keep_item(
        self,
        title: str,
        summary: str,
        cleaned_description_html: str,
        keywords: list[str],
        deadline: datetime | None,
        status_code: str | None,
    ) -> bool:
        if not self._is_allowed_status(status_code):
            return False
        if len(cleaned_description_html.strip()) < MIN_DESCRIPTION_LENGTH:
            return False
        if not keywords:
            return False

        return True

    def transform(self, eu_calls: list[dict]) -> pl.DataFrame:
        if not eu_calls:
            return pl.DataFrame(
                schema=[(column, dtype) for column, dtype in EU_COMMON_SCHEMA.items()]
            )

        rows = []
        for item in eu_calls:
            identifier = self._normalize_string(item.get("id"))
            call_id = self._normalize_string(item.get("call_id"))
            title = self._normalize_string(item.get("title")) or "N/A"
            summary = self._html_cleaner.clean(item.get("summary"))
            description_from_html = self._html_cleaner.clean(
                item.get("description_html")
            )

            if summary == "N/A" and description_from_html != "N/A":
                summary = description_from_html

            deadline = self._parse_datetime(item.get("deadline"))
            status_code = self._normalize_string(item.get("status_code"))
            keywords = self._normalize_list(item.get("keywords"))
            funding_area = self._build_funding_area(
                keywords=keywords,
                identifier=identifier,
                call_id=call_id,
            )

            if not self._should_keep_item(
                title=title,
                summary=summary,
                cleaned_description_html=description_from_html,
                keywords=funding_area,
                deadline=deadline,
                status_code=status_code,
            ):
                continue

            url = self._normalize_string(item.get("url"))

            uuid_source = call_id or identifier or url or title

            if description_from_html != "N/A" and summary != description_from_html:
                combined_description = f"{summary}\n\n{description_from_html}"
            elif description_from_html != "N/A":
                combined_description = description_from_html
            else:
                combined_description = summary

            rows.append(
                {
                    "id_hash": self._compute_id_hash(uuid_source),
                    "id_url": identifier,
                    "url": url,
                    "title": title,
                    "description": combined_description,
                    "more_info": call_id,
                    "legal_basis": None,
                    "contact_info_institution": None,
                    "contact_info_street": None,
                    "contact_info_city": None,
                    "contact_info_fax": None,
                    "contact_info_phone": None,
                    "contact_info_email": None,
                    "contact_info_website": None,
                    "funding_type": ["Zuschuss"],
                    "funding_area": funding_area,
                    "funding_location": ["EU"],
                    "eligible_applicants": [],
                    "funding_body": self._normalize_string(item.get("programme")),
                    "further_links": [],
                    "checksum": None,
                    "license_info": None,
                    "previous_update_dates": [],
                    "date_2": deadline,
                    "date_1": self._parse_datetime(item.get("start_date")),
                    "deleted": self._parse_status(status_code),
                    "project_short_description": summary,
                    "project_full_description": description_from_html,
                    UUID_SOURCE_COLUMN: uuid_source,
                }
            )

        if not rows:
            return pl.DataFrame(
                schema=[(column, dtype) for column, dtype in EU_COMMON_SCHEMA.items()]
            )

        df = pl.DataFrame(rows)

        for column, dtype in EU_COMMON_SCHEMA.items():
            if column not in df.columns:
                df = df.with_columns(pl.lit(None).cast(dtype).alias(column))

        return df.select(list(EU_COMMON_SCHEMA.keys())).with_columns(
            [pl.col(column).cast(dtype) for column, dtype in EU_COMMON_SCHEMA.items()]
        )
