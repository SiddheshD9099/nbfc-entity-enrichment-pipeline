"""LeadLens BFSI / healthcare entity enrichment pipeline."""

from __future__ import annotations

import sys
import time

from data_reader import prepare_output_sheet, read_entities, write_entity_row
from data_validator import validate_enriched_row, _website_matches_company
from db_writer import get_cached_entity, upsert_rows
from logger import setup_logger
from scraper import linkedin_employees, scrape_site
from search_resolver import find_linkedin, find_website, polite
from seed_fallback import (
    apply_seed_to_address,
    apply_seed_to_employees,
    apply_seed_to_urls,
    get_seed,
)


def enrich_entity(
    entity_name: str,
    entity_type: str | None,
    use_seed: bool,
    database_url: str | None = None,
    sqlite_path: str | None = None,
) -> dict:
    cached = get_cached_entity(
        entity_name,
        database_url=database_url,
        sqlite_path=sqlite_path,
    )

    if cached:
        required_fields = (
            "company_website",
            "company_address",
            "employee_size",
        )

        complete = all(
            cached.get(field)
            and str(cached[field]).strip().lower() not in {
                "not found", "none", "null", ""
            }
            for field in required_fields
        )

        if complete and cached.get("validation_status") == "ok":
            print("    cache hit: reusing complete validated record")
            cached["entity_type"] = entity_type or cached.get("entity_type")
            return cached

        print("    cache record incomplete or flagged; refreshing")

    seed = get_seed(entity_name, use_seed)
    sources: set[str] = set()

    website = find_website(entity_name)
    polite()
    linkedin = find_linkedin(entity_name)
    polite()

    if website or linkedin:
        sources.add("live")

    if website and not _website_matches_company(entity_name, website):
        website = None

    website, linkedin = apply_seed_to_urls(
        entity_name, seed, website, linkedin, sources
    )

    site = (
        scrape_site(website)
        if website
        else dict(address=None, employees=None, contacts=None)
    )

    if any(site.values()):
        sources.add("live")

    address = apply_seed_to_address(
        entity_name, seed, site["address"] or None, sources
    )

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
    # Preserve previously populated fields when refresh finds no replacement.
    if cached:
        cached_status = {
            item.strip()
            for item in (cached.get("validation_status") or "").split(",")
            if item.strip()
        }

        field_blockers = {
            "company_website": {
                "website_domain_mismatch",
                "domain_mismatch",
            },
            "company_linkedin": {"linkedin_mismatch"},
            "company_address": {
                "incomplete_address",
                "suspicious_address",
            },
            "employee_size": {"possible_parent_employee_count"},
            "contacts": set(),
        }

        missing_values = {"", "not found", "none", "null", "n/a"}

        for field, blockers in field_blockers.items():
            new_value = row.get(field)
            old_value = cached.get(field)

            new_missing = (
                not new_value
                or str(new_value).strip().lower() in missing_values
                or (
                    field == "contacts"
                    and str(new_value).strip().lower()
                    == "no direct contacts published (contact form only)"
                )
            )

            old_available = (
                old_value
                and str(old_value).strip().lower() not in missing_values
            )

            if (
                new_missing
                and old_available
                and not cached_status.intersection(blockers)
            ):
                row[field] = old_value
                
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

    # Start measuring the pipeline
    start_time = time.perf_counter()

    # Read the input Excel file
    wb, header_row, _cols, entities = read_entities(input_path)

    # Count the company records
    total_records = len(entities)

    print(f"\nTotal company records: {total_records}")

    ws = wb.active
    prepare_output_sheet(ws, header_row)

    db_batch: list[dict] = []
    try:
        for idx, entity in enumerate(entities, start=1):
            print(f"\n[{idx}] {entity.entity_name}" + (f" ({entity.entity_type})" if entity.entity_type else ""))
            row = enrich_entity(
                entity.entity_name,
                entity.entity_type,
                use_seed=use_seed,
                database_url=database_url,
                sqlite_path=sqlite_path,
            )
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

        elapsed_time = time.perf_counter() - start_time

        print(f"Total input records: {total_records}")
        print(f"Total execution time: {elapsed_time:.2f} seconds")

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
    process(
        in_file,
        out_file,
        use_seed=use_seed,
        log_path=log_path,
        sqlite_path=__import__("os").environ.get(
            "LEADLENS_SQLITE_PATH", "leadlens.db"
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
