"""
Deterministic decision engine behind the shopkeeper advisor.

This module owns all of the arithmetic and all of the safety branching. The
Claude agent calls into it through tools rather than reasoning about numbers
itself, which means:

  * shelf-life figures and safety rules are always traceable to `knowledge.py`,
  * the advice is reproducible for the same inputs, and
  * the app still gives correct, if blunter, advice when no API key is
    configured and the language model is unavailable.

`assess()` is the single entry point. `agent.py` wraps it with Claude for the
explanation; `app.py` falls back to it directly.
"""

from datetime import date, timedelta

from .knowledge import (
    DISPLAY_NAMES,
    GENERIC_INSPECTION_NOTE,
    GENERIC_PARTLY_SPOILED_RULE,
    GENERIC_RETAIL_WINDOWS,
    GENERIC_RULE_SOURCE,
    GENERIC_SOURCE,
    INSPECTION_NOTES,
    KNOWN_VEGETABLES,
    MOISTURE_CLASS,
    MOLD_HANDLING,
    MOLD_SOURCE,
    OPTIMUM_SOURCE,
    OPTIMUM_STORAGE,
    RETAIL_SOURCE,
    RETAIL_WINDOWS,
    STAGE_REMAINING_FRACTION,
    STORAGE_CONDITIONS,
    normalise_vegetable,
)

# Below this top-class probability the classifier is not trusted to drive a
# sell-or-discard decision on its own.
CONFIDENCE_FLOOR = 65.0

# If the top two classes are this close, the image sits on a class boundary
# (typically Fresh vs Mildly_Spoiled) and a human should look at it.
AMBIGUITY_MARGIN = 15.0

# Action codes the frontend can switch on.
SELL_NORMALLY = "sell_normally"
PRIORITISE_SALE = "prioritise_sale"
TRIM_AND_DISCOUNT = "trim_and_discount"
DISCARD = "discard"
NEEDS_HUMAN_CHECK = "needs_human_check"
NEEDS_VEGETABLE_TYPE = "needs_vegetable_type"
CHECK_THEN_TRIM_OR_DISCARD = "check_then_trim_or_discard"

ACTION_LABELS = {
    SELL_NORMALLY: "Sell as normal stock",
    PRIORITISE_SALE: "Sell quickly - move to the front",
    TRIM_AND_DISCOUNT: "Trim the affected part, then sell at a discount",
    DISCARD: "Do not sell - discard",
    NEEDS_HUMAN_CHECK: "Check by hand before deciding",
    NEEDS_VEGETABLE_TYPE: "Tell me which vegetable this is",
    CHECK_THEN_TRIM_OR_DISCARD: "Check how deep the damage goes, then decide",
}


class AssessmentError(ValueError):
    """Raised when the caller supplies inputs the engine cannot act on."""


