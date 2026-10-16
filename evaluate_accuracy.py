"""Evaluate website-domain matches against a manually defined reference set."""

import openpyxl
from urllib.parse import urlparse

OUTPUT_FILE = "output.xlsx"

# Reference domains for the eight-company sample dataset.
# These are evaluation targets and should be verified against official sources.
EXPECTED_DOMAINS = {
    "bajaj finance limited": "bajajfinserv.in",
    "hdfc ergo general insurance company limited": "hdfcergo.com",
    "apollo hospitals enterprise limited": "apollohospitals.com",
    "dr. reddy's laboratories limited": "drreddys.com",
    "manappuram finance limited": "manappuram.com",
    "icici lombard general insurance company limited": "icicilombard.com",
    "max healthcare institute limited": "maxhealthcare.in",
    "cipla limited": "cipla.com",
}


def get_domain(url):
    try:
        return (urlparse(str(url)).hostname or "").lower()
    except ValueError:
        return ""


def main():
    workbook = openpyxl.load_workbook(OUTPUT_FILE, data_only=True)
    sheet = workbook.active

    headers = [cell.value for cell in sheet[1]]
    records = [
        dict(zip(headers, row))
        for row in sheet.iter_rows(min_row=2, values_only=True)
        if any(value is not None for value in row)
    ]

    correct = 0
    checked = 0

    print("\n=== Website Domain Accuracy ===")

    for record in records:
        name = str(record.get("Entity Name") or "").strip().lower()
        website = record.get("Company Website")
        expected = EXPECTED_DOMAINS.get(name)

        if expected is None:
            print(f"UNVERIFIED REFERENCE: {name}")
            continue

        actual = get_domain(website)
        matches = actual == expected or actual.endswith("." + expected)

        checked += 1
        correct += int(matches)

        status = "MATCH" if matches else "MISMATCH"
        print(
            f"{status}: {record.get('Entity Name')} | "
            f"actual={actual or 'missing'} | expected={expected}"
        )

    print(f"\nRecords evaluated: {checked}")
    print(f"Correct domain matches: {correct}")

    if checked:
        print(f"Domain match rate: {correct / checked * 100:.1f}%")


if __name__ == "__main__":
    main()
