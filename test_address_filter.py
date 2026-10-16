from scraper import address_from_html

test_cases = {
    "SIM card text": """
        <html><body>
        <p>Address: and pay a delivery charge of ₹100 for the
        vendor to ship the SIM card to the cardholder's address.</p>
        </body></html>
    """,

    "Navigation text": """
        <html><body>Find Doctor By Disease/Condition</body></html>
    """,

    "Customer review": """
        <html><body>
        <p>Address: I was sent a link to do the correction online,
        which made my work very easy.</p>
        </body></html>
    """,

    "Plausible corporate address": """
        <html><body>
        <p>Headquarters: ICICI Lombard House, 414, Veer Savarkar
        Marg, Prabhadevi, Mumbai 400025, India</p>
        </body></html>
    """,
}

for name, html in test_cases.items():
    print(f"{name}: {address_from_html(html)}")

