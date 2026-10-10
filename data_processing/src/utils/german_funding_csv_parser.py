"""Parser for CorrelAid's published Förderdatenbank CSV export."""

from pathlib import Path

import polars as pl

from data_processing.config import CODE_LABELS


# Output contract of this parser. `GermanFundingProcessor` renames `absent` to
# `deleted`; everything else flows unchanged into `CommonDataPipeline`.
#
# The source's history columns (on_website_from, last_updated, first_scraped_at,
# previous_update_dates) are deliberately not carried. They are ISO weeks derived by
# comparing two weekly loads, and they are empty for almost every programme:
# on_website_from is null for everything upstream's first load already saw (~99%) and
# last_updated until a programme first changes (~97%). Nothing in SeFuSe displays or
# filters on them.
GERMAN_SCHEMA = {
    "id_hash": pl.Utf8,
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
    "license_info": pl.Utf8,
    "absent": pl.Boolean,
    "project_short_description": pl.Utf8,
    "project_full_description": pl.Utf8,
    "status_note": pl.Utf8,
    "deadlines": pl.Utf8,
    # Model-segmented keywords. Upstream joins keywords with plain spaces and 87.7% of
    # values carry no separator at all, so the raw `keywords` string cannot be split by
    # a rule; upstream splits it with a fine-tuned German encoder and marks the column
    # `inferred`. Embedded and displayed; the raw column is not carried.
    "keywords_extracted": pl.List(pl.Utf8),
}

# Source column -> output column, for values copied across without transformation.
_PLAIN_COLUMNS = {
    "id_hash": "id_hash",
    "url": "url",
    "title": "title",
    # fdb's `summary`: the user-facing "what, how much, for whom" text. This is what
    # gets embedded — `legal_basis` (the full Richtlinie) is not suitable for it.
    "description": "project_full_description",
    "short_description": "project_short_description",
    "legal_basis": "legal_basis",
    # fdb renamed the export's `proc_description` to `legal_citation`; SeFuSe has
    # always surfaced that property as `more_info`.
    "legal_citation": "more_info",
    "license_info": "license_info",
    "status_note": "status_note",
    "deadlines": "deadlines",
    # fdb splits the address into 13 columns; SeFuSe carries seven of them.
    "contact_info_institution": "contact_info_institution",
    "contact_info_road": "contact_info_street",
    "contact_info_city": "contact_info_city",
    "contact_info_fax": "contact_info_fax",
    "contact_info_phone": "contact_info_phone",
    "contact_info_email": "contact_info_email",
    "contact_info_website": "contact_info_website",
}

# Columns whose cells hold a JSON array of strings, decoded then code-mapped.
_TAXONOMY_COLUMNS = (
    "funding_type",
    "funding_area",
    "funding_location",
    "eligible_applicants",
)

_FURTHER_LINKS_DTYPE = pl.List(pl.Struct({"url": pl.Utf8, "title": pl.Utf8}))


