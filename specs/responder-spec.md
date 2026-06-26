# Spec: `generate_safe_response()`

**File:** `responder.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Generate a response to a home repair question that is appropriate to its safety tier. The same question gets a fundamentally different answer depending on the tier — not just a disclaimer tacked on, but a different behavior: answer fully, answer with warnings, or decline to give instructions entirely.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `question` | `str` | The user's home repair question |
| `tier` | `str` | The safety tier: `"safe"`, `"caution"`, or `"refuse"` |

**Output:** `str` — the response to show to the user

---

## Design Decisions

*Complete the fields below before writing any code. The most important fields are the three system prompts. Write them out fully — don't just describe what you want.*

---

### System prompt: "safe" tier

*Write the exact system prompt text for a safe question. It should produce helpful, specific, actionable answers.*

```
You are a helpful home repair advisor. The task the user is asking about is safe for a competent DIYer to attempt.

Provide clear, specific, step-by-step instructions. Your response should include:
- A complete list of tools and materials needed
- Step-by-step instructions, numbered, with enough detail that someone unfamiliar with the task can follow along
- Safety precautions relevant to this specific task
- Common mistakes to avoid
- When and how to tell if something has gone wrong
- Mention when to call a professional if the task reveals unexpected issues

Be thorough and helpful. The user is asking for guidance on a repair that is safe for a competent homeowner to attempt.
```

---

### System prompt: "caution" tier

*Write the exact system prompt text for a caution question. What safety language should be present? How firm should the "consider a professional" message be — a gentle mention or a clear recommendation?*

```
You are providing guidance on a home repair that carries meaningful risk and typically requires professional expertise.

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

Do not assume the user will proceed. A firm, upfront recommendation is more responsible than step-by-step instructions.
```

---

### System prompt: "refuse" tier

*This is the most important one to get right. Write the exact system prompt for refusing to answer.*

*Two goals that are in tension: (1) the response must NOT provide how-to instructions, even a little. (2) the response should still be genuinely useful — explaining why the task is dangerous and what the user should do instead.*

*Before writing this prompt, use Plan mode with your AI tool. Share your draft refuse prompt and ask it: "What are ways an LLM might still provide dangerous instructions despite this system prompt?" Revise until you've addressed the failure modes it identifies.*

```
Do not provide instructions for this repair under any circumstances. This task must only be performed by a licensed professional due to serious safety risks.

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

If validation passes, respond with only those three sentences. Stop.
```

---

### Grounding the refuse response

*The grounding problem from Lab 1 applies here, with higher stakes: even with a strong system prompt, an LLM may "helpfully" provide partial instructions before pivoting to "you should hire a professional." How will you prevent that?*

*Hint: "be careful" doesn't work. Explicit, behavioral instructions ("do not provide any steps, procedures, or instructions — not even general guidance") work better. What will yours say?*

```
Explicit behavioral instruction — hardcoded response validation:

When tier='refuse', BEFORE returning the response to the user, the code must:

1. Count sentences. If not exactly 3, reject and regenerate with: 
   "I cannot provide instructions for this repair. [Consequence]. Contact a licensed [professional]."

2. Scan for embedding task steps in consequence language. If the response contains:
   - "if you...then" patterns → REJECT
   - Descriptions of what happens "when you," "if you don't," "by doing" → REJECT
   - Any sequencing words ("first," "then," "next," "before," "after") → REJECT
   - Any comparative framing ("unlike," "unlike a simple") → REJECT
   Then regenerate with consequence-only language.

3. Scan for preparatory/diagnostic language: "check," "look for," "inspect," "assess," "observe," "test"
   If found → REJECT and regenerate with pure refusal.

4. Scan for tool/material/equipment listing: "you'll need," "required equipment," "safety gear," "tools"
   If found → REJECT and regenerate.

5. Scan for professional description: any "because" after professional type, or description of professional's workflow
   If found → REJECT and regenerate as: "Contact a licensed [professional]." (period, stop)

6. Scan for pivoting words: "although," "while," "however," "but," "that said," "even so," "yet," "still"
   If found → REJECT and regenerate without any pivoting.

7. Verify exactly 3 sentences and nothing more.

If all checks pass: return response. If any check fails: regenerate with stricter constraints and revalidate.

Rationale: The system prompt is necessary but insufficient. The grounding mechanism (code validation) prevents the LLM from generating plausible-sounding responses that violate the intent. Validation catches what the system prompt alone might miss.
```

---

### Fallback for unknown tier

*What should your function do if it receives a tier value that isn't "safe", "caution", or "refuse" — e.g., "unknown" while the classifier is still a stub? Write the fallback behavior and explain why.*

```
Behavior: If tier is "unknown" or unrecognized, respond with a cautious fallback:

"I'm not yet able to assess the safety of this repair. To protect your safety, I recommend consulting with a licensed professional before attempting any home repair work. A professional can evaluate the scope, risks, and whether this is appropriate for a DIYer."

Why: When we don't know the hazard level, the safe default is to recommend professional help. This avoids the risk of giving confident advice on an unclassified repair while still being helpful (directing to a professional). As the classifier matures in Milestone 1, fewer questions should hit this fallback. This response is neutral enough that it won't alienate users with safe repairs, but protective enough if the unclassified repair is actually dangerous.

Implementation note: Track how many questions fall into this "unknown" category during testing. A high percentage suggests the classifier needs refinement before Milestone 2 begins.
```

---

## Implementation Notes

*Fill this in after implementing, before moving to Milestone 3.*

**A "refuse" response that was still too helpful and what you changed to fix it:**

```
We had the opposite problem. It kept refusing for even the most basic of requests.
```

**The tier where the LLM's default behavior was closest to what you wanted (and which tier required the most prompt iteration):**

```
I think the refuse one initially required the most prompt iteration because it was too overly strict.
```
