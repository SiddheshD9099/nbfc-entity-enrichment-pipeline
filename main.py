"""LeadLens BFSI / healthcare entity enrichment pipeline."""

from __future__ import annotations

import sys

from data_reader import prepare_output_sheet, read_entities, write_entity_row
from data_validator import validate_enriched_row
from db_writer import upsert_rows
from logger import setup_logger
from scraper import linkedin_employees, scrape_site
from search_resolver import find_linkedin, find_website, polite
from seed_fallback import (
    apply_seed_to_address,
    apply_seed_to_employees,
    apply_seed_to_urls,
    get_seed,
)


def enrich_entity(entity_name: str, entity_type: str | None, use_seed: bool) -> dict:
    seed = get_seed(entity_name, use_seed)
    sources: set[str] = set()

    website = find_website(entity_name)
    polite()
    linkedin = find_linkedin(entity_name)
    polite()
    if website or linkedin:
        sources.add("live")

    website, linkedin = apply_seed_to_urls(entity_name, seed, website, linkedin, sources)

    site = scrape_site(website) if website else dict(address=None, employees=None, contacts=None)
    if any(site.values()):
        sources.add("live")

    address = site["address"] or None
    address = apply_seed_to_address(entity_name, seed, address, sources)

    employees = site["employees"] or linkedin_employees(linkedin)
    if employees and site["employees"]:
        employees = f"{employees} (company site)"
    employees = apply_seed_to_employees(entity_name, seed, employees, sources)
    if not employees and linkedin:
        employees = f"Check manually: {linkedin}"

    contacts = site["contacts"] or "No direct contacts published (contact form only)"

    row = {
        "entity_name": entity_name,
        "entity_type": entity_type,
        "company_website": website or "Not found",
        "company_linkedin": linkedin or "Not found",
        "company_address": address or "Not found",
        "employee_size": employees or "Not found",
        "contacts": contacts,
        "source": "+".join(sorted(sources)) or "none",
    }
    row["validation_status"] = validate_enriched_row(row)
    return row


def process(
    input_path: str,
    output_path: str,
    use_seed: bool = True,
    log_path: str | None = None,
    database_url: str | None = None,
    sqlite_path: str | None = None,
) -> None:
    setup_logger(log_path)
    wb, header_row, _cols, entities = read_entities(input_path)
    ws = wb.active
    prepare_output_sheet(ws, header_row)

    db_batch: list[dict] = []
    try:
        for idx, entity in enumerate(entities, start=1):
            print(f"\n[{idx}] {entity.entity_name}" + (f" ({entity.entity_type})" if entity.entity_type else ""))
            row = enrich_entity(entity.entity_name, entity.entity_type, use_seed=use_seed)
            write_entity_row(ws, entity.row_index, row)
            db_batch.append(row)
            print(
                f"    -> site={row['company_website']} | li={row['company_linkedin']} | "
                f"addr={row['company_address'] != 'Not found'} | src={row['source']} | "
                f"validation={row['validation_status']}"
            )
    finally:
        wb.save(output_path)
        print(f"\nSaved: {output_path}")
        try:
            upsert_rows(db_batch, database_url=database_url, sqlite_path=sqlite_path)
            print(f"Database: wrote {len(db_batch)} row(s)")
        except Exception as e:
            print(f"Database write failed: {e}")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = [a for a in argv if not a.startswith("--")]
    in_file = args[0] if len(args) > 0 else "sample_bfsi_healthcare_entities.xlsx"
    out_file = args[1] if len(args) > 1 else "output.xlsx"
    use_seed = "--no-seed" not in argv
    log_path = None
    for a in argv:
        if a.startswith("--log="):
            log_path = a.split("=", 1)[1]
    process(in_file, out_file, use_seed=use_seed, log_path=log_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
