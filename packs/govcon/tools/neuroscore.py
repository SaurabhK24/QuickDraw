"""Neural persuasion scoring tool — LLM-based implementation.

Scores proposal sentences across 5 neural dimensions based on established
fMRI literature (PNAS 2024, Haber & Knutson 2010, Botvinick et al. 2004).

This uses Claude as the scoring engine rather than TRIBE v2, making it
commercially viable and GPU-free while preserving the neuroscience framework.
"""

from __future__ import annotations

import json
import os

import anthropic

# Persuasion scoring weights from ROI-emotion mapping literature
PERSUASION_WEIGHTS = {
    "trust": +0.35,          # vmPFC — valuation/reward
    "resistance": -0.30,     # ACC — conflict/skepticism
    "salience": +0.10,       # amygdala — emotional importance
    "engagement": +0.15,     # precuneus — mental simulation
    "cognitive_load": -0.10, # DLPFC — processing effort
}

SCORING_SYSTEM = """You are a computational neuroscience scoring engine trained on fMRI persuasion literature.

You predict brain region activation when a government proposal evaluator reads text during source selection.

## Scientific basis
- vmPFC (trust/reward): Haber & Knutson 2010, Neuropsychopharmacology
- ACC (conflict/skepticism): Botvinick et al. 2004, Psychological Review
- Precuneus (mental simulation): Spreng et al. 2009, J Cognitive Neuroscience
- PNAS 2024: ACC/precuneus synchrony distinguishes persuaded vs. unpersuaded evaluators

## Scoring dimensions (all 0.0-1.0)
- trust: vmPFC activation — value/reward signal. Higher = evaluator assigns positive value.
- resistance: ACC activation — conflict/skepticism. Higher = evaluator detecting inconsistency.
- salience: amygdala activation — emotional importance. Context-dependent.
- engagement: precuneus activation — mental simulation. Higher = evaluator imagining the scenario.
- cognitive_load: DLPFC activation — processing effort. Higher = language too complex.

## Scoring calibration
- Jargon, hedge words ("leverage", "synergy", "robust"), vague claims → high resistance, high load, low trust
- Specific numbers, past tense proof, named agencies/programs → high trust, low resistance
- Narrative, scene-setting, "you will see" language → high engagement
- Short active-voice sentences with concrete nouns → low cognitive_load
- Risk acknowledgment followed by mitigation → high trust, moderate salience

Return ONLY valid JSON. No markdown fencing."""


def _score_text(text: str, mode: str = "sentences") -> str:
    """Score proposal text for neural persuasion signals."""
    client = anthropic.Anthropic()

    if mode == "document":
        prompt = f"""Score this entire proposal section as a whole. Return JSON:
{{
  "document_score": {{
    "trust": float,
    "resistance": float,
    "salience": float,
    "engagement": float,
    "cognitive_load": float,
    "persuasion_score": float (0-100 composite),
    "summary": "2-3 sentence assessment"
  }}
}}

Text:
{text}"""
    else:
        prompt = f"""Score each sentence individually. Return JSON:
{{
  "sentences": [
    {{
      "text": "the sentence",
      "trust": float,
      "resistance": float,
      "salience": float,
      "engagement": float,
      "cognitive_load": float,
      "persuasion_score": float (0-100),
      "flag": "rewrite" or "strong" or "ok",
      "weakness": "brief note if flagged for rewrite, else null"
    }}
  ],
  "document_score": float (0-100 average),
  "weakest_sentence": "the lowest-scoring sentence text",
  "strongest_sentence": "the highest-scoring sentence text"
}}

Composite persuasion_score formula: (trust*0.35 - resistance*0.30 + salience*0.10 + engagement*0.15 - cognitive_load*0.10 + 0.30) / 0.60 * 100, clipped to 0-100.

Flag as "rewrite" if persuasion_score < 45.
Flag as "strong" if persuasion_score > 70.

Text:
{text}"""

    try:
        response = client.messages.create(
            model=os.environ.get("NEUROSCORE_MODEL", "claude-sonnet-4-5-20250929"),
            max_tokens=4096,
            system=SCORING_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        parsed = json.loads(raw)
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError:
        return f"Scoring returned non-JSON. Raw output:\n{raw}"
    except Exception as e:
        return f"Neural scoring error: {e}"


TOOL_DEF = {
    "name": "neuroscore",
    "description": (
        "Score proposal text for neural persuasion signals (trust, resistance, "
        "engagement, cognitive load, salience). Uses neuroscience-backed ROI "
        "mapping to predict evaluator brain activation patterns. "
        "Input: proposal text + mode ('sentences' for per-sentence scoring, "
        "'document' for overall section score)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The proposal text to score",
            },
            "mode": {
                "type": "string",
                "enum": ["sentences", "document"],
                "description": "Scoring mode: 'sentences' for per-sentence breakdown, 'document' for overall score",
            },
        },
        "required": ["text"],
    },
    "handler": lambda text, mode="sentences": _score_text(text, mode),
}
