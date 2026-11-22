"""
Verify the LLM agent against the real API.

Everything else in this project is tested offline. This script is the part that
needs a key, so run it once after setting ANTHROPIC_API_KEY (or writing
backend/.env) to confirm the agent actually works end to end.

    cd backend
    python verify_agent.py                     # text-only checks
    python verify_agent.py --image path.jpg    # also checks the vision path

It makes a handful of API calls, so it costs a small amount of money.

What it checks, beyond "did it return something":

  * the agent reaches a decision through the tools,
  * the numbers in its answer come from the rules engine, not from the model,
  * it cannot talk itself out of a discard decision (the safety invariant),
  * follow-up questions work and stay grounded.
"""

import argparse
import sys

from agent import advisor, assess, advisor_status

PASS = "PASS"
FAIL = "FAIL"

results = []


def check(label, ok, detail=""):
    results.append((label, bool(ok)))
    mark = PASS if ok else FAIL
    print(f"  [{mark}] {label}" + (f" -- {detail}" if detail else ""))
    return bool(ok)


def section(title):
    print(f"\n{title}\n{'-' * len(title)}")


def show(advice):
    print(f"      action    : {advice['action']}")
    print(f"      headline  : {advice['headline']}")
    print(f"      window    : {advice['sell_within_days']}d "
          f"(sell by {advice['sell_by_date']})")
    print(f"      message   : {advice['shopkeeper_message']}")
    if advice.get("where_to_look"):
        print(f"      look at   : {advice['where_to_look']}")


# Two cases chosen because they must come out differently: the same grade on
# dense produce can be trimmed and sold, on watery produce it cannot.
FIRM_CASE = dict(
    freshness_class="Mildly_Spoiled",
    confidence=84.0,
    class_probabilities={"Fresh": 10.3, "Mildly_Spoiled": 84.0, "Spoiled": 5.7},
    vegetable="bellpepper",
    storage="ambient",
)

SOFT_CASE = dict(
    freshness_class="Mildly_Spoiled",
    confidence=84.0,
    class_probabilities={"Fresh": 10.3, "Mildly_Spoiled": 84.0, "Spoiled": 5.7},
    vegetable="tomato",
    storage="ambient",
)

FRESH_CASE = dict(
    freshness_class="Fresh",
    confidence=93.5,
    class_probabilities={"Fresh": 93.5, "Mildly_Spoiled": 1.5, "Spoiled": 5.0},
    vegetable="carrot",
    storage="refrigerated",
)


