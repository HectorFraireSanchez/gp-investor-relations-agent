INVESTORS = [
    {
        "id": "INV-001",
        "name": "Redwood Family Office",
        "type": "Family Office",
    },
    {
        "id": "INV-002",
        "name": "Beacon University Endowment",
        "type": "Endowment",
    },
    {
        "id": "INV-003",
        "name": "Atlas Pension Fund",
        "type": "Pension Fund",
    },
]


POSITIONS = [
    {
        "investor_id": "INV-001",
        "fund": "Northstar Growth Fund II",
        "commitment": 5_000_000,
        "contributed": 3_750_000,
        "unfunded_commitment": 1_250_000,
    },
    {
        "investor_id": "INV-002",
        "fund": "Northstar Growth Fund II",
        "commitment": 8_000_000,
        "contributed": 6_500_000,
        "unfunded_commitment": 1_500_000,
    },
]


CAPITAL_CALLS = [
    {
        "id": "CC-019",
        "investor_id": "INV-001",
        "fund": "Northstar Growth Fund II",
        "amount": 250_000,
        "due_date": "2026-09-30",
        "status": "Outstanding",
    },
    {
        "id": "CC-020",
        "investor_id": "INV-002",
        "fund": "Northstar Growth Fund II",
        "amount": 400_000,
        "due_date": "2026-09-25",
        "status": "Paid",
    },
]


def find_investor(name: str) -> dict | None:
    """Find an investor whose name contains the supplied text."""
    normalized_name = name.lower()

    for investor in INVESTORS:
        if normalized_name in investor["name"].lower():
            return investor

    return None