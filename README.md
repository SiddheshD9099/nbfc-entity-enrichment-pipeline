# LeadLens: Automated Company Data Enrichment

Python tool that takes a list of company names from an Excel file and fills in, for each one:

- Company website
- Company LinkedIn page
- Company address
- Employee size
- Contacts available on the website (emails / phone numbers)

Output is written back to a new Excel file with a **Source** column showing where each row's data came from.

## Why this exists

Sales and research teams spend hours searching each account by hand. This script does the lookup for a whole list in minutes and flags anything that still needs a human check.

## How it works

1. **Reads** the `Account Name` column from the input `.xlsx` (openpyxl).
2. **Finds the website and LinkedIn URL** using a chain of search engines: Google Custom Search API (optional) -> Bing -> DuckDuckGo -> `googlesearch`. Engines that fail to connect are skipped for the rest of the run. Redirect links are decoded to real URLs, and aggregator sites (Wikipedia, ZoomInfo, etc.) are filtered out.
3. **Scrapes the company's own site** (requests + BeautifulSoup). It discovers Contact / About / Company links from the homepage, then extracts:
   - Address from JSON-LD, `<address>` tags, Japanese `〒` postal blocks, or English labels
   - Employee count when the site states it
   - Emails and phone numbers from `mailto:` / `tel:` links
4. **Falls back to a verified seed table** for any cell live lookup could not fill, so the output is never blank.
5. **Saves** the result, even if the run is interrupted.

## Project structure

```
Populate_company_data/
|-- populate_company_data_final.py   # main script
|-- Walkins_Test_05082026.xlsx       # input (Account Name list)
|-- output.xlsx                      # generated result
`-- README.md
```

## Setup

Requires Python 3.9+.

```bash
python -m pip install requests beautifulsoup4 openpyxl
```

## Usage

```bash
python populate_company_data_final.py Walkins_Test_05082026.xlsx output.xlsx
```

Options:

| Option                                    | Effect                                                                       |
| ----------------------------------------- | ---------------------------------------------------------------------------- |
| `--no-seed`                               | Disable the seed fallback and show pure live results                         |
| `GOOGLE_API_KEY` + `GOOGLE_CX` (env vars) | Use the official Google Custom Search API first (free tier: 100 queries/day) |

## Output columns

| Column                        | Meaning                                   |
| ----------------------------- | ----------------------------------------- |
| Company Website               | Official site (homepage)                  |
| Company Linkedin              | LinkedIn company page                     |
| Company Address               | Head office / contact address             |
| Employee Size                 | From company site, LinkedIn, or seed data |
| Contacts Available on Website | Emails and phones published on the site   |
| Source                        | `live`, `seed`, or `live+seed`            |

## Known limitations

- LinkedIn hides employee counts behind login, so Employee Size often comes from the company site or needs a manual check.
- Many corporate sites publish only a contact form, so "no direct contacts published" is a valid result.
- Sites that load content with JavaScript may not expose their address to a plain HTTP scraper.
- Subsidiaries often do not publish their own headcount, so a parent-company figure may be shown and is labelled as such.
- Scraping search engines can be blocked by some networks. For dependable results at scale, use the Google API option or a paid data provider (Apollo, ZoomInfo, Clearbit).

## Tech stack

Python, requests, BeautifulSoup4, openpyxl, regex, JSON-LD parsing.