class GermanFundingCsvParser:
    """Parses CorrelAid's Förderdatenbank CSV into a typed Polars DataFrame.

    The source is the published distribution of the ``fdb_scraper`` project
    (https://github.com/CorrelAid/fdb_scraper), rebuilt weekly from the BMWE XML
    export at https://www.foerderdatenbank.de/FDB/WS/export and validated against a
    pandera schema before publication. Its column contract is documented at
    https://fdb.cdl.correlaid.org/table-schema.json.

    Two properties of that format drive this parser:

    - **Nested values are JSON-encoded per cell.** CSV cannot carry a list, so a
      taxonomy cell reads ``'["zuschuss","darlehen"]'`` and ``further_links`` reads
      ``'[{"url":"…","title":"…"}]'``.
    - **Taxonomies are codes, not labels.** The export states ``zuschuss``; the
      German display name lives in a separate vocabulary, vendored here as
      ``data_processing/src/config/german_vocab.py``. Codes with no entry in that
      vocabulary are kept verbatim rather than dropped or guessed at, so an upstream
      addition shows up as a recognisable slug in the taxonomy artifact.

    The data is licensed CC BY-ND 4.0 with the BMWE as rights holder; every row
    carries its own attribution string in ``license_info``.

    Example:
        parser = GermanFundingCsvParser()
        df = parser.parse(Path("data/german_programme.csv"))
    """

    @staticmethod
    def _source_or_null(df: pl.DataFrame, source: str, dtype: pl.DataType) -> pl.Expr:
        """Return an expression reading `source`, or a typed null if it is absent.

        Upstream validates its own output, so a missing column means a deliberate
        schema change on their side rather than corruption. Filling it with nulls
        keeps this pipeline running on the remaining columns instead of failing the
        whole refresh.

        Args:
            df (pl.DataFrame): The raw frame read from the CSV.
            source (str): Column name expected in the CSV.
            dtype (pl.DataType): Dtype to cast the null literal to when absent.

        Returns:
            pl.Expr: An expression yielding the column's values, or nulls.
        """
        if source in df.columns:
            return pl.col(source)
        return pl.lit(None).cast(dtype)

    def _decode_list(self, df: pl.DataFrame, source: str) -> pl.Expr:
        """Decode a JSON-array cell into a ``List(Utf8)``, empty when the cell is null."""
        return (
            self._source_or_null(df, source, pl.Utf8)
            .str.json_decode(dtype=pl.List(pl.Utf8))
            .fill_null([])
        )

    def _decode_taxonomy(self, df: pl.DataFrame, column: str) -> pl.Expr:
        """Decode a taxonomy cell and map its codes to German display names."""
        return self._decode_list(df, column).list.eval(
            # `replace` without a default leaves unmatched values untouched, which is
            # what keeps an unknown upstream code visible instead of silently lost.
            pl.element().replace(CODE_LABELS[column])
        ).alias(column)

    def _decode_funding_body(self, df: pl.DataFrame) -> pl.Expr:
        """Map the ``funding_body`` code list to labels and join it into one string.

        The source allows several funding levels per programme (``["bund","land"]``),
        but SeFuSe's schema slot is a scalar, so the labels are joined rather than one
        of them being picked arbitrarily. An empty list becomes null so `DataCleaner`
        can fill it like any other missing string.
        """
        joined = (
            self._decode_list(df, "funding_body")
            .list.eval(pl.element().replace(CODE_LABELS["funding_body"]))
            .list.join(", ")
        )
        return (
            pl.when(joined.str.len_chars() > 0)
            .then(joined)
            .otherwise(None)
            .alias("funding_body")
        )

    def _decode_further_links(self, df: pl.DataFrame) -> pl.Expr:
        """Reduce the ``{url, title}`` structs to a plain list of URLs."""
        return (
            self._source_or_null(df, "further_links", pl.Utf8)
            .str.json_decode(dtype=_FURTHER_LINKS_DTYPE)
            .fill_null([])
            .list.eval(pl.element().struct.field("url"))
            .alias("further_links")
        )

    def parse(self, csv_path: Path) -> pl.DataFrame:
        """Parse the published CSV and return a DataFrame matching ``GERMAN_SCHEMA``.

        The file is read with all columns as strings (``infer_schema_length=0``):
        the JSON-in-cell columns would otherwise be sampled for a type they do not
        have, and at ~55 MB the inference pass is not worth paying for when every
        column is cast explicitly afterwards.

        Args:
            csv_path (Path): Path to the downloaded ``programme.csv``.

        Returns:
            pl.DataFrame: DataFrame conforming to ``GERMAN_SCHEMA``. An empty
                schema DataFrame is returned when the CSV holds no rows.
        """
        raw_df = pl.read_csv(csv_path, infer_schema_length=0)

        if raw_df.is_empty():
            return pl.DataFrame(
                schema=[(col, dtype) for col, dtype in GERMAN_SCHEMA.items()]
            )

        expressions = [
            self._source_or_null(raw_df, source, pl.Utf8).alias(target)
            for source, target in _PLAIN_COLUMNS.items()
        ]
        expressions.extend(
            self._decode_taxonomy(raw_df, column) for column in _TAXONOMY_COLUMNS
        )
        expressions.append(self._decode_funding_body(raw_df))
        expressions.append(self._decode_further_links(raw_df))
        expressions.append(
            self._decode_list(raw_df, "keywords_extracted").alias("keywords_extracted")
        )
        # `absent` marks a programme that has left the export. Upstream renamed it
        # from "deleted" because absence has several causes — the programme ended,
        # was reorganised, or upstream restructured their data.
        expressions.append(
            (
                self._source_or_null(raw_df, "absent", pl.Utf8)
                .str.to_lowercase()
                .eq("true")
                .fill_null(False)
            ).alias("absent")
        )
        # `description` is what gets embedded, so it must never be empty: `DataCleaner`
        # fills a null with the literal "N/A", which would put ~22% of the corpus into
        # Qdrant as the string "N/A". Upstream states no summary for those programmes,
        # only the Richtlinie, so fall back to it — the same coalesce the previous XML
        # parser did with `full_desc or body_html`.
        expressions.append(
            pl.coalesce(
                self._source_or_null(raw_df, "description", pl.Utf8),
                self._source_or_null(raw_df, "legal_basis", pl.Utf8),
            ).alias("description")
        )

        df = raw_df.select(expressions)

        # Drop programmes with no text at all. There is nothing to embed for them, and
        # keeping them would put a document reading "N/A" into Qdrant. Upstream notes
        # these are the same rows that carry no title. The previous XML parser dropped
        # them for the same reason.
        df = df.filter(pl.col("description").is_not_null())

        return df.select(list(GERMAN_SCHEMA.keys())).with_columns(
            [pl.col(col).cast(dtype) for col, dtype in GERMAN_SCHEMA.items()]
        )
