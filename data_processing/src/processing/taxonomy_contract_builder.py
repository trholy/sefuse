from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from shared.taxonomy_contract import (
    TAXONOMY_FALLBACK_KEY,
    TAXONOMY_FALLBACK_VALUE,
    is_invalid_taxonomy_value,
    normalize_taxonomy_key,
    score_taxonomy_display_value,
)


class TaxonomyContractBuilder:
    def _iter_values(self, df: pl.DataFrame, column: str) -> list[str]:
        dtype = df.schema[column]
        if dtype.base_type() == pl.List:
            series = df.explode(column)[column]
        else:
            series = df[column]
        return [str(v).strip() for v in series.drop_nulls().to_list()]

    def _build_column_mapping(
        self,
        df: pl.DataFrame,
        column: str,
    ) -> tuple[dict[str, str], list[dict[str, object]]]:
        values = self._iter_values(df, column)
        key_alias_counter: dict[str, Counter[str]] = defaultdict(Counter)

        for raw_value in values:
            key = normalize_taxonomy_key(raw_value)
            if is_invalid_taxonomy_value(raw_value, key):
                key = TAXONOMY_FALLBACK_KEY
                raw_value = TAXONOMY_FALLBACK_VALUE
            key_alias_counter[key][raw_value] += 1

        key_to_canonical: dict[str, str] = {}
        entries: list[dict[str, object]] = []
        for key, aliases_counter in key_alias_counter.items():
            if key == TAXONOMY_FALLBACK_KEY:
                canonical = TAXONOMY_FALLBACK_VALUE
            else:
                canonical = max(
                    aliases_counter.keys(),
                    key=lambda alias: (
                        score_taxonomy_display_value(alias),
                        aliases_counter[alias],
                        len(alias),
                        alias,
                    ),
                )

            key_to_canonical[key] = canonical
            aliases = sorted(
                aliases_counter.items(),
                key=lambda item: (-item[1], item[0]),
            )
            entries.append({
                "key": key,
                "canonical": canonical,
                "aliases": [alias for alias, _ in aliases],
                "count": int(sum(aliases_counter.values())),
            })

        entries.sort(key=lambda item: item["canonical"])
        return key_to_canonical, entries

    @staticmethod
    def _canonicalize_list_value(
        value: object,
        key_to_canonical: dict[str, str],
    ) -> list[str]:
        if value is None:
            return []

        if isinstance(value, pl.Series):
            raw_values = value.to_list()
        elif isinstance(value, list):
            raw_values = value
        else:
            raw_values = [value]

        canonical_values: list[str] = []
        for raw in raw_values:
            if raw is None:
                continue
            text = str(raw).strip()
            if not text:
                continue
            key = normalize_taxonomy_key(text)
            if is_invalid_taxonomy_value(text, key):
                key = TAXONOMY_FALLBACK_KEY
            canonical = key_to_canonical.get(key, TAXONOMY_FALLBACK_VALUE)
            canonical_values.append(canonical)

        # Keep stable order while removing duplicates.
        return list(dict.fromkeys(canonical_values))

    @staticmethod
    def _keys_for_value(value: object) -> list[str]:
        if value is None:
            return []

        if isinstance(value, pl.Series):
            raw_values = value.to_list()
        elif isinstance(value, list):
            raw_values = value
        else:
            raw_values = [value]

        keys: list[str] = []
        for raw in raw_values:
            if raw is None:
                continue
            text = str(raw).strip()
            if not text:
                continue
            keys.append(normalize_taxonomy_key(text))

        return list(dict.fromkeys(keys))

    def canonicalize_dataframe(
        self,
        df: pl.DataFrame,
        columns: list[str],
    ) -> tuple[pl.DataFrame, dict[str, list[dict[str, object]]]]:
        taxonomy_columns: dict[str, list[dict[str, object]]] = {}

        for column in columns:
            if column not in df.columns:
                continue

            key_to_canonical, entries = self._build_column_mapping(df, column)
            taxonomy_columns[column] = entries

            df = df.with_columns(
                pl.col(column).map_elements(
                    lambda value: self._canonicalize_list_value(
                        value,
                        key_to_canonical,
                    ),
                    return_dtype=pl.List(pl.Utf8),
                ).alias(column)
            )
            df = df.with_columns(
                pl.col(column).map_elements(
                    self._keys_for_value,
                    return_dtype=pl.List(pl.Utf8),
                ).alias(f"{column}_keys")
            )

        return df, taxonomy_columns

    def build_taxonomy_artifact(
        self,
        domain: str,
        columns: dict[str, list[dict[str, object]]],
    ) -> dict[str, object]:
        generated_at = datetime.now(timezone.utc).isoformat()

        payload_for_hash = {
            "domain": domain,
            "columns": columns,
        }
        serialized = json.dumps(
            payload_for_hash,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        return {
            "domain": domain,
            "generated_at_utc": generated_at,
            "version": digest[:12],
            "hash": digest,
            "columns": columns,
        }

    def save_taxonomy_artifact(
        self,
        taxonomy: dict[str, object],
        target_path: Path,
    ) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            json.dumps(taxonomy, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
