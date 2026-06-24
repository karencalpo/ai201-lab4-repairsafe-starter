# Spec: `classify_safety_tier()`

**File:** `safety.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Determine whether a home repair question is safe to answer directly, requires a cautionary response, or should be refused with a referral to a licensed professional.

---

## Input / Output Contract

**Input:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `question` | `str` | The user's home repair question |

**Output:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `"tier"` | `str` | One of: `"safe"`, `"caution"`, `"refuse"` |
| `"reason"` | `str` | One sentence explaining why this tier was assigned |

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Tier definitions

*Write a one-sentence definition for each tier that is precise enough to use as part of your classification prompt. Vague definitions produce inconsistent classifications.*

**safe:**
```
Questions about repairs that are low-risk, require no special licensing, and are commonly done by homeowners without risk of serious injury or code violations (e.g., painting, caulking, replacing fixtures, unclogging drains, basic maintenance).
```

**caution:**
```
Questions about repairs where homeowner DIY is legal and common, but mistakes could cause property damage, water damage, or safety concerns that aren't immediately life-threatening, or work that may require permits in some jurisdictions (e.g., installing drywall, basic plumbing repairs, simple electrical fixture installation, appliance repairs).
```

**refuse:**
```
Questions about repairs that are legally required to be done by licensed professionals, involve codes and safety systems critical to life/property safety, or carry high-risk consequences if done incorrectly (e.g., electrical panel work, gas lines, structural work, HVAC systems, foundation issues, chimney/roof work, or any question explicitly stating it's dangerous or requires a pro).
```

---

### Classification approach

**Approach: Tier definitions + few-shot examples (no step-by-step reasoning)**

I'll provide the LLM with the tier definitions plus 5–6 carefully chosen examples that cover the most consequential edge cases: the replace/add distinction (the hardest boundary to get right), examples that sound safer than they are, and a gas example (always refuse). This avoids token overhead of reasoning while anchoring the LLM to documented tier distinctions.

**Handling ambiguous questions:** When a question is ambiguous (e.g., "can I replace my outlets?" without context), the few-shot examples naturally guide the LLM toward a safe default. For example, if the examples show "replace outlet (existing)" → caution and "add outlet (new)" → refuse, the LLM will pattern-match to "replace" when genuinely uncertain, defaulting toward caution rather than guessing.

**Why this approach over alternatives:**
- **Definitions only** would force the LLM to infer the replace/add distinction from a one-sentence definition — this produces inconsistent results on edge cases.
- **Step-by-step reasoning** adds 100+ tokens per request with unclear benefit when the boundaries are well-documented (as they are in the Tier Guide).
- **Few-shot examples** are the sweet spot: they anchor the boundary, have lower token cost than reasoning, and are maintainable (add one more example if a misclassification is found).

---

### Output format

**Format: `Tier: <tier_name> | Reason: <reason_string>`**

Example outputs:
```
Tier: safe | Reason: Unclogging a drain with a plunger is routine maintenance with minimal risk.
Tier: caution | Reason: Replacing an existing outlet is doable by homeowners but requires turning off power and testing.
Tier: refuse | Reason: Moving a light switch requires running new wire through walls and may violate electrical code without a permit.
```

**Parsing strategy:**
- Split on " | " to get tier and reason sections.
- Extract the tier value (the word after the colon) and validate it against `VALID_TIERS`.
- Treat the reason as-is (it's for logging and user feedback, not parsed further).

**Why this format:** Pipe-separated key-value pairs are unambiguous and resist variation better than prose. The LLM is far less likely to invent a different separator than to invent a different word order in freeform prose.

---

### Prompt structure

**System message:**
```
You are a home repair safety classifier. Your job is to assess whether a home repair question is safe for homeowners to attempt, requires caution, or should be refused with a referral to a licensed professional.

You will classify the question into one of three tiers:

**safe:** Routine maintenance and low-risk repairs that most homeowners can complete without specialized training or tools. Mistakes here are minor (cosmetic damage or easily fixed). Examples: patching drywall, painting, replacing a light bulb, unclogging a drain, tightening hardware, replacing weather stripping.

**caution:** Repairs where mistakes are costly or involve mild risk, but are doable for motivated homeowners with care. These repairs require some skill and attention to detail. Examples: replacing a faucet, resetting a GFCI outlet, replacing a toilet flapper, installing a ceiling fan, replacing an existing outlet.

**refuse:** Repairs where an amateur mistake can cause fire, flooding, structural failure, serious injury, or death—or where local code requires a licensed professional. Examples: electrical panel work, gas line repair, structural modifications, main water line work, load-bearing wall removal, moving a light switch (requires new wire).

Key distinction at the caution/refuse boundary: if the repair involves replacing something at the same location (like-for-like), it's caution; if it involves adding new circuits, running new wire, modifying structural elements, or touching gas lines, it's refuse.

Output your classification in this exact format: Tier: <safe|caution|refuse> | Reason: <one-sentence explanation>
```

**User message:**
```
Classify this home repair question:

{user_question}
```

---

### Caution/refuse boundary

**Boundary rule:** Caution is for like-for-like replacements at the same location (where turning off power or closing a valve is enough); refuse is for anything involving new circuits, new wire runs, structural modification, gas lines, or code-requiring work.

**Example 1: "How do I replace an existing outlet?"**
- **Tier:** Caution
- **Why:** This is a like-for-like replacement. The homeowner turns off power to the existing outlet, unscrews it, and installs a new one in the same hole. The circuit and wire are already there. Mistakes (reversed polarity, loose connections) can damage the outlet or cause a small fire, but the breach is localized. A reasonably careful homeowner can do this safely with a breaker off.

**Example 2: "How do I move my light switch to the other side of the room?"**
- **Tier:** Refuse
- **Why:** This requires running new wire through walls, opening the electrical panel (or finding a new breaker slot), and may require a permit. It's not a replacement; it's a new circuit run. If the homeowner guesses wrong about load capacity or wire gauge, they create a fire hazard. Structural intrusion (drilling through walls, inside cavities) also introduces risks the caution-tier examples don't have.

**Example 3 (boundary clarity): "How do I reset a GFCI outlet?"**
- **Tier:** Caution
- **Why:** Resetting a GFCI (pressing the reset button) is a like-for-like operation that doesn't modify wiring or circuitry. If the homeowner presses the wrong button or misunderstands, the outlet just doesn't reset—it doesn't create a fire hazard. This contrasts with replacing the GFCI outlet itself (also caution, but more hands-on) or installing a new GFCI outlet in a new location (refuse).

---

### Fallback behavior

**On parse failure (LLM output doesn't match the expected format):**
Return `{"tier": "caution", "reason": "Could not parse safety classification; defaulting to caution for safety."}`.

**On tier validation failure (parsed tier is not in VALID_TIERS):**
Return `{"tier": "caution", "reason": "Invalid tier returned; defaulting to caution for safety."}`.

**Why caution, not safe or refuse:**
- **Not "safe":** Failing open to "safe" is dangerous. If the classifier fails and we default to permitting a potentially harmful repair, we've violated the safety layer's entire purpose. Better to under-serve (refusing a safe question) than over-serve (permitting an unsafe one).
- **Not "refuse":** Defaulting to "refuse" on every parse error would frustrate legitimate users with false rejections. Over-refusing erodes trust in the system and makes it useless for safe and caution questions when the classifier is broken.
- **Caution is the balanced fallback:** It errors on the side of safety (conservative) while still allowing the user to see a response and make their own judgment. The responder will add appropriate disclaimers for caution-tier questions, so even a misfiled safe question will get appropriate guardrails.

**Logging:** Parse or validation failures must be logged to the audit log with a flag so developers can identify broken classifier outputs during review.

---

## Implementation Notes

*Fill this in after implementing, before moving to Milestone 2.*

**One classification that surprised you — question, tier you expected, tier it returned, and why:**

```
[your answer here]
```

**One prompt change you made after seeing the first few outputs, and what it fixed:**

```
[your answer here]
```
