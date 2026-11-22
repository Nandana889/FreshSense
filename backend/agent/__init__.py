"""Agentic shopkeeper-advice layer on top of the freshness classifier."""

from .decide import AssessmentError, assess
from .env import ENV_PATH, load_env
from .knowledge import KNOWN_VEGETABLES, STORAGE_CONDITIONS

# Pick up backend/.env before anything reads credentials, so dropping the key
# in that file is enough -- no shell variable needed.
load_env()

__all__ = [
    "AssessmentError",
    "assess",
    "ENV_PATH",
    "KNOWN_VEGETABLES",
    "STORAGE_CONDITIONS",
    "advisor_status",
    "ask_followup",
    "get_advice",
    "load_env",
]


def advisor_status():
    """Report which advisor backend a request would use right now."""
    from . import advisor

    available = advisor.credentials_available()

    return {
        "agent_available": available,
        "model": advisor.MODEL,
        "fallback": "rules",
        # The frontend hides the question box when this is false, because
        # free-form answers have no rules-based equivalent.
        "followup_available": available,
        "env_file": str(ENV_PATH),
        "env_file_present": ENV_PATH.is_file(),
    }


def get_advice(
    freshness_class,
    confidence,
    class_probabilities=None,
    vegetable=None,
    storage="ambient",
    images=None,
    use_agent=True,
):
    """
    Shopkeeper advice for one classified item.

    Tries the LLM agent first when `use_agent` is set and credentials are
    configured, and falls back to the deterministic rules engine otherwise so
    the endpoint always returns usable advice.
    """
    import logging

    from . import advisor

    logger = logging.getLogger(__name__)

    if use_agent:
        try:
            return advisor.advise(
                freshness_class=freshness_class,
                confidence=confidence,
                class_probabilities=class_probabilities,
                vegetable=vegetable,
                storage=storage,
                images=images,
            )
        except advisor.AgentUnavailable as exc:
            logger.info("Agent unavailable, using rules engine: %s", exc)
        except AssessmentError:
            # Bad caller input -- let the endpoint turn this into a 400.
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Agent failed unexpectedly, using rules engine: %s", exc
            )

    return assess(
        freshness_class=freshness_class,
        confidence=confidence,
        class_probabilities=class_probabilities,
        vegetable=vegetable,
        storage=storage,
    )


def ask_followup(
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
    Answer a follow-up question about advice already given.

    Raises `advisor.AgentUnavailable` when no credentials are configured --
    there is no rules-based way to answer an open question, so the caller
    should surface that rather than invent an answer.
    """
    from . import advisor

    return advisor.answer_followup(
        question=question,
        freshness_class=freshness_class,
        confidence=confidence,
        decision=decision,
        class_probabilities=class_probabilities,
        vegetable=vegetable,
        storage=storage,
        history=history,
    )
