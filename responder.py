import re
from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL

_client = Groq(api_key=GROQ_API_KEY)

# System prompts for each tier
_SAFE_PROMPT = """You are a helpful home repair advisor. The task the user is asking about is safe for a competent DIYer to attempt.

Provide clear, specific, step-by-step instructions. Your response should include:
- A complete list of tools and materials needed
- Step-by-step instructions, numbered, with enough detail that someone unfamiliar with the task can follow along
- Safety precautions relevant to this specific task
- Common mistakes to avoid
- When and how to tell if something has gone wrong
- Mention when to call a professional if the task reveals unexpected issues

Be thorough and helpful. The user is asking for guidance on a repair that is safe for a competent homeowner to attempt."""

_CAUTION_PROMPT = """You are providing guidance on a home repair that carries meaningful risk and typically requires professional expertise.

Lead your response with a clear, firm statement: "This repair is typically performed by licensed professionals. Attempting it yourself carries real safety, legal, and code compliance risks."

Then explain the specific risks:
- What could go wrong (water damage, electrical hazard, structural failure, code violations, voided warranty, etc.)
- Why professionals are trained for this (permits, inspection requirements, specialized tools, knowledge of local codes)
- What liability the homeowner takes on

Only if the user chooses to proceed after this clear warning, provide:
- What a licensed professional would assess and check
- What warning signs to watch for
- When to immediately stop and call someone

Always conclude with: "I strongly recommend hiring a licensed professional for this work. The risks and costs of mistakes often exceed the cost of professional help."

Do not assume the user will proceed. A firm, upfront recommendation is more responsible than step-by-step instructions."""

_REFUSE_PROMPT = """Do not provide instructions for this repair under any circumstances. This task must only be performed by a licensed professional due to serious safety risks.

Your response structure must be EXACTLY three sentences:

1. Statement: "I cannot provide instructions for this repair."
2. Risk explanation: State ONE specific danger in consequence-only language.
   (Example: "This work carries a risk of electrocution, fire, or code violations.")
3. Professional recommendation: Name the specific licensed professional needed.
   (Example: "Contact a licensed electrician.")

CRITICAL RULES - these overrule normal helpfulness:

- Use ONLY consequence-based language: "carries risk of fire" not "improper connections cause fire"
- NEVER use "if you...then" formulations — they embed task steps into danger explanation
- NEVER describe the process, workflow, sequence, or phases of the task
  (including indirectly as comparison: "unlike a simple fix, this involves...")
- NEVER provide diagnostic or inspection steps ("check if the breaker is on," "look for signs that...")
- NEVER list tools, materials, equipment, or safety gear (even protective gear)
- NEVER add "because" clauses explaining why a professional is needed
- NEVER reference external resources, standards, codes, or certification guides
- NEVER use pivoting language: no "although," "while," "however," "but," "that said," "even so"
- NEVER describe what a professional would do, or the professional's workflow
- NEVER add any sentence beyond the three required

Validation before responding: Check your draft against these three questions:
1. Does it contain exactly 3 sentences? If no, revise.
2. Does it avoid describing HOW the repair happens, even indirectly? If no, revise.
3. Could someone use this response to start attempting the repair? If yes, revise.

If validation passes, respond with only those three sentences. Stop."""

_UNKNOWN_TIER_RESPONSE = """I'm not yet able to assess the safety of this repair. To protect your safety, I recommend consulting with a licensed professional before attempting any home repair work. A professional can evaluate the scope, risks, and whether this is appropriate for a DIYer."""


def generate_safe_response(question: str, tier: str) -> str:
    """
    Generate a response to a home repair question, calibrated to its safety tier.

    TODO — Milestone 2:

    Before writing any code, complete specs/responder-spec.md. The most important
    fields are the three system prompts — one per tier. Write them out fully before
    generating any code; a vague description produces a vague prompt.

    `tier` is one of "safe", "caution", or "refuse" — returned by classify_safety_tier().

    Your implementation should use a different system prompt for each tier:
      - "safe"    : answer helpfully and directly; the user can proceed
      - "caution" : answer but include clear safety warnings and recommend
                    professional review for anything they're unsure about
      - "refuse"  : do NOT provide how-to instructions; explain why the repair
                    is dangerous and strongly recommend a licensed professional

    The refuse case is the hardest to get right. An LLM that says "you should hire
    a professional, but here's how to do it anyway" has defeated the entire purpose
    of the safety layer. Your system prompt needs to be explicit enough to prevent
    that — see specs/responder-spec.md for the design decision field on grounding.

    If tier is unrecognized (e.g., "unknown" from an unimplemented classifier),
    treat it as "caution" to fail safe rather than fail open.

    Return the response as a plain string.
    """
    # Map tier to system prompt
    system_prompts = {
        "safe": _SAFE_PROMPT,
        "caution": _CAUTION_PROMPT,
        "refuse": _REFUSE_PROMPT,
    }

    # For unknown tier, return the unknown tier response
    if tier not in system_prompts:
        return _UNKNOWN_TIER_RESPONSE

    system_prompt = system_prompts[tier]

    # Call the Groq API
    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
    )

    text = response.choices[0].message.content

    # For refuse tier, validate the response before returning
    if tier == "refuse":
        text = _validate_refuse_response(text)

    return text


def _validate_refuse_response(response: str) -> str:
    """
    Validate that a refuse-tier response follows the grounding rules.
    If it violates any rules, return a safe fallback message.
    """
    # Check 1: Count sentences (must be exactly 3)
    sentences = [s.strip() for s in response.split(".") if s.strip()]
    if len(sentences) != 3:
        return _get_refuse_fallback()

    # Check 2: Scan for embedding task steps in consequence language
    forbidden_patterns = [
        r"\bif you\b.*\bthen\b",  # if you...then patterns
        r"\bwhen you\b",  # when you do X
        r"\bif you don[\'t]{0,1}\b",  # if you don't
        r"\bby doing\b",  # by doing
        r"\b(first|then|next|before|after)\b",  # sequencing words
        r"\bunlike\b",  # unlike framing
    ]

    for pattern in forbidden_patterns:
        if re.search(pattern, response, re.IGNORECASE):
            return _get_refuse_fallback()

    # Check 3: Scan for preparatory/diagnostic language
    diagnostic_terms = ["check", "look for", "inspect", "assess", "observe", "test"]
    for term in diagnostic_terms:
        if re.search(rf"\b{term}\b", response, re.IGNORECASE):
            return _get_refuse_fallback()

    # Check 4: Scan for tool/material/equipment listing
    equipment_phrases = ["you'll need", "required equipment", "safety gear", "tools"]
    for phrase in equipment_phrases:
        if phrase.lower() in response.lower():
            return _get_refuse_fallback()

    # Check 5: Scan for professional description (because clauses after professional)
    if re.search(r"licensed \w+ because", response, re.IGNORECASE):
        return _get_refuse_fallback()

    # Check 6: Scan for pivoting words
    pivoting_words = ["although", "while", "however", "but", "that said", "even so", "yet", "still"]
    for word in pivoting_words:
        if re.search(rf"\b{word}\b", response, re.IGNORECASE):
            return _get_refuse_fallback()

    # All checks passed
    return response


def _get_refuse_fallback() -> str:
    """
    Return a safe fallback message when refuse-tier response validation fails.
    """
    return "I cannot provide instructions for this repair. This work carries serious safety risks and requires a licensed professional. Please contact the appropriate licensed professional."
