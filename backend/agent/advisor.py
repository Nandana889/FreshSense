"""
Tool-using Claude agent that explains a freshness classification to a shopkeeper.

Division of responsibility
--------------------------
The agent does NOT do arithmetic and does NOT recall shelf-life facts. It is
given four tools; three of them read from the grounded tables in
`knowledge.py` via `decide.py`, and the fourth is how it hands back its answer.

    lookup_shelf_life       -> cited storage figures + the shop selling window
    lookup_safety_rule      -> the mould-handling rule for this vegetable
    compute_selling_window  -> the deterministic decision (action, days, date)
    submit_recommendation   -> the agent's plain-language wording

When the agent submits, the numeric fields (`action`, `sell_within_days`,
`sell_by_date`, `references`) are taken from `compute_selling_window`, and only
the wording is taken from the agent. So the worst a bad generation can do is
word the advice poorly -- it cannot invent a selling window or overturn a
discard decision.

If no credentials are configured, or the API call fails for any reason, the
caller falls back to `decide.assess()` and the app keeps working.
"""

import logging
import os

from . import decide
from .decide import AssessmentError
from .knowledge import KNOWN_VEGETABLES, STORAGE_CONDITIONS

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000
MAX_ITERATIONS = 8

# Opus 5.5 defaults to `medium` effort; set it explicitly so a future default
# change cannot silently alter behaviour. This is a short judgement task.
EFFORT = "medium"

# Server-side refusal fallback: if a safety classifier declines the request,
# the API retries on another model instead of returning an unusable response.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """\
You advise a vegetable shopkeeper. An image classifier has graded one item of \
their stock as Fresh, Mildly_Spoiled or Spoiled, and your job is to turn that \
grade into a clear instruction they can act on in the next few seconds.

You must work through the tools:

1. Call `lookup_shelf_life` and `lookup_safety_rule` to get the storage figures \
and the handling rule for this vegetable.
2. Call `compute_selling_window` to get the decision, the number of selling days \
and the sell-by date.
3. Call `submit_recommendation` exactly once to deliver your answer.

Rules you must follow:

- Never state a shelf life, a number of days or a date that did not come back \
from a tool. If you need a number, call a tool for it.
- Never contradict `compute_selling_window`. If it says discard, your wording \
says discard. You are explaining its decision, not reviewing it.
- The difference between dense produce (carrot, potato, bell pepper) and \
high-moisture produce (tomato, cucumber) matters more than anything else you \
will say. Dense produce that is mildly spoiled can be trimmed and sold. \
High-moisture produce that is mildly spoiled must be thrown away whole, because \
mould grows deeper than it looks. If the tools tell you this is the \
high-moisture case, say plainly that trimming it is not good enough.
- If the tools report low confidence or an ambiguous grade, tell the shopkeeper \
to check that item by hand and say why.

Write for someone standing at a market stall, not for an engineer. Short \
sentences. No jargon, no hedging, no mention of models, probabilities, \
classifiers or tools. Give the instruction first, then the reason. Where money \
is involved (discounting, clearing stock) say what to do with the price."""

# Appended to the system prompt only when images are supplied.
VISION_PROMPT = """

You have also been given two pictures of this item: the photograph, and a \
heatmap showing which parts of it the grading looked at most (red and yellow \
areas counted most, blue areas counted least).

Use them to tell the shopkeeper where on the item to look, in `where_to_look`. \
Say it in ordinary words - "the stem end", "the lower left side", "right across \
the middle". Never mention heatmaps, colours, models or attention.

Two limits on this:

