"""Automated tests for entity enrichment validation."""

from data_validator import validate_enriched_row


def make_row(**overrides):
    row = {
        "entity_name": "ICICI Lombard General Insurance Company Limited",
        "company_website": "https://www.icicilombard.com",
        "company_address": (
            "ICICI Lombard House, 414, Veer Savarkar Marg, "
            "Mumbai 400025, India"
        ),
        "employee_size": "Not found",
    }
    row.update(overrides)
    return row


def test_valid_row():
    assert validate_enriched_row(make_row()) == "ok"


def test_wrong_website_is_flagged():
    result = validate_enriched_row(
        make_row(company_website="https://www.icici.bank.in")
    )
    assert "website_domain_mismatch" in result


def test_missing_website_is_flagged():
    result = validate_enriched_row(make_row(company_website="Not found"))
    assert "missing_website" in result


def test_suspicious_address_is_flagged():
    result = validate_enriched_row(
        make_row(
            company_address=(
                "Pay a delivery charge of 100 for the vendor "
                "to ship the SIM card"
            )
        )
    )
    assert "suspicious_address" in result


def test_missing_address_is_flagged():
    result = validate_enriched_row(make_row(company_address="Not found"))
    assert "incomplete_address" in result


def test_group_employee_count_is_flagged():
    result = validate_enriched_row(
        make_row(employee_size="10,000+ (global group)")
    )
    assert "possible_parent_employee_count" in result


if __name__ == "__main__":
    tests = [
        test_valid_row,
        test_wrong_website_is_flagged,
        test_missing_website_is_flagged,
        test_suspicious_address_is_flagged,
        test_missing_address_is_flagged,
        test_group_employee_count_is_flagged,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print(f"\nAll {len(tests)} tests passed.")
