"""Curated reference data for the synthetic desk universe.

These are the fixed "vocabularies" the generator samples from. Keeping them here
(separate from the random generation) makes the world easy to read, tweak, and
extend without touching generation logic.
"""

# --- Credit ratings, ordered best -> worst -------------------------------------
# Index in this list = credit "notch". Lower index = higher quality.
RATINGS = [
    "AAA",
    "AA+", "AA", "AA-",
    "A+", "A", "A-",
    "BBB+", "BBB", "BBB-",   # <- BBB- is the lowest investment-grade rung
    "BB+", "BB", "BB-",
    "B+", "B", "B-",
]

# Everything at or above BBB- is Investment Grade (IG); below it is High Yield (HY).
IG_CUTOFF_INDEX = RATINGS.index("BBB-")


def rating_notch(rating: str) -> int:
    """Numeric notch for a rating (0 = AAA). Used for 'near rating' distance."""
    return RATINGS.index(rating)


def is_investment_grade(rating: str) -> bool:
    return rating_notch(rating) <= IG_CUTOFF_INDEX


# --- Sectors -------------------------------------------------------------------
SECTORS = [
    "Healthcare",
    "Technology",
    "Financials",
    "Energy",
    "Utilities",
    "Consumer",
    "Industrials",
    "Telecom",
    "Real Estate",
    "Materials",
]

# Plausible-but-fake issuer names per sector (deliberately not real companies).
ISSUERS = {
    "Healthcare":   ["Meridian Health", "Cascade Pharma", "Northstar Biotic", "Vantage Medical", "Alpine Care"],
    "Technology":   ["Helix Systems", "Quanta Micro", "Beacon Software", "Orbital Compute", "Lumen Data"],
    "Financials":   ["Sterling Capital", "Harbor Financial", "Keystone Bancorp", "Granite Trust", "Union Lending"],
    "Energy":       ["Cardinal Energy", "Delta Petroleum", "Summit Resources", "Ironwood Oil", "Pinnacle Gas"],
    "Utilities":    ["Evergreen Power", "Riverbend Utility", "Meadow Grid", "Sentinel Electric", "Coastal Water"],
    "Consumer":     ["Maple Retail", "Crestview Brands", "Harvest Foods", "Willow Consumer", "Anchor Goods"],
    "Industrials":  ["Titan Industrial", "Forge Manufacturing", "Redwood Machinery", "Atlas Components", "Vertex Steel"],
    "Telecom":      ["Signal Telecom", "Nova Networks", "Clearline Comm", "Zenith Wireless", "Meridian Fiber"],
    "Real Estate":  ["Cornerstone REIT", "Highgate Properties", "Beacon Realty", "Parkside Estates", "Summit REIT"],
    "Materials":    ["Granite Materials", "Copperline Mining", "Cobalt Chemicals", "Ridgeline Metals", "Quarry Corp"],
}

# --- Duration buckets ----------------------------------------------------------
# Maturity in years -> a coarse bucket used for "similar duration" matching.
DURATION_BUCKETS = [
    ("short", 0, 3),      # 0-3y
    ("medium", 3, 7),     # 3-7y
    ("long", 7, 15),      # 7-15y
    ("ultra-long", 15, 31),  # 15y+
]


def duration_bucket(maturity_years: float) -> str:
    for name, lo, hi in DURATION_BUCKETS:
        if lo <= maturity_years < hi:
            return name
    return "ultra-long"


# --- Clients -------------------------------------------------------------------
CLIENT_TYPES = ["Pension Fund", "Insurer", "Asset Manager", "Hedge Fund"]

# Client name pools by type (fake).
CLIENT_NAMES = {
    "Pension Fund":  ["Redwood Pension", "Ironclad Retirement", "State Teachers Fund",
                      "Harborview Pension", "Granite Public Retirement", "Meadowlark Pension"],
    "Insurer":       ["Sentinel Life", "Beacon Assurance", "Coastal Mutual",
                      "Everest Insurance", "Provident Life", "Cornerstone Assurance"],
    "Asset Manager": ["Bluepeak Asset Mgmt", "Meridian Investors", "Kestrel Capital Mgmt",
                      "Northwind Advisors", "Silverline Asset Mgmt", "Aldergate Investors"],
    "Hedge Fund":    ["Vireo Capital", "Blackford Partners", "Tesseract Fund",
                      "Riptide Macro", "Onyx Credit Partners", "Halcyon Capital"],
}

# Mandate tags a client can carry. The generator picks a coherent subset per client.
CREDIT_MANDATES = ["IG-credit", "high-yield", "crossover"]        # quality appetite
DURATION_MANDATES = ["short-duration", "core-duration", "long-duration"]  # rate appetite
# Sector tilts reuse SECTORS (a client may explicitly favour a couple of sectors).

# Typical behaviour by client type: how quality-sensitive and rate-sensitive they are.
# Used to make generated books *coherent* (a pension holds long IG; a HF holds junk).
CLIENT_TYPE_PROFILE = {
    "Pension Fund":  {"credit": ["IG-credit"],               "duration": ["long-duration", "core-duration"], "risk": "low"},
    "Insurer":       {"credit": ["IG-credit"],               "duration": ["long-duration"],                   "risk": "low"},
    "Asset Manager": {"credit": ["IG-credit", "crossover"],  "duration": ["core-duration", "short-duration"], "risk": "medium"},
    "Hedge Fund":    {"credit": ["high-yield", "crossover"], "duration": ["short-duration", "core-duration"], "risk": "high"},
}