- The grade is already decided. Do not re-grade the item from the pictures, and \
do not disagree with the grade even if the photograph looks better or worse to \
you. You are saying where to look, not what grade it is.
- If the heatmap is spread all over the item, or sits on the background rather \
than the produce, say that the picture does not point anywhere in particular \
and the shopkeeper should check the whole item. Do not invent a location."""


class AgentUnavailable(RuntimeError):
    """Raised when the Claude-backed advisor cannot be used at all."""


def credentials_available():
    """True when something the SDK can authenticate with is configured."""
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )


def _build_tools(state):
    """Create the agent's tools, bound to a per-request `state` dict."""
    try:
        from anthropic import beta_tool
    except ImportError as exc:  # pragma: no cover - import guard
        raise AgentUnavailable(
            "The `anthropic` package is not installed. "
            "Run: pip install anthropic"
        ) from exc

    @beta_tool
    def lookup_shelf_life(vegetable: str, storage: str = "ambient") -> str:
        """Look up published storage figures and the shop selling window.

        Args:
            vegetable: One of bellpepper, carrot, cucumber, potato, tomato.
            storage: Either "ambient" (open shelf) or "refrigerated" (chiller).
        """
        try:
            return _as_text(decide.lookup_shelf_life(vegetable, storage))
        except AssessmentError as exc:
            return _tool_error_text(exc)

    @beta_tool
    def lookup_safety_rule(vegetable: str, freshness_class: str) -> str:
        """Look up the mould-handling rule for this vegetable.

        Tells you whether partly spoiled produce of this type can be trimmed
        and sold, or has to be discarded whole.

        Args:
            vegetable: One of bellpepper, carrot, cucumber, potato, tomato.
            freshness_class: Fresh, Mildly_Spoiled or Spoiled.
        """
        try:
            return _as_text(
                decide.lookup_safety_rule(vegetable, freshness_class)
            )
        except AssessmentError as exc:
            return _tool_error_text(exc)

    @beta_tool
    def compute_selling_window(
        vegetable: str,
        freshness_class: str,
        confidence: float,
        storage: str = "ambient",
    ) -> str:
        """Compute the decision, the selling window and the sell-by date.

        This is the authoritative decision. Do not contradict it.

        Args:
            vegetable: One of bellpepper, carrot, cucumber, potato, tomato, or
                an empty string when the shopkeeper has not said which it is,
                which returns a cautious figure valid for any of them.
            freshness_class: Fresh, Mildly_Spoiled or Spoiled.
            confidence: The classifier's confidence as a percentage, 0-100.
            storage: Either "ambient" (open shelf) or "refrigerated" (chiller).
        """
        try:
            result = decide.assess(
                freshness_class=freshness_class,
                confidence=confidence,
                class_probabilities=state["class_probabilities"],
                vegetable=vegetable,
                storage=storage,
            )
        except AssessmentError as exc:
            return _tool_error_text(exc)

        # Keep the authoritative result so the numbers in the final answer come
        # from here rather than from the model.
        state["computed"] = result

        return _as_text(result)

    @beta_tool
    def submit_recommendation(
        headline: str,
        shopkeeper_message: str,
        reasoning: str,
        where_to_look: str = "",
    ) -> str:
        """Deliver the final advice to the shopkeeper. Call this exactly once.

        Args:
            headline: One short line, under about 60 characters, saying what to
                do (e.g. "Sell within 3 days" or "Discard - do not trim").
            shopkeeper_message: Two to four plain sentences telling the
                shopkeeper what to do and what to watch for.
            reasoning: Two or three sentences explaining why, in the same plain
                language.
            where_to_look: Only if you were shown the photo and the heatmap:
                one sentence saying which part of the item to check, in plain
                words such as "the stem end" or "the lower left side". Leave
                empty if you were not shown images.
        """
        state["submitted"] = {
            "headline": headline.strip(),
            "shopkeeper_message": shopkeeper_message.strip(),
            "reasoning": reasoning.strip(),
            "where_to_look": where_to_look.strip(),
        }

        return "Recommendation recorded. Stop here and do not call more tools."

    return [
        lookup_shelf_life,
        lookup_safety_rule,
        compute_selling_window,
        submit_recommendation,
    ]


def _as_text(payload):
    """Serialise a tool result, surfacing input errors to the model."""
    import json

    return json.dumps(payload, default=str)


def _tool_error_text(exc):
    import json

    return json.dumps({"error": str(exc)})


def _image_block(base64_png):
    """Wrap a base64 PNG string as an image content block."""
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64_png,
        },
    }


def _image_content(images):
    """
    Build the image blocks for a request, labelled so the model knows which
    picture is which. Returns [] when no usable images were supplied.
    """
    if not images:
        return []

    photo = images.get("original_image")
    heatmap = images.get("gradcam_overlay")

    if not photo or not heatmap:
        # Only the pair is useful: the heatmap alone has no context, and the
        # photo alone tells the model nothing about where the grade came from.
        return []

    return [
        {"type": "text", "text": "The photograph of the item:"},
        _image_block(photo),
        {"type": "text", "text": "The same item with the grading heatmap over it:"},
        _image_block(heatmap),
    ]


