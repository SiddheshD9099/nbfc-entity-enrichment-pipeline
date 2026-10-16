"""Validate enriched rows before persist / export."""

from __future__ import annotations

import re
from urllib.parse import urlparse

NOT_FOUND = "Not found"

_PARENT_EMPLOYEE_HINTS = re.compile(
    r"parent|group|holdings|consolidated|global|subsidiary|not separately disclosed|"
    r"verify entity vs group|hospital chain|network|finserv group",
    re.I,
)

_INCOMPLETE_ADDRESS_HINTS = re.compile(
    r"^\s*(contact us|n/a|tbd|unknown)\s*$|verify on site",
    re.I,
)


_SUSPICIOUS_ADDRESS_HINTS = re.compile(
    r"find doctor|by disease|customer review|"
    r"made my work easy|patient needs|financial needs|"
    r"business travel|complete platform|read more|"
    r"learn more|delivery charge|sim card|"
    r"cardholder|vendor to ship|correction online",
    re.I,
)

# Known official domains for the eight companies in the sample dataset.
_EXPECTED_DOMAINS = {
    "bajaj finance limited": ("bajajfinserv.in",),
    "hdfc ergo general insurance company limited": ("hdfcergo.com",),
    "apollo hospitals enterprise limited": ("apollohospitals.com",),
    "dr. reddy's laboratories limited": ("drreddys.com",),
    "manappuram finance limited": ("manappuram.com",),
    "icici lombard general insurance company limited": ("icicilombard.com",),
    "max healthcare institute limited": ("maxhealthcare.in",),
    "cipla limited": ("cipla.com",),
}


def _is_missing(value: str | None) -> bool:
    if value is None:
        return True
    s = str(value).strip()
    return not s or s.lower() == NOT_FOUND.lower()


def _website_matches_company(entity_name: str, website: str) -> bool:
    """Check whether a website uses an expected domain for a known sample company."""
    expected_domains = _EXPECTED_DOMAINS.get(entity_name.strip().lower())

    if not expected_domains:
        # Unknown companies still need manual or external verification.
        return True

    try:
        hostname = (urlparse(website).hostname or "").lower()
    except ValueError:
        return False

    return any(
        hostname == domain or hostname.endswith("." + domain)
        for domain in expected_domains
    )


def validate_enriched_row(row: dict) -> str:
    """
    Return validation_status: comma-separated flags, or 'ok'.

    Flags:
    missing_website, website_domain_mismatch, incomplete_address,
    possible_parent_employee_count
    """
    flags: list[str] = []

    entity_name = str(row.get("entity_name") or "")
    website = row.get("company_website")

    if _is_missing(website):
        flags.append("missing_website")
    elif not _website_matches_company(entity_name, str(website)):
        flags.append("website_domain_mismatch")

    address = row.get("company_address")

    if _is_missing(address):
        flags.append("incomplete_address")
    elif address and _SUSPICIOUS_ADDRESS_HINTS.search(str(address)):
        flags.append("suspicious_address")
    elif address and len(str(address).strip()) < 12:
        flags.append("incomplete_address")
    elif address and _INCOMPLETE_ADDRESS_HINTS.search(str(address)):
        flags.append("incomplete_address")

    employees = row.get("employee_size")

    if employees and not _is_missing(employees):
        text = str(employees)

        if _PARENT_EMPLOYEE_HINTS.search(text):
            flags.append("possible_parent_employee_count")

        if (
            "|" in text
            and re.search(r"group|parent|consolidated", text, re.I)
            and "possible_parent_employee_count" not in flags
        ):
            flags.append("possible_parent_employee_count")

    return "ok" if not flags else ",".join(flags)
