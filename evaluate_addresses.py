"""Evaluate address completeness and suspicious-content detection."""

import openpyxl
from collections import Counter

OUTPUT_FILE = "output.xlsx"

SUSPICIOUS_PHRASES = (
    "find doctor",
    "by disease",
    "customer review",
    "made my work easy",
    "patient needs",
    "financial needs",
    "business travel",
    "complete platform",
    "delivery charge",
    "sim card",
    "cardholder",
    "vendor to ship",
    "correction online",
)

REQUIRES_VERIFICATION = (
    "verify on site",
    "verify",
    "estimate",
    "not separately disclosed",
)


def main():
    workbook = openpyxl.load_workbook(OUTPUT_FILE, data_only=True)
    sheet = workbook.active

    headers = [cell.value for cell in sheet[1]]
    rows = [
        dict(zip(headers, values))
        for values in sheet.iter_rows(min_row=2, values_only=True)
        if any(value is not None for value in values)
    ]

    total = len(rows)
    complete = 0
    suspicious = 0
    needs_verification = 0

    print("\n=== Address Quality Review ===")

    for row in rows:
        company = str(row.get("Entity Name") or "Unknown")
        address = str(row.get("Company Address") or "").strip()
        normalized = address.lower()

        is_populated = normalized not in {"", "not found", "none", "null"}
        is_suspicious = any(
            phrase in normalized for phrase in SUSPICIOUS_PHRASES
        )
        needs_review = any(
            phrase in normalized for phrase in REQUIRES_VERIFICATION
        )

        complete += int(is_populated)
        suspicious += int(is_suspicious)
        needs_verification += int(needs_review)

        if not is_populated:
            status = "MISSING"
        elif is_suspicious:
            status = "SUSPICIOUS"
        elif needs_review:
            status = "NEEDS VERIFICATION"
        else:
            status = "POPULATED - NOT INDEPENDENTLY VERIFIED"

        print(f"{company}: {status} | {address}")

    print("\n=== Summary ===")
    print(f"Total records: {total}")
    print(f"Populated addresses: {complete}/{total}")
    print(f"Suspicious addresses: {suspicious}/{total}")
    print(f"Addresses requiring verification: {needs_verification}/{total}")

    if total:
        print(f"Address completion rate: {complete / total * 100:.1f}%")

    print(
        "\nNote: This script detects missing fields and known suspicious "
        "phrases. It does not establish address accuracy."
    )


if __name__ == "__main__":
    main()
