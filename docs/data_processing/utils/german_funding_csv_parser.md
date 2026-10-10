# `data_processing.utils.german_funding_csv_parser`

Parser for CorrelAid's published Förderdatenbank CSV export.

The source is the published distribution of the [`fdb_scraper`](https://github.com/CorrelAid/fdb_scraper)
project, rebuilt weekly (Monday 03:00 UTC) from the BMWE XML export at
`https://www.foerderdatenbank.de/FDB/WS/export` and validated against a pandera schema
before publication. SeFuSe reads the published table rather than parsing the raw XML
itself, so upstream schema drift surfaces as a failed upstream build instead of as
silent data loss here.

| What | URL |
|---|---|
| The data | `https://fdb.cdl.correlaid.org/data/programme.csv` |
| Column contract (CSVW) | `https://fdb.cdl.correlaid.org/table-schema.json` |
| Vocabulary (SKOS) | `https://fdb.cdl.correlaid.org/def/fdb` |

**Licence:** CC BY-ND 4.0, rights holder Bundesministerium für Wirtschaft und Energie.
Every row carries its own attribution string in `license_info`, and the German search
page renders a source/licence credit below its results.

---

## Module Constants

| Constant | Description |
|---|---|
| `GERMAN_SCHEMA` | Ordered dict of `{column_name: polars_dtype}` defining the output DataFrame schema. Mirrors the structure expected by `GermanFundingProcessor.transform` and the downstream `CommonDataPipeline`. |
| `_PLAIN_COLUMNS` | Source column → output column for values copied across without transformation. |
| `_TAXONOMY_COLUMNS` | The four taxonomy columns whose codes are mapped to German display names. |

The source's history columns (`on_website_from`, `last_updated`, `first_scraped_at`, `previous_update_dates`) are deliberately **not** carried: nothing in SeFuSe displays or filters on them, and they are empty for almost every programme — `on_website_from` is null for everything upstream's first load already saw (~99%), `last_updated` until a programme first changes (~97%).

---

## Two properties of the source format

**Nested values are JSON-encoded per cell.** CSV cannot carry a list, so a taxonomy
cell reads `'["zuschuss","darlehen"]'` and `further_links` reads
`'[{"url":"…","title":"…"}]'`. The convention is declared per column in the linked
table schema.

**Taxonomies are codes, not labels.** The export states `zuschuss`; the German display
name lives in a separate vocabulary, vendored as
`data_processing/src/config/german_vocab.py`. Codes absent from that vocabulary are
kept verbatim rather than dropped or guessed at, so an upstream addition shows up as a
recognisable slug in the taxonomy artifact.

---

## Class `GermanFundingCsvParser`

### `parse(csv_path: Path) -> pl.DataFrame`

Read the published CSV and return a DataFrame conforming to `GERMAN_SCHEMA`.

The file is read with `infer_schema_length=0` so every column arrives as `Utf8`: the
JSON-in-cell columns would otherwise be sampled for a type they do not have, and at
~55 MB the inference pass is not worth paying for when every column is cast explicitly
afterwards.

**Steps:**

1. Copy the plain text columns, renaming to SeFuSe's schema (`short_description` →
   `project_short_description`, `legal_citation` → `more_info`,
   `contact_info_road` → `contact_info_street`).
2. Decode the JSON list cells; a null cell becomes an empty list.
3. Map taxonomy codes to German labels via `CODE_LABELS`.
4. Join the `funding_body` label list into the scalar schema slot; an empty list
   becomes null.
5. Reduce the `further_links` `{url, title}` structs to a list of URLs.
6. Map `absent` to a boolean.
7. Decode `keywords_extracted` into a `List(Utf8)`.
8. Coalesce `description` (the text that gets embedded) onto `legal_basis` where
   upstream states no summary — roughly 22% of programmes. Without this the cleaner
   would fill them with the literal `"N/A"` and that string would be embedded.
9. Drop programmes with no text at all (3 rows upstream, the same ones that carry no
   title): there is nothing to embed for them.
10. Fill any column upstream no longer ships with typed nulls, then select and cast in
    the declared order, so the frame's shape never depends on the input.

**Returns:** `pl.DataFrame` conforming to `GERMAN_SCHEMA`. An empty schema DataFrame is
returned when the CSV holds no rows.

### `keywords_extracted`

Upstream joins a programme's keywords with plain spaces, and 87.7% of values carry no
separator at all, so the raw `keywords` string cannot be split by a rule. Upstream
splits it with a fine-tuned German encoder and marks the column `inferred`; every term
is verifiably a contiguous span of the raw string, but where the boundaries fall is a
model decision. SeFuSe carries the segmented list — it is both embedded and displayed —
and does not carry the raw column.