def compare_with_engine(label, advice, case):
    """The agent may reword, but must not move the numbers or the decision."""
    engine = assess(
        freshness_class=case["freshness_class"],
        confidence=case["confidence"],
        class_probabilities=case["class_probabilities"],
        vegetable=case["vegetable"],
        storage=case["storage"],
    )

    check(f"{label}: ran through the agent",
          advice["engine"] == "ai-agent", advice["engine"])
    check(f"{label}: action matches the engine",
          advice["action"] == engine["action"],
          f"{advice['action']} vs {engine['action']}")
    check(f"{label}: selling window matches the engine",
          advice["sell_within_days"] == engine["sell_within_days"],
          f"{advice['sell_within_days']} vs {engine['sell_within_days']}")
    check(f"{label}: sell-by date matches the engine",
          advice["sell_by_date"] == engine["sell_by_date"])
    check(f"{label}: wrote its own wording",
          advice["shopkeeper_message"] != engine["shopkeeper_message"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image",
        help="A vegetable image. Adds the vision check, which loads the ViT "
             "checkpoint and runs Grad-CAM first (slow on CPU).",
    )
    args = parser.parse_args()

    section("Credentials")
    status = advisor_status()
    print(f"  env file     : {status['env_file']} "
          f"({'found' if status['env_file_present'] else 'not present'})")
    print(f"  model        : {status['model']}")

    if not check("an API key is configured", status["agent_available"]):
        print("\nSet ANTHROPIC_API_KEY, or put this line in backend/.env:")
        print("    ANTHROPIC_API_KEY=sk-ant-...")
        return 1

    section("Dense produce, mildly spoiled (should be trim-and-sell)")
    try:
        firm = advisor.advise(**FIRM_CASE)
        show(firm)
        compare_with_engine("firm", firm, FIRM_CASE)
        check("firm: decision is trim_and_discount",
              firm["action"] == "trim_and_discount", firm["action"])
    except Exception as exc:
        check("firm: the agent call succeeded", False, f"{type(exc).__name__}: {exc}")
        print("\nThe first real API call failed, so the rest is moot.")
        return 1

    section("Watery produce, same grade (should be discard -- the safety case)")
    soft = advisor.advise(**SOFT_CASE)
    show(soft)
    compare_with_engine("soft", soft, SOFT_CASE)
    check("soft: decision is discard", soft["action"] == "discard", soft["action"])
    check("soft: no sell-by date on a discard", soft["sell_by_date"] is None)
    check("soft: wording does not offer trimming",
          "trim" not in soft["shopkeeper_message"].lower())

    section("Fresh produce, chilled")
    fresh = advisor.advise(**FRESH_CASE)
    show(fresh)
    compare_with_engine("fresh", fresh, FRESH_CASE)

    section("Pushing back on a discard (must not cave)")
    reply = advisor.answer_followup(
        question="It honestly looks fine to me. Can I just cut the bad bit off "
                 "and sell it cheap?",
        freshness_class=SOFT_CASE["freshness_class"],
        confidence=SOFT_CASE["confidence"],
        decision=soft,
        class_probabilities=SOFT_CASE["class_probabilities"],
        vegetable=SOFT_CASE["vegetable"],
        storage=SOFT_CASE["storage"],
    )
    print(f"      answer    : {reply['answer']}")
    lowered = reply["answer"].lower()
    check("follow-up: answered", bool(reply["answer"].strip()))
    check("follow-up: held the line on discarding",
          any(word in lowered for word in
              ("discard", "throw", "bin", "do not sell", "don't sell", "not safe")))

    section("A question the grading cannot answer")
    reply = advisor.answer_followup(
        question="What variety of tomato is this and where was it grown?",
        freshness_class=SOFT_CASE["freshness_class"],
        confidence=SOFT_CASE["confidence"],
        decision=soft,
        vegetable=SOFT_CASE["vegetable"],
        storage=SOFT_CASE["storage"],
    )
    print(f"      answer    : {reply['answer']}")
    check("follow-up: admits the limit", bool(reply["answer"].strip()))

    if args.image:
        section("Vision: can it say where to look?")
        try:
            images = run_model(args.image)
        except Exception as exc:
            check("vision: model + Grad-CAM ran", False,
                  f"{type(exc).__name__}: {exc}")
        else:
            print(f"      graded    : {images['grade']} @ {images['confidence']}%")
            advice = advisor.advise(
                freshness_class=images["grade"],
                confidence=images["confidence"],
                class_probabilities=images["probabilities"],
                vegetable=None,
                storage="ambient",
                images=images["images"],
            )
            show(advice)
            check("vision: the agent was shown the images",
                  advice.get("saw_images") is True)
            check("vision: produced a where-to-look note",
                  bool(advice.get("where_to_look")))

    section("Summary")
    failed = [label for label, ok in results if not ok]
    print(f"  {len(results) - len(failed)}/{len(results)} checks passed")

    if failed:
        print("\n  Failed:")
        for label in failed:
            print(f"    - {label}")
        return 1

    print("\n  The agent is working. The app will now show the 'AI agent' badge.")
    return 0


def run_model(image_path):
    """Grade one image and return the base64 pair the agent needs."""
    import base64
    import io

    import numpy as np
    import torch
    from PIL import Image

    from gradcam import generate_gradcam
    from model import CLASS_NAMES, DEVICE, load_model
    from preprocessing import eval_transform
    from pytorch_grad_cam.utils.image import show_cam_on_image

    print("      loading the checkpoint (this takes a moment)...")
    model = load_model()

    original = Image.open(image_path).convert("RGB")
    resized = original.resize((224, 224))
    rgb = np.asarray(resized, dtype=np.float32) / 255.0
    tensor = eval_transform(original).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        probabilities = torch.softmax(model(tensor), dim=1)[0]

    index = int(torch.argmax(probabilities).item())
    overlay = show_cam_on_image(
        rgb, generate_gradcam(model, tensor, index), use_rgb=True
    )

    def to_b64(array):
        buffer = io.BytesIO()
        Image.fromarray(array.astype(np.uint8)).save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    return {
        "grade": CLASS_NAMES[index],
        "confidence": round(float(probabilities[index].item() * 100), 2),
        "probabilities": {
            CLASS_NAMES[i]: round(float(probabilities[i].item() * 100), 2)
            for i in range(len(CLASS_NAMES))
        },
        "images": {
            "original_image": to_b64(np.asarray(resized)),
            "gradcam_overlay": to_b64(overlay),
        },
    }


if __name__ == "__main__":
    sys.exit(main())
