"""Validate enriched rows before persist / export."""

from __future__ import annotations

import re

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


def _is_missing(value: str | None) -> bool:
    if value is None:
        return True
    s = str(value).strip()
    return not s or s.lower() == NOT_FOUND.lower()


def validate_enriched_row(row: dict) -> str:
    """
    Return validation_status: comma-separated flags, or 'ok'.
    Flags: missing_website, incomplete_address, possible_parent_employee_count
    """
    flags: list[str] = []

    website = row.get("company_website")
    if _is_missing(website):
        flags.append("missing_website")

    address = row.get("company_address")
    if _is_missing(address):
        flags.append("incomplete_address")
    elif address and len(str(address).strip()) < 12:
        flags.append("incomplete_address")
    elif address and _INCOMPLETE_ADDRESS_HINTS.search(str(address)):
        flags.append("incomplete_address")

    employees = row.get("employee_size")
    if employees and not _is_missing(employees):
        text = str(employees)
        if _PARENT_EMPLOYEE_HINTS.search(text):
            flags.append("possible_parent_employee_count")
        if "|" in text and re.search(r"group|parent|consolidated", text, re.I):
            if "possible_parent_employee_count" not in flags:
                flags.append("possible_parent_employee_count")

    return "ok" if not flags else ",".join(flags)
