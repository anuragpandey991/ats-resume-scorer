"""
scoring_engine.py
Combines keyword match %, semantic similarity %, and an experience-fit adjustment
into a final weighted ATS score.
"""

# Weights sum to 1.0. Semantic gets slightly more weight since it captures
# paraphrased/contextual matches that exact keyword matching misses.
WEIGHT_SEMANTIC = 0.55
WEIGHT_KEYWORD = 0.45

# Experience is NOT blended into the weighted average above — it's applied as a
# capped penalty afterward instead. Reasoning: a candidate can be a great skills/
# semantic match but short on tenure, or vice versa. Averaging it in would let a
# huge experience gap get diluted/hidden by a strong skills score. A separate
# penalty keeps the experience shortfall visible in the final number without
# letting it dominate (it's capped so it can't tank an otherwise strong match).
MAX_EXPERIENCE_PENALTY = 15  # max points that can be deducted for an experience gap
PENALTY_PER_MISSING_YEAR = 4  # points deducted per year short of the requirement


def compute_final_score(semantic_percent: float, keyword_percent: float,
                         experience_result: dict | None = None,
                         w_semantic: float = WEIGHT_SEMANTIC,
                         w_keyword: float = WEIGHT_KEYWORD) -> dict:
    """
    Combine the two sub-scores into one final score (0-100), plus a simple
    verdict label so the UI can show something friendlier than a raw number.

    experience_result: optional dict from experience_matcher.compute_experience_match().
    If the JD had no detectable experience requirement, or it's omitted, no
    penalty is applied.
    """
    base_score = round(semantic_percent * w_semantic + keyword_percent * w_keyword, 1)

    experience_penalty = 0.0
    if experience_result and experience_result.get("required_years") is not None:
        gap_years = experience_result.get("gap_years", 0.0)
        experience_penalty = min(MAX_EXPERIENCE_PENALTY, gap_years * PENALTY_PER_MISSING_YEAR)

    final_score = round(max(0.0, base_score - experience_penalty), 1)

    if final_score >= 80:
        verdict = "Strong Match"
    elif final_score >= 60:
        verdict = "Moderate Match"
    elif final_score >= 40:
        verdict = "Weak Match"
    else:
        verdict = "Poor Match"

    return {
        "final_score": final_score,
        "base_score": base_score,
        "experience_penalty": round(experience_penalty, 1),
        "verdict": verdict,
        "breakdown": {
            "semantic_similarity": semantic_percent,
            "keyword_match": keyword_percent,
            "weights": {"semantic": w_semantic, "keyword": w_keyword},
        },
    }


if __name__ == "__main__":
    # No experience data
    result = compute_final_score(semantic_percent=72.0, keyword_percent=50.0)
    print("Without experience data:", result)

    # With an experience gap of 2.4 years
    exp_result = {"required_years": 6.0, "candidate_years": 3.6, "gap_years": 2.4}
    result2 = compute_final_score(semantic_percent=72.0, keyword_percent=50.0, experience_result=exp_result)
    print("With 2.4yr experience gap:", result2)

    # Candidate exceeds requirement (gap_years already floored at 0 upstream)
    exp_ok = {"required_years": 3.0, "candidate_years": 5.0, "gap_years": 0.0}
    result3 = compute_final_score(semantic_percent=72.0, keyword_percent=50.0, experience_result=exp_ok)
    print("Experience requirement met:", result3)
