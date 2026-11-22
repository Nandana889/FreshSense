"""
Grounded produce knowledge used by the shopkeeper advisor.

Every number here is either (a) cited to a published postharvest source, or
(b) explicitly marked as an operational estimate. The agent is only allowed to
quote figures it obtained from these tables via tools -- it must never invent a
shelf-life number of its own. That is the whole point of putting them here.

Provenance
----------
OPTIMUM_STORAGE  -- University of Maine Cooperative Extension Bulletin #4135,
                    "Storage Conditions: Fruits and Vegetables", which reproduces
                    the USDA Agriculture Handbook 66 storage table.
                    https://extension.umaine.edu/publications/4135e/

MOLD_HANDLING    -- USDA-derived extension guidance on mold in produce, e.g.
                    UConn Extension "Handling Food with Mold" and NC State
                    Extension "Moldy Foods: Use or Pitch".
                    https://extension.uconn.edu/publication/handling-food-with-mold/
                    https://brunswick.ces.ncsu.edu/news/moldy-foods-use-or-pitch/

RETAIL_WINDOWS   -- OPERATIONAL ESTIMATES, not published figures. The USDA
                    numbers assume a cold chain (e.g. carrots at 0 C and
                    98-100% RH) that a produce shop does not have, so quoting
                    them to a shopkeeper would be badly misleading. These are
                    deliberately conservative working defaults and are labelled
                    as estimates everywhere they surface. Tune them against your
                    own stock records before relying on them commercially.
"""

# --- Moisture class -----------------------------------------------------------
# This drives the single most important safety branch in the whole advisor.
# Mould spreads readily through high-moisture tissue but not through dense
# low-moisture tissue, so "a bit spoiled" means opposite things for a carrot
# and for a tomato.

FIRM = "firm"  # dense / low moisture -- localised damage can be trimmed out
SOFT = "soft"  # high moisture -- spoilage is assumed to have penetrated

MOISTURE_CLASS = {
    "bellpepper": FIRM,
    "carrot": FIRM,
    "potato": FIRM,
    "cucumber": SOFT,
    "tomato": SOFT,
}

# Vegetables the classifier was trained on.
KNOWN_VEGETABLES = tuple(sorted(MOISTURE_CLASS))

DISPLAY_NAMES = {
    "bellpepper": "Bell pepper",
    "carrot": "Carrot",
    "cucumber": "Cucumber",
    "potato": "Potato",
    "tomato": "Tomato",
}


# --- Published optimum storage (cited) ---------------------------------------

OPTIMUM_STORAGE = {
    "carrot": {
        "temperature": "0 C (32 F)",
        "humidity": "98-100%",
        "storage_life": "7-9 months (mature carrots)",
    },
    "potato": {
        "temperature": "3-4 C (38-40 F)",
        "humidity": "90-95%",
        "storage_life": "5-10 months (late crop); 4-5 months (early crop)",
    },
    "bellpepper": {
        "temperature": "7-13 C (45-55 F)",
        "humidity": "90-95%",
        "storage_life": "2-3 weeks",
    },
    "cucumber": {
        "temperature": "10-13 C (50-55 F)",
        "humidity": "95%",
        "storage_life": "10-14 days",
    },
    "tomato": {
        "temperature": "13-21 C (55-70 F)",
        "humidity": "90-95%",
        "storage_life": "4-7 days (firm ripe); 1-3 weeks (mature green)",
    },
}

OPTIMUM_SOURCE = (
    "University of Maine Cooperative Extension Bulletin #4135, reproducing the "
    "USDA Agriculture Handbook 66 storage table"
)


# --- Retail selling windows (operational estimates) --------------------------
# Days of saleable life remaining for stock that is still classified Fresh.
# "ambient" = open shop shelf, no cooling. "refrigerated" = shop chiller.

RETAIL_WINDOWS = {
    "carrot": {"ambient": 5, "refrigerated": 21},
    "potato": {"ambient": 14, "refrigerated": 30},
    "bellpepper": {"ambient": 4, "refrigerated": 14},
    "cucumber": {"ambient": 3, "refrigerated": 10},
    "tomato": {"ambient": 3, "refrigerated": 7},
}

STORAGE_CONDITIONS = ("ambient", "refrigerated")

RETAIL_SOURCE = (
    "Operational estimate for shop conditions, not a published figure -- "
    "calibrate against your own stock records"
)


# --- How much life a spoilage stage removes ----------------------------------
# Fraction of the Fresh window that remains at each classifier stage.
# Mildly_Spoiled produce is already losing condition, so it gets a short
# clearance window rather than a normal one; Spoiled produce gets none.

STAGE_REMAINING_FRACTION = {
    "Fresh": 1.0,
    "Mildly_Spoiled": 0.35,
    "Spoiled": 0.0,
}


# --- Mould / spoilage handling rules (cited) ---------------------------------

