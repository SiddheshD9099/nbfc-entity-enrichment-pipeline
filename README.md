# nbfc-entity-enrichment-pipeline

Python pipeline that takes a list of regulated and healthcare entities (NBFCs, insurers, hospital chains, pharma companies) from an Excel file and fills in, for each one:

- Company website
- Company LinkedIn page
- Company address
- Employee size
- Contacts available on the website (emails / phone numbers)

Output is written to **output.xlsx** (for review) and to a **SQLite or PostgreSQL** table (for dashboards and downstream jobs). Each row includes a **Source** column (live / seed / live+seed) and a **validation_status** flag for data-quality checks.

## Why this exists

Compliance, underwriting, and provider-network teams need consistent firmographics across NBFCs, insurers, hospitals, and pharma chains. Manual lookup does not scale. This pipeline automates website resolution and on-site extraction for a batch of entity names from public regulator-style lists (RBI NBFC register, IRDAI insurer lists, etc.), while logging search failures and seed fallbacks instead of failing silently.

## How it works

1. **Reads** the `Entity Name` column (and optional `Entity Type`: NBFC / Insurer / Hospital / Pharma) from the input `.xlsx` (`data_reader.py`).
2. **Finds the website and LinkedIn URL** using a chain of search engines (`search_resolver.py`): Google Custom Search API (optional) → Bing → DuckDuckGo → `googlesearch`. Each engine is retried with exponential backoff before it is skipped for the rest of the run. Events are logged to `leadlens_enrichment.log` (`logger.py`).
3. **Scrapes the company's own site** (`scraper.py`, requests + BeautifulSoup). It discovers Contact / About / Company links from the homepage, then extracts:
   - Address from JSON-LD, `<address>` tags, Japanese `〒` postal blocks, or English labels
   - Employee count when the site states it
   - Emails and phone numbers from `mailto:` / `tel:` links
4. **Falls back to a verified seed table** (`seed_fallback.py`) for any cell live lookup could not fill.
5. **Validates** each row (`data_validator.py`) — e.g. missing website, thin address, employee count that looks like a parent/group figure.
6. **Saves** Excel and appends rows to the database (`db_writer.py`), even if the run is interrupted (Excel save in `finally`).

## Project structure

```
Leadlens/
|-- main.py                          # orchestrates the pipeline
|-- data_reader.py                   # input Excel read + output column layout
|-- search_resolver.py               # multi-engine search + retries
|-- scraper.py                       # homepage / contact page scraping
|-- seed_fallback.py                 # seed table + fallback helpers
|-- data_validator.py                # validation_status flags
|-- db_writer.py                     # SQLite / PostgreSQL persist
|-- logger.py                        # timestamped enrichment log file
|-- populate_company_data_final.py   # legacy CLI (calls main.py)
|-- sample_bfsi_healthcare_entities.xlsx
|-- output.xlsx                      # generated result
|-- leadlens.db                      # default SQLite output (generated)
|-- leadlens_enrichment.log          # generated log
`-- README.md
```

## Setup

Requires Python 3.9+.

```bash
python -m pip install requests beautifulsoup4 openpyxl
```

Optional:

```bash
python -m pip install psycopg2-binary   # PostgreSQL via LEADLENS_DATABASE_URL
python -m pip install googlesearch-python  # last-resort search engine
```

## Usage

```bash
python main.py sample_bfsi_healthcare_entities.xlsx output.xlsx
```

Options:

| Option / env | Effect |
| --- | --- |
| `--no-seed` | Disable the seed fallback and show pure live results |
| `--log=path` | Custom log file path (default: `leadlens_enrichment.log`) |
| `GOOGLE_API_KEY` + `GOOGLE_CX` | Use Google Custom Search API first (free tier: 100 queries/day) |
| `LEADLENS_DATABASE_URL` | PostgreSQL connection string (or `sqlite:///./leadlens.db`) |
| `LEADLENS_SQLITE_PATH` | SQLite file path when no URL is set (default: `leadlens.db`) |

### Sample input format

| Entity Name | Entity Type |
| --- | --- |
| Bajaj Finance Limited | NBFC |
| HDFC ERGO General Insurance Company Limited | Insurer |
| Apollo Hospitals Enterprise Limited | Hospital |
| Dr. Reddy's Laboratories Limited | Pharma |

## Output columns

| Column | Meaning |
| --- | --- |
| Entity Name | Input entity |
| Entity Type | NBFC / Insurer / Hospital / Pharma (if provided) |
| Company Website | Official site (homepage) |
| Company Linkedin | LinkedIn company page |
| Company Address | Head office / contact address |
| Employee Size | From company site, LinkedIn, or seed data |
| Contacts Available on Website | Emails and phones published on the site |
| Source | `live`, `seed`, or `live+seed` |
| validation_status | `ok` or comma-separated flags (e.g. `missing_website`, `incomplete_address`, `possible_parent_employee_count`) |

## Known limitations

- LinkedIn hides employee counts behind login, so Employee Size often comes from the company site or needs a manual check.
- Many corporate sites publish only a contact form, so "no direct contacts published" is a valid result.
- Sites that load content with JavaScript may not expose their address to a plain HTTP scraper.
- Subsidiaries often do not publish their own headcount, so a parent-company figure may be shown and is labelled as such.
- Scraping search engines can be blocked by some networks. For dependable results at scale, use the Google API option or a paid data provider (Apollo, ZoomInfo, Clearbit).

## Tech stack

Python, requests, BeautifulSoup4, openpyxl, SQLite, PostgreSQL (optional), structured file logging, regex, JSON-LD parsing.