def advise(
    freshness_class,
    confidence,
    class_probabilities=None,
    vegetable=None,
    storage="ambient",
    images=None,
):
    """
    Produce shopkeeper advice using Claude, grounded in the rules engine.

    `images` may carry the base64 PNGs from /predict ("original_image" and
    "gradcam_overlay"); when both are present the agent is shown them and adds
    a `where_to_look` note.

    Raises AgentUnavailable if the agent cannot run; the caller should then use
    `decide.assess()` directly.
    """
    if not credentials_available():
        raise AgentUnavailable(
            "No Anthropic credentials found. Set ANTHROPIC_API_KEY to enable "
            "the agent; the rule-based advisor is used in the meantime."
        )

    try:
        import anthropic
    except ImportError as exc:
        raise AgentUnavailable(
            "The `anthropic` package is not installed. "
            "Run: pip install anthropic"
        ) from exc

    if storage not in STORAGE_CONDITIONS:
        raise AssessmentError(
            f"Unknown storage condition {storage!r}. "
            f"Use one of: {', '.join(STORAGE_CONDITIONS)}."
        )

    state = {
        "class_probabilities": class_probabilities or {},
        "computed": None,
        "submitted": None,
    }

    tools = _build_tools(state)
    client = anthropic.Anthropic()

    known = ", ".join(KNOWN_VEGETABLES)
    vegetable_line = (
        f"The shopkeeper says this is a {vegetable}."
        if vegetable
        else (
            "The shopkeeper has not said which vegetable this is. Call "
            "compute_selling_window with the vegetable left as an empty "
            "string: it will return a deliberately cautious general figure "
            "that applies to any of the produce this model covers. Give that "
            "advice, and tell them that naming the vegetable will sharpen it. "
            "Do not guess the vegetable from the picture."
        )
    )

    prompt = (
        f"A customer's stock item has been graded.\n\n"
        f"Grade: {freshness_class}\n"
        f"Confidence: {confidence:.1f}%\n"
        f"All class scores: {state['class_probabilities']}\n"
        f"Storage: {storage}\n"
        f"{vegetable_line}\n"
        f"Vegetables the shop stocks: {known}.\n\n"
        f"Work through the tools and submit your recommendation."
    )

    image_content = _image_content(images)
    system = SYSTEM_PROMPT + (VISION_PROMPT if image_content else "")

    request = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "tools": tools,
        "messages": [
            {
                "role": "user",
                "content": [*image_content, {"type": "text", "text": prompt}],
            }
        ],
        "output_config": {"effort": EFFORT},
        "max_iterations": MAX_ITERATIONS,
    }

    _run(client, request, allow_fallback_beta=True)

    computed = state["computed"]
    submitted = state["submitted"]

    if computed is None:
        # The agent never asked for the authoritative decision, so there is
        # nothing trustworthy to dress up.
        raise AgentUnavailable(
            "The agent did not call compute_selling_window; "
            "falling back to the rules engine."
        )

    if submitted is None:
        logger.warning(
            "Agent finished without calling submit_recommendation; "
            "returning the rules-engine wording."
        )
        return computed

    # Numbers and the decision come from the engine; wording from the agent.
    saw_images = bool(image_content)

    result = dict(computed)
    result.update(
        {
            "headline": submitted["headline"] or computed["headline"],
            "shopkeeper_message": (
                submitted["shopkeeper_message"] or computed["shopkeeper_message"]
            ),
            "reasoning": submitted["reasoning"] or computed["reasoning"],
            # Only trust a location note when the agent was actually shown the
            # pictures -- otherwise it would be describing a place it never saw.
            "where_to_look": (
                (submitted.get("where_to_look") or None) if saw_images else None
            ),
            "saw_images": saw_images,
            "engine": "claude-agent",
            "model": MODEL,
        }
    )

    return result


def _run(client, request, allow_fallback_beta):
    """Run the tool loop, retrying once without the refusal-fallback beta."""
    import anthropic

    attempt = dict(request)

    if allow_fallback_beta:
        attempt["betas"] = [FALLBACK_BETA]
        attempt["fallbacks"] = "default"

    try:
        runner = client.beta.messages.tool_runner(**attempt)
        final = runner.until_done()
    except (anthropic.BadRequestError, TypeError) as exc:
        if not allow_fallback_beta:
            raise AgentUnavailable(f"Claude request rejected: {exc}") from exc

        # The installed SDK or endpoint may predate the refusal-fallback beta.
        logger.warning(
            "Retrying without the refusal-fallback beta (%s): %s",
            FALLBACK_BETA,
            exc,
        )
        return _run(client, request, allow_fallback_beta=False)
    except anthropic.APIError as exc:
        raise AgentUnavailable(f"Claude API error: {exc}") from exc

    stop_reason = getattr(final, "stop_reason", None)

    if stop_reason == "refusal":
        raise AgentUnavailable(
            "Claude declined the request "
            f"({getattr(final, 'stop_details', None)})."
        )

    if stop_reason == "max_tokens":
        logger.warning("Agent response hit max_tokens.")

    return final


