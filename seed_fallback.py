"""Verified seed rows for BFSI / healthcare entities when live lookup misses a field."""

from logger import log_seed_fallback

# Used ONLY to fill cells live lookup missed.
SEED = {
    "bajaj finance limited": dict(
        website="https://www.bajajfinserv.in/bajaj-finance-limited",
        linkedin="https://www.linkedin.com/company/bajaj-finance-limited",
        address="Akurdi, Pune, Maharashtra, India (registered office; verify on site)",
        employees="Not separately disclosed | Bajaj Finserv group scale",
    ),
    "hdfc ergo general insurance company limited": dict(
        website="https://www.hdfcergo.com",
        linkedin="https://www.linkedin.com/company/hdfc-ergo-general-insurance",
        address="D-301, 3rd Floor, Eastern Business District, LBS Marg, Bhandup West, Mumbai 400078, India",
        employees="5,001-10,000 (LinkedIn band; verify)",
    ),
    "apollo hospitals enterprise limited": dict(
        website="https://www.apollohospitals.com",
        linkedin="https://www.linkedin.com/company/apollo-hospitals",
        address="No. 21, Greams Lane, Off Greams Road, Chennai 600006, Tamil Nadu, India",
        employees="10,000+ (group; hospital chain)",
    ),
    "dr. reddy's laboratories limited": dict(
        website="https://www.drreddys.com",
        linkedin="https://www.linkedin.com/company/dr-reddys-laboratories",
        address="8-2-337, Road No. 3, Banjara Hills, Hyderabad 500034, Telangana, India",
        employees="10,001+ (global group)",
    ),
    "manappuram finance limited": dict(
        website="https://www.manappuram.com",
        linkedin="https://www.linkedin.com/company/manappuram-finance-ltd",
        address="Manappuram House, Valapad, Thrissur, Kerala 680567, India",
        employees="5,001-10,000 (estimate; verify on site)",
    ),
    "icici lombard general insurance company limited": dict(
        website="https://www.icicilombard.com",
        linkedin="https://www.linkedin.com/company/icici-lombard",
        address="ICICI Lombard House, 414, Veer Savarkar Marg, Prabhadevi, Mumbai 400025, India",
        employees="10,001+ (LinkedIn band; verify)",
    ),
    "max healthcare institute limited": dict(
        website="https://www.maxhealthcare.in",
        linkedin="https://www.linkedin.com/company/max-healthcare",
        address="Max House, Okhla Phase III, New Delhi 110020, India",
        employees="10,001+ (hospital network)",
    ),
    "cipla limited": dict(
        website="https://www.cipla.com",
        linkedin="https://www.linkedin.com/company/cipla",
        address="Cipla House, Peninsula Business Park, Ganpatrao Kadam Marg, Lower Parel, Mumbai 400013, India",
        employees="22,000+ (global; verify entity vs group)",
    ),
}


def get_seed(entity_name: str, use_seed: bool) -> dict:
    if not use_seed:
        return {}
    return SEED.get(entity_name.lower(), {})


def apply_seed_to_urls(entity_name: str, seed: dict, website, linkedin, sources: set):
    if not website and seed.get("website"):
        website = seed["website"]
        sources.add("seed")
        log_seed_fallback(entity_name, "website")
    if not linkedin and seed.get("linkedin"):
        linkedin = seed["linkedin"]
        sources.add("seed")
        log_seed_fallback(entity_name, "linkedin")
    return website, linkedin


def apply_seed_to_address(entity_name: str, seed: dict, address, sources: set):
    if not address and seed.get("address"):
        log_seed_fallback(entity_name, "address")
        sources.add("seed")
        return seed["address"]
    return address


def apply_seed_to_employees(entity_name: str, seed: dict, employees, sources: set):
    if not employees and seed.get("employees"):
        log_seed_fallback(entity_name, "employees")
        sources.add("seed")
        return seed["employees"]
    return employees