MOLD_HANDLING = {
    FIRM: {
        "rule": (
            "Dense, low-moisture produce: mould does not spread easily through "
            "the tissue, so visibly affected produce can be salvaged by cutting "
            "at least 1 inch (2.5 cm) around and below the affected area. Keep "
            "the knife out of the mould itself so it does not contaminate the "
            "rest of the produce."
        ),
        "salvageable": True,
    },
    SOFT: {
        "rule": (
            "High-moisture produce: mould can grow deep into the flesh well "
            "beyond what is visible, so affected items should be discarded "
            "whole. Do not trim and sell them."
        ),
        "salvageable": False,
    },
}

MOLD_SOURCE = (
    "USDA-derived extension guidance on mould in produce (UConn Extension, "
    "'Handling Food with Mold'; NC State Extension, 'Moldy Foods: Use or Pitch')"
)


# --- Per-vegetable inspection prompts ----------------------------------------
# Things a camera looking at a whole vegetable cannot reliably judge, so the
# shopkeeper is asked to check them by hand.

INSPECTION_NOTES = {
    "potato": (
        "Check separately for green patches and sprouting. Green or sprouted "
        "potatoes should not be sold regardless of what the freshness model "
        "says -- greening indicates glycoalkaloid build-up, which the image "
        "model is not trained to detect."
    ),
    "tomato": (
        "Press gently. Softening, weeping or split skin means it should come "
        "off the shelf even at a Fresh classification."
    ),
    "cucumber": (
        "Check the stem end and any waxed surface for soft or sunken spots, "
        "which spread quickly in cucumbers."
    ),
    "carrot": (
        "Check for whitened surfaces and flexibility; limp carrots have lost "
        "water and will not hold on the shelf for the full window."
    ),
    "bellpepper": (
        "Check around the stem and the inner cavity, where rot usually starts "
        "before it is visible from outside."
    ),
}


# --- Generic fallbacks when the vegetable is not known ------------------------
# The classifier grades freshness but does not identify the vegetable, and the
# shopkeeper may not have picked one yet. These give an immediate, usable
# answer straight after Grad-CAM, deliberately set to the conservative end so
# that naming the vegetable can only ever extend the window, never shorten it.
#
# GENERIC_RETAIL_WINDOWS: the refrigerated figure is the published Virginia
# Cooperative Extension estimate that most fresh vegetables keep about 5 days
# in a refrigerator. The ambient figure is the lowest ambient window in
# RETAIL_WINDOWS above (tomato and cucumber, at 3 days), so it is no more
# generous than the weakest produce this model was trained on.

GENERIC_RETAIL_WINDOWS = {"ambient": 3, "refrigerated": 5}

GENERIC_SOURCE = (
    "Virginia Cooperative Extension FST-453, 'most fresh vegetables may be "
    "stored up to 5 days in the refrigerator', combined with the shortest "
    "ambient window in this project's own table -- a conservative default "
    "used only until the vegetable is identified"
)

# For partly spoiled produce of unknown type we cannot apply the dense-vs-watery
# rule, because that is exactly what depends on knowing the vegetable. Published
# guidance splits on how deep the damage goes rather than on the species, so the
# fallback asks the shopkeeper to make that call by hand.
GENERIC_PARTLY_SPOILED_RULE = (
    "Vegetable not identified, so the dense-versus-watery rule cannot be "
    "applied. Published guidance splits on how deep the damage runs: shallow "
    "surface damage on dense produce can be cut away, while internal damage, "
    "mould or any softening means the item is discarded. Damaged produce also "
    "spoils faster than sound produce, so whatever is kept must be sold the "
    "same day."
)

GENERIC_RULE_SOURCE = (
    "University of Wisconsin Extension, 'To Eat or Not to Eat? Less-than-"
    "Perfect Garden Produce' (superficial damage versus internal damage); "
    "Virginia Cooperative Extension FST-234 (bruised spots as pathogen entry "
    "points); Texas A&M AgriLife, 'when in doubt, throw it out'"
)

GENERIC_INSPECTION_NOTE = (
    "Pick the vegetable above for a firm answer. Until then, press the item "
    "gently and look at the stem end: softness, weeping, a sour smell or any "
    "mould means discard it rather than trim it."
)


def normalise_vegetable(name):
    """Map a loose user-supplied vegetable name onto a known key, or None."""
    if not name:
        return None

    cleaned = "".join(
        ch for ch in str(name).lower() if ch.isalnum()
    )

    if not cleaned:
        return None

    if cleaned in MOISTURE_CLASS:
        return cleaned

    # Accept common spellings and the dataset's folder wording.
    aliases = {
        "bellpeppers": "bellpepper",
        "capsicum": "bellpepper",
        "pepper": "bellpepper",
        "peppers": "bellpepper",
        "sweetpepper": "bellpepper",
        "carrots": "carrot",
        "cucumbers": "cucumber",
        "potatoes": "potato",
        "tomatoes": "tomato",
        "tomatos": "tomato",
    }

    return aliases.get(cleaned)
