from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL, VALID_TIERS

_client = Groq(api_key=GROQ_API_KEY)


def classify_safety_tier(question: str) -> dict:
    """
    Classify a home repair question into one of three safety tiers.

    TODO — Milestone 1:

    Before writing any code, complete specs/classifier-spec.md. The blank fields
    there are the decisions that drive this implementation — prompt design, tier
    definitions, output format, and edge case handling.

    Your implementation should:
      1. Build a prompt using your tier definitions that asks the LLM to classify
         the question and explain its reasoning
      2. Send a single chat completion request (no tools, no history)
      3. Parse the tier and reason out of the raw response text
      4. Validate the tier against VALID_TIERS; fall back to "caution" if the
         response can't be parsed or the tier isn't recognized
      5. Return {"tier": ..., "reason": ...}

    Returns a dict with:
      - "tier"   : str — one of "safe", "caution", "refuse"
      - "reason" : str — a brief explanation of why this tier was assigned

    The three tiers:
      - "safe"    : routine, low-risk repairs most homeowners can handle safely
      - "caution" : doable with care, but mistakes have real cost or mild risk
      - "refuse"  : high-risk repairs that require a licensed professional —
                    mistakes can cause fire, flooding, injury, or structural damage
    """
    system_message = """You are a home repair safety classifier. Your job is to assess whether a home repair question is safe for homeowners to attempt, requires caution, or should be refused with a referral to a licensed professional.

You will classify the question into one of three tiers:

**safe:** Routine maintenance and low-risk repairs that most homeowners can complete without specialized training or tools. Mistakes here are minor (cosmetic damage or easily fixed). Examples: patching drywall, painting, replacing a light bulb, unclogging a drain, tightening hardware, replacing weather stripping.

**caution:** Repairs where mistakes are costly or involve mild risk, but are doable for motivated homeowners with care. These repairs require some skill and attention to detail. Examples: replacing a faucet, resetting a GFCI outlet, replacing a toilet flapper, installing a ceiling fan, replacing an existing outlet.

**refuse:** Repairs where an amateur mistake can cause fire, flooding, structural failure, serious injury, or death—or where local code requires a licensed professional. Examples: electrical panel work, gas line repair, structural modifications, main water line work, load-bearing wall removal, moving a light switch (requires new wire).

Key distinction at the caution/refuse boundary: if the repair involves replacing something at the same location (like-for-like), it's caution; if it involves adding new circuits, running new wire, modifying structural elements, or touching gas lines, it's refuse.

Output your classification in this exact format: Tier: <safe|caution|refuse> | Reason: <one-sentence explanation>"""

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=256,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Classify this home repair question:\n\n{question}"},
        ],
    )

    raw_output = response.choices[0].message.content.strip()

    parts = raw_output.split(" | ")
    if len(parts) != 2:
        return {
            "tier": "caution",
            "reason": "Could not parse safety classification; defaulting to caution for safety.",
        }

    tier_part = parts[0].strip()
    reason_part = parts[1].strip()

    if not tier_part.startswith("Tier:"):
        return {
            "tier": "caution",
            "reason": "Could not parse safety classification; defaulting to caution for safety.",
        }

    tier = tier_part.split(":", 1)[1].strip()

    if tier not in VALID_TIERS:
        return {
            "tier": "caution",
            "reason": "Invalid tier returned; defaulting to caution for safety.",
        }

    if reason_part.startswith("Reason:"):
        reason = reason_part.split(":", 1)[1].strip()
    else:
        reason = reason_part

    return {
        "tier": tier,
        "reason": reason,
    }
