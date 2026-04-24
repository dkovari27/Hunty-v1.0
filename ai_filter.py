"""
ai_filter.py — Scores job postings for relevance using Claude.

Uses prompt caching on the system prompt (stable job criteria) so repeated
calls to evaluate jobs within the same run are cheaper after the first one.
"""
import json
import logging

import anthropic

from config import AI_MODEL, ANTHROPIC_API_KEY, JOB_PROFILE, MIN_RELEVANCE_SCORE

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# System prompt is stable across all jobs in a run — good caching candidate.
_SYSTEM_PROMPT = f"""You are a precise job relevance evaluator. Your task is to \
score how well a job posting matches a candidate's profile and preferences.

CANDIDATE PROFILE:
{JOB_PROFILE.strip()}

SCORING GUIDE (1–10):
- 9–10: Excellent match on skills AND location is Basel/Switzerland/nearby CH, or near-perfect skills match with only trivial gaps
- 7–8:  Strong skills match; location is UK or EU (candidate explicitly open to both); no disqualifying factors
- 5–6:  Decent discipline match but one significant issue — e.g. US location, or moderate skill gap, or role is too junior/senior
- 3–4:  Partial match — wrong sub-discipline OR strong location mismatch (US) AND skill gaps
- 1–2:  Not a job posting, wrong discipline entirely, requires German B2+, or is a postdoc/academia role

LOCATION RULES (apply these strictly):
- Basel, Zurich, Geneva, or nearby Swiss cities → no location penalty (preferred)
- Any other European city or UK city (London, Cambridge, Oxford, etc.) → acceptable per candidate profile, minor penalty only
- Remote with no geographic restriction → treat like EU if role fits
- USA, Canada, Asia → significant penalty (-2 to -3 from skills score)

INSTANT DISQUALIFIERS (score 1–2 regardless of fit):
- Role requires German B2 or higher (candidate is B1)
- Postdoc or academic research position (explicitly excluded)
- Not an actual job posting (press release, article, profile page)

Respond with ONLY a valid JSON object in this exact format (no markdown fences):
{{
  "score": <integer 1-10>,
  "reasoning": "<one concise sentence>",
  "key_matches": ["<matched skill or factor>"],
  "concerns": ["<mismatch or concern>"]
}}"""


def _evaluate_job(job: dict) -> dict:
    """Call Claude to score a single job. Returns a dict with scoring fields."""
    job_text = (
        f"Job Title: {job.get('title', 'N/A')}\n"
        f"Company: {job.get('company', 'N/A')}\n"
        f"Location: {job.get('location', 'N/A')}\n"
        f"Salary: {job.get('salary') or 'Not listed'}\n"
        f"Date Posted: {job.get('date_posted', 'N/A')}\n\n"
        f"Description:\n{job.get('description', 'No description available')[:2500]}"
    )

    try:
        response = _client.messages.create(
            model=AI_MODEL,
            max_tokens=512,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    # Cache the stable system prompt — saves tokens on repeated calls
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Evaluate this job posting:\n\n{job_text}",
                }
            ],
        )

        raw = response.content[0].text.strip()

        # Strip accidental markdown code fences
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

        result = json.loads(raw)
        return {
            "relevance_score": max(1, min(10, int(result.get("score", 0)))),
            "ai_reasoning": str(result.get("reasoning", "")),
            "key_matches": result.get("key_matches", []),
            "concerns": result.get("concerns", []),
        }

    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error for '{job.get('title')}': {e}")
    except (KeyError, IndexError, ValueError) as e:
        logger.warning(f"Unexpected response structure for '{job.get('title')}': {e}")
    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic API error ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError as e:
        logger.error(f"Anthropic connection error: {e}")

    return {
        "relevance_score": 0,
        "ai_reasoning": "Evaluation failed",
        "key_matches": [],
        "concerns": [],
    }


def filter_jobs(jobs: list[dict], progress_callback=None) -> list[dict]:
    """
    Score every job with Claude.
    Returns ALL scored jobs sorted by score descending — caller decides what to display.
    Jobs below MIN_RELEVANCE_SCORE are included but flagged for easy filtering in Excel.
    """
    if not ANTHROPIC_API_KEY:
        logger.error(
            "ANTHROPIC_API_KEY is not set. "
            "Create a .env file with ANTHROPIC_API_KEY=your_key"
        )
        return []

    logger.info(
        f"AI filter: evaluating {len(jobs)} jobs "
        f"(threshold >= {MIN_RELEVANCE_SCORE})"
    )

    consecutive_failures = 0

    for i, job in enumerate(jobs, start=1):
        logger.info(
            f"  [{i}/{len(jobs)}] {job.get('title', '?')} @ {job.get('company', '?')}"
        )
        scores = _evaluate_job(job)
        job.update(scores)

        if scores["ai_reasoning"] == "Evaluation failed":
            consecutive_failures += 1
            if consecutive_failures >= 3:
                logger.error(
                    "3 consecutive API failures — aborting scoring. "
                    "Check your Anthropic credit balance at console.anthropic.com."
                )
                break
        else:
            consecutive_failures = 0

        logger.info(
            f"    Score {scores['relevance_score']}/10 — {scores['ai_reasoning']}"
        )

        if progress_callback:
            progress_callback(i, len(jobs))

    # Sorting is handled by write_excel (after distance enrichment).

    passed = sum(1 for j in jobs if j["relevance_score"] >= MIN_RELEVANCE_SCORE)
    logger.info(
        f"AI filter complete: {passed}/{len(jobs)} jobs at or above threshold "
        f"(score >= {MIN_RELEVANCE_SCORE}) — all written to Excel"
    )
    return jobs