# --- Follow-up questions ------------------------------------------------------
# Unlike `advise()`, this has no rules-engine equivalent: answering an open
# question is exactly what the language model is for. The endpoint tells the
# shopkeeper plainly when it is unavailable rather than faking an answer.

MAX_HISTORY_TURNS = 12

FOLLOWUP_PROMPT = """\
You are answering a vegetable shopkeeper's follow-up questions about advice \
you already gave them on one item of stock.

The decision has already been made and shown to them. Your job is to answer \
what they ask about it.

- Use the tools whenever a storage figure, a selling window or a safety rule is \
involved. Never state a number or a date that did not come from a tool.
- Never overturn the decision they were given. If they push back ("it looks \
fine to me", "can I still sell it?"), explain the reason behind it rather than \
changing it. On a discard decision, do not help them sell the item.
- You cannot see the item unless pictures were provided, and you cannot re-grade \
it. If they ask something the grading cannot answer - the variety, where it was \
grown, how it will taste, whether a customer will complain - say so plainly.
- If a question falls outside produce handling altogether, say it is not \
something you can help with and leave it there.
- Keep answers to two or three sentences unless they ask for detail. Plain \
market-stall language. No jargon, no mention of models, tools or probabilities."""


def answer_followup(
    question,
    freshness_class,
    confidence,
    decision,
    class_probabilities=None,
    vegetable=None,
    storage="ambient",
    history=None,
):
    """
    Answer a shopkeeper's follow-up question about advice already given.

    `decision` is the advice dict previously returned, so the agent can see
    what the shopkeeper was told. `history` is a list of
    {"role": "user"|"assistant", "content": str} from earlier in this thread.

    Raises AgentUnavailable when the agent cannot run. There is no rules-based
    fallback for free-form questions.
    """
    if not credentials_available():
        raise AgentUnavailable(
            "Follow-up questions need an Anthropic API key. Set "
            "ANTHROPIC_API_KEY and restart the backend."
        )

    try:
        import anthropic
    except ImportError as exc:
        raise AgentUnavailable(
            "The `anthropic` package is not installed. "
            "Run: pip install anthropic"
        ) from exc

    question = (question or "").strip()
    if not question:
        raise AssessmentError("Ask a question first.")

    state = {
        "class_probabilities": class_probabilities or {},
        "computed": None,
        "submitted": None,
    }

    # The submit tool is for the initial recommendation only; a follow-up
    # answer is just the model's reply.
    tools = [
        tool
        for tool in _build_tools(state)
        if tool.to_dict()["name"] != "submit_recommendation"
    ]

    client = anthropic.Anthropic()

    briefing = (
        "Here is the item and the advice you already gave.\n\n"
        f"Vegetable: {vegetable or 'not stated'}\n"
        f"Grade: {freshness_class} ({confidence:.1f}% confidence)\n"
        f"Storage: {storage}\n"
        f"Decision given: {decision.get('action_label')}\n"
        f"Headline given: {decision.get('headline')}\n"
        f"Selling window given: {decision.get('sell_within_days')} day(s)"
        f", sell-by {decision.get('sell_by_date') or 'none'}\n"
        f"What they were told: {decision.get('shopkeeper_message')}"
    )

    messages = [
        {"role": "user", "content": briefing},
        {
            "role": "assistant",
            "content": "Understood. I'll answer their questions about it.",
        },
    ]

    for turn in (history or [])[-MAX_HISTORY_TURNS:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question})

    request = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": FOLLOWUP_PROMPT,
        "tools": tools,
        "messages": messages,
        "output_config": {"effort": EFFORT},
        "max_iterations": MAX_ITERATIONS,
    }

    final = _run(client, request, allow_fallback_beta=True)

    answer = "\n\n".join(
        block.text.strip()
        for block in getattr(final, "content", [])
        if getattr(block, "type", None) == "text" and block.text.strip()
    )

    if not answer:
        raise AgentUnavailable("The agent returned an empty answer.")

    return {"answer": answer, "engine": "claude-agent", "model": MODEL}
