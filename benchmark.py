"""Generate a basic quality report for the entity enrichment output."""

from collections import Counter
from pathlib import Path

import openpyxl

OUTPUT_FILE = Path("output.xlsx")

REQUIRED_COLUMNS = [
    "Entity Name",
    "Company Website",
    "Company Address",
    "Employee Size",
    "validation_status",
]


def main():
    if not OUTPUT_FILE.exists():
        raise FileNotFoundError(
            f"{OUTPUT_FILE} not found. Run python main.py first."
        )

    workbook = openpyxl.load_workbook(OUTPUT_FILE, data_only=True)
    sheet = workbook.active

    headers = [cell.value for cell in sheet[1]]
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in headers]

    if missing_columns:
        raise ValueError(f"Missing columns: {missing_columns}")

    rows = [
        dict(zip(headers, values))
        for values in sheet.iter_rows(min_row=2, values_only=True)
        if any(value is not None for value in values)
    ]

    total = len(rows)

    if total == 0:
        print("No records found.")
        return

    def populated(column):
        return sum(
            1
            for row in rows
            if str(row.get(column) or "").strip().lower()
            not in {"", "not found", "none", "null"}
        )

    website_count = populated("Company Website")
    address_count = populated("Company Address")
    employee_count = populated("Employee Size")

    statuses = Counter(
        str(row.get("validation_status") or "missing_status")
        for row in rows
    )

    print("\n=== Entity Enrichment Benchmark ===")
    print(f"Total records: {total}")
    print(
        f"Website completion: {website_count}/{total} "
        f"({website_count / total * 100:.1f}%)"
    )
    print(
        f"Address completion: {address_count}/{total} "
        f"({address_count / total * 100:.1f}%)"
    )
    print(
        f"Employee-size completion: {employee_count}/{total} "
        f"({employee_count / total * 100:.1f}%)"
    )

    print("\nValidation statuses:")
    for status, count in statuses.items():
        print(f"  {status}: {count}")

    print(
        "\nNote: Completion measures whether a field is populated. "
        "It does not measure whether its value is correct."
    )


if __name__ == "__main__":
    main()