def _confidence_flags(class_probabilities, confidence):
    """Return (low_confidence, ambiguous, runner_up_name)."""
    ordered = sorted(
        class_probabilities.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    runner_up = ordered[1] if len(ordered) > 1 else None

    low_confidence = confidence < CONFIDENCE_FLOOR
    ambiguous = bool(
        runner_up and (confidence - runner_up[1]) < AMBIGUITY_MARGIN
    )

    return low_confidence, ambiguous, (runner_up[0] if runner_up else None)


def lookup_shelf_life(vegetable, storage="ambient"):
    """Grounded shelf-life reference for one vegetable. Exposed as a tool."""
    key = normalise_vegetable(vegetable)

    if key is None:
        raise AssessmentError(
            f"Unknown vegetable {vegetable!r}. "
            f"Known vegetables: {', '.join(KNOWN_VEGETABLES)}."
        )

    if storage not in STORAGE_CONDITIONS:
        raise AssessmentError(
            f"Unknown storage condition {storage!r}. "
            f"Use one of: {', '.join(STORAGE_CONDITIONS)}."
        )

    return {
        "vegetable": key,
        "display_name": DISPLAY_NAMES[key],
        "storage": storage,
        "moisture_class": MOISTURE_CLASS[key],
        "fresh_window_days": RETAIL_WINDOWS[key][storage],
        "fresh_window_basis": RETAIL_SOURCE,
        "published_optimum": OPTIMUM_STORAGE[key],
        "published_optimum_source": OPTIMUM_SOURCE,
        "inspection_note": INSPECTION_NOTES[key],
    }


def lookup_safety_rule(vegetable, freshness_class):
    """Grounded mould-handling rule for one vegetable. Exposed as a tool."""
    key = normalise_vegetable(vegetable)

    if key is None:
        raise AssessmentError(
            f"Unknown vegetable {vegetable!r}. "
            f"Known vegetables: {', '.join(KNOWN_VEGETABLES)}."
        )

    if freshness_class not in STAGE_REMAINING_FRACTION:
        raise AssessmentError(
            f"Unknown freshness class {freshness_class!r}. "
            f"Use one of: {', '.join(STAGE_REMAINING_FRACTION)}."
        )

    moisture_class = MOISTURE_CLASS[key]
    handling = MOLD_HANDLING[moisture_class]

    return {
        "vegetable": key,
        "display_name": DISPLAY_NAMES[key],
        "freshness_class": freshness_class,
        "moisture_class": moisture_class,
        "salvageable_when_partly_spoiled": handling["salvageable"],
        "rule": handling["rule"],
        "source": MOLD_SOURCE,
        "applies": freshness_class != "Fresh",
    }


def _window_days(vegetable, freshness_class, storage):
    """Saleable days remaining, rounded down, floored at 0."""
    fresh_days = RETAIL_WINDOWS[vegetable][storage]
    fraction = STAGE_REMAINING_FRACTION[freshness_class]

    return max(0, int(fresh_days * fraction))


def assess(
    freshness_class,
    confidence,
    class_probabilities=None,
    vegetable=None,
    storage="ambient",
    today=None,
):
    """
    Turn a classifier result into a shopkeeper decision.

    Returns a dict with a stable shape; see `ADVICE_FIELDS` in app.py for the
    contract the frontend relies on.
    """
    if freshness_class not in STAGE_REMAINING_FRACTION:
        raise AssessmentError(
            f"Unknown freshness class {freshness_class!r}. "
            f"Use one of: {', '.join(STAGE_REMAINING_FRACTION)}."
        )

    if storage not in STORAGE_CONDITIONS:
        raise AssessmentError(
            f"Unknown storage condition {storage!r}. "
            f"Use one of: {', '.join(STORAGE_CONDITIONS)}."
        )

    confidence = float(confidence)
    probabilities = class_probabilities or {freshness_class: confidence}
    today = today or date.today()

    low_confidence, ambiguous, runner_up = _confidence_flags(
        probabilities, confidence
    )

    key = normalise_vegetable(vegetable)

    cautions = []
    if low_confidence:
        cautions.append(
            f"The model is only {confidence:.0f}% confident, below the "
            f"{CONFIDENCE_FLOOR:.0f}% threshold needed to act on it alone."
        )
    if ambiguous and runner_up:
        cautions.append(
            f"'{freshness_class}' and '{runner_up}' scored close together, so "
            "this item sits on the boundary between two grades."
        )

    # --- Vegetable not identified: answer generically ------------------------
    # The classifier grades freshness but does not identify the vegetable, and
    # the trim-vs-discard rule for partly spoiled stock depends on whether the
    # flesh is dense or watery. Rather than refuse to answer, fall back to
    # deliberately conservative generic figures so there is always an action on
    # screen straight after Grad-CAM, and keep asking for the vegetable so the
    # answer can be sharpened. Naming the vegetable can only extend a window,
    # never shorten one.
    if key is None:
        generic_fresh_days = GENERIC_RETAIL_WINDOWS[storage]
        generic_days = max(
            0,
            int(generic_fresh_days * STAGE_REMAINING_FRACTION[freshness_class]),
        )

        generic_references = [
            {
                "claim": (
                    f"Generic selling window for unidentified produce "
                    f"({storage}): {generic_fresh_days} day(s) when fresh"
                ),
                "source": GENERIC_SOURCE,
            }
        ]

        if freshness_class == "Spoiled":
            # This one needs no species knowledge at all.
            generic_action = DISCARD
            generic_headline = "Do not sell this item"
            generic_reasoning = (
                f"The model graded this item as Spoiled at {confidence:.0f}% "
                "confidence. Spoiled produce has no saleable life left whatever "
                "the vegetable, so this decision does not depend on knowing "
                "which one it is."
            )
            generic_message = (
                "Take this item off the shelf and throw it away. Check the rest "
                "of the crate too, because spoilage spreads to whatever is "
                "touching it."
            )
            generic_references.append(
                {"claim": GENERIC_PARTLY_SPOILED_RULE, "source": GENERIC_RULE_SOURCE}
            )

        elif freshness_class == "Mildly_Spoiled":
            generic_action = CHECK_THEN_TRIM_OR_DISCARD
            generic_headline = "Check the damage, then trim or throw away"
            generic_reasoning = (
                "This item is partly spoiled. Whether it can be trimmed and "
                "sold depends on the vegetable: dense produce such as carrot, "
                "potato or bell pepper can be cut well clear of the damage, "
                "while watery produce such as tomato or cucumber has to be "
                "thrown away whole because mould grows deeper than it looks. "
                "Until the vegetable is named, published guidance splits on how "
                "deep the damage runs instead."
            )
            generic_message = (
                "Look at the item before you decide. If it is a firm, dry "
                "vegetable and the damage is only on the surface, cut at least "
                "1 inch (2.5 cm) around and below it and sell the rest today at "
                "a discount. If it is soft or watery, or the damage goes inside, "
                "or there is any mould or smell, throw the whole item away. Pick "
                "the vegetable above and I will give you a firm answer."
            )
            generic_references.append(
                {"claim": GENERIC_PARTLY_SPOILED_RULE, "source": GENERIC_RULE_SOURCE}
            )

        else:
            generic_action = (
                SELL_NORMALLY if generic_days > 2 else PRIORITISE_SALE
            )
            generic_headline = f"Sell within {generic_days} day(s)"
            generic_reasoning = (
                f"The model graded this item as Fresh at {confidence:.0f}% "
                f"confidence. Without knowing the vegetable this uses a "
                f"cautious general figure of {generic_days} day(s) in {storage} "
                "storage, set to the shortest-lived produce this model covers."
            )
            generic_message = (
                f"This is good stock. Sell it within {generic_days} day(s) in "
                f"{storage} storage. Pick the vegetable above for an exact "
                "window - most keep longer than this general figure."
            )

        generic_cautions = list(cautions)
        generic_cautions.append(
            "No vegetable selected, so this is a cautious general figure rather "
            "than a window for this particular produce."
        )

        # Low confidence downgrades a sale, but never softens a discard.
        if (low_confidence or ambiguous) and generic_action != DISCARD:
            generic_cautions.append(
                "Confirm this one by hand before shelving it; the grading is "
                "not certain enough to act on by itself."
            )
            generic_action = NEEDS_HUMAN_CHECK
            generic_headline = "Check this item by hand first"
            generic_message = (
                "Do not shelve this on the grading alone. Look it over by hand "
                "first, then treat it as a " + str(generic_days) + " day(s) "
                f"item in {storage} storage if it checks out, or discard it if "
                "you find soft spots, mould or damage."
            )

        generic_sell_by = (
            (today + timedelta(days=generic_days)).isoformat()
            if generic_action != DISCARD and generic_days > 0
            else None
        )

        return {
            "action": generic_action,
            "action_label": ACTION_LABELS[generic_action],
            "vegetable": None,
            "display_name": None,
            "storage": storage,
            "freshness_class": freshness_class,
            "confidence": round(confidence, 2),
            "sell_within_days": (
                generic_days if generic_action != DISCARD else 0
            ),
            "sell_by_date": generic_sell_by,
            "headline": generic_headline,
            "reasoning": generic_reasoning,
            "shopkeeper_message": generic_message,
            "cautions": generic_cautions,
            "safety_rule": (
                GENERIC_PARTLY_SPOILED_RULE
                if freshness_class != "Fresh"
                else None
            ),
            "inspection_note": GENERIC_INSPECTION_NOTE,
            "references": generic_references,
            # The frontend keeps the vegetable selector highlighted on this.
            "needs_input": "vegetable_type",
            "known_vegetables": list(KNOWN_VEGETABLES),
            "engine": "rules",
        }

    shelf = lookup_shelf_life(key, storage)
    safety = lookup_safety_rule(key, freshness_class)
    display = DISPLAY_NAMES[key]
    is_salvageable = safety["salvageable_when_partly_spoiled"]

    days = _window_days(key, freshness_class, storage)

    references = [
        {
            "claim": (
                f"Published optimum storage for {display.lower()}: "
                f"{shelf['published_optimum']['storage_life']} at "
                f"{shelf['published_optimum']['temperature']}, "
                f"{shelf['published_optimum']['humidity']} RH"
            ),
            "source": OPTIMUM_SOURCE,
        },
        {
            "claim": f"Selling window for shop conditions ({storage})",
            "source": RETAIL_SOURCE,
        },
    ]

    if freshness_class != "Fresh":
        references.append({"claim": safety["rule"], "source": MOLD_SOURCE})

    # --- Spoiled: no sale, whatever the vegetable ---------------------------
    if freshness_class == "Spoiled":
        action = DISCARD
        headline = f"Do not sell this {display.lower()}"
        reasoning = (
            f"The model graded this {display.lower()} as Spoiled at "
            f"{confidence:.0f}% confidence. Spoiled produce has no saleable "
            "life left, so there is no selling window to give."
        )
        message = (
            f"Remove this {display.lower()} from the shelf and discard it. "
            "Check the rest of the crate as well, because spoilage spreads to "
            "the produce touching it."
        )

    # --- Mildly spoiled: the branch that actually matters -------------------
    elif freshness_class == "Mildly_Spoiled":
        if is_salvageable:
            action = TRIM_AND_DISCOUNT
            headline = f"Trim it, then sell within {days} day(s)"
            reasoning = (
                f"This {display.lower()} is mildly spoiled, and "
                f"{display.lower()} is dense, low-moisture produce, so mould "
                "does not travel far through the flesh. Published guidance "
                "allows cutting well clear of the damage and selling the rest. "
                f"Allowing for the condition it is already in, about {days} "
                f"day(s) of selling life remain in {storage} storage."
            )
            message = (
                f"Cut at least 1 inch (2.5 cm) around and below the spoiled "
                f"part of this {display.lower()}, keeping the knife out of the "
                f"mould itself. Sell the trimmed stock at a discount within "
                f"{days} day(s). If the damage runs deep or covers much of the "
                "item, discard it instead."
            )
        else:
            action = DISCARD
            headline = f"Discard this {display.lower()} - do not trim and sell"
            reasoning = (
                f"This {display.lower()} is mildly spoiled, and "
                f"{display.lower()} is high-moisture produce. Mould grows deep "
                "into watery flesh well past the part you can see, so published "
                "guidance says to discard the whole item rather than cut the "
                "bad part away. The visible damage being small does not make it "
                "safe to sell."
            )
            message = (
                f"Throw this {display.lower()} away whole. Do not cut off the "
                "spoiled part and sell the rest - in watery produce the spoilage "
                "reaches further in than it looks. Check the items stored next "
                "to it too."
            )

    # --- Fresh ---------------------------------------------------------------
    else:
        action = SELL_NORMALLY if days > 2 else PRIORITISE_SALE
        headline = f"Sell within {days} day(s)"
        reasoning = (
            f"The model graded this {display.lower()} as Fresh at "
            f"{confidence:.0f}% confidence. In {storage} storage a fresh "
            f"{display.lower()} holds its condition for roughly {days} day(s) "
            "in shop conditions."
        )
        message = (
            f"This {display.lower()} is good stock. Sell it within {days} "
            f"day(s) in {storage} storage."
        )

        if storage == "ambient":
            chilled = RETAIL_WINDOWS[key]["refrigerated"]
            if chilled > days:
                message += (
                    f" Moving it to the chiller would extend that to about "
                    f"{chilled} day(s)."
                )

    # Low confidence never overrides a discard -- it only downgrades a decision
    # that would have put produce on the shelf.
    if (low_confidence or ambiguous) and action != DISCARD:
        cautions.append(
            "Confirm this one by hand before shelving it; the grading is not "
            "certain enough to act on by itself."
        )
        action = NEEDS_HUMAN_CHECK
        headline = f"Check this {display.lower()} by hand first"
        # The message is the line the shopkeeper actually reads, so it has to
        # carry the downgrade too -- otherwise the headline says "check this"
        # while the body still says "good stock, sell within N days".
        message = (
            f"Do not shelve this {display.lower()} on the grading alone. "
            f"Look it over by hand first, then treat it as a "
            f"{days} day(s) item in {storage} storage if it checks out, or "
            "discard it if you find soft spots, mould or damage."
        )

    sell_by = (
        (today + timedelta(days=days)).isoformat()
        if action not in (DISCARD,) and days > 0
        else None
    )

    return {
        "action": action,
        "action_label": ACTION_LABELS[action],
        "vegetable": key,
        "display_name": display,
        "storage": storage,
        "freshness_class": freshness_class,
        "confidence": round(confidence, 2),
        "sell_within_days": days if action != DISCARD else 0,
        "sell_by_date": sell_by,
        "headline": headline,
        "reasoning": reasoning,
        "shopkeeper_message": message,
        "cautions": cautions,
        "safety_rule": safety["rule"] if freshness_class != "Fresh" else None,
        "inspection_note": shelf["inspection_note"],
        "references": references,
        "needs_input": None,
        "known_vegetables": list(KNOWN_VEGETABLES),
        "engine": "rules",
    }
