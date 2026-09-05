"""
scoring_engine.py
Combines keyword match %, semantic similarity %, and an experience-fit
adjustment into a final weighted ATS score.
"""

WEIGHT_SEMANTIC = 0.55
WEIGHT_KEYWORD = 0.45

MAX_EXPERIENCE_PENALTY = 15
PENALTY_PER_MISSING_YEAR = 4

# Verdict labels deliberately avoid words like "Poor"/"Weak" in isolation —
# a candidate who matches most required skills and meets the experience bar
# but scores in the 40-59 band (often due to domain-phrasing differences that
# semantic similarity picks up on) should not read as "you're a bad fit."
# The label plus description together aim to be accurate without being
# needlessly discouraging.
VERDICT_TIERS = [
    (80, "Strong Fit", "Your resume aligns closely with this role's requirements."),
    (60, "Good Fit", "Solid alignment overall, with some room to sharpen the match."),
    (40, "Developing Fit", "A reasonable foundation — a handful of targeted edits could meaningfully raise this."),
    (0, "Early-Stage Fit", "There's a real gap to close here, but the specific gaps below are addressable."),
]


def _verdict_for_score(score: float) -> tuple:
    for threshold, label, description in VERDICT_TIERS:
        if score >= threshold:
            return label, description
    return VERDICT_TIERS[-1][1], VERDICT_TIERS[-1][2]


def compute_final_score(semantic_percent: float, keyword_percent: float,
                         experience_result: dict | None = None,
                         w_semantic: float = WEIGHT_SEMANTIC,
                         w_keyword: float = WEIGHT_KEYWORD) -> dict:
    base_score = round(semantic_percent * w_semantic + keyword_percent * w_keyword, 1)

    experience_penalty = 0.0
    if experience_result and experience_result.get("required_years") is not None:
        gap_years = experience_result.get("gap_years", 0.0)
        experience_penalty = min(MAX_EXPERIENCE_PENALTY, gap_years * PENALTY_PER_MISSING_YEAR)

    final_score = round(max(0.0, base_score - experience_penalty), 1)
    verdict, verdict_description = _verdict_for_score(final_score)

    return {
        "final_score": final_score,
        "base_score": base_score,
        "experience_penalty": round(experience_penalty, 1),
        "verdict": verdict,
        "verdict_description": verdict_description,
        "breakdown": {
            "semantic_similarity": semantic_percent,
            "keyword_match": keyword_percent,
            "weights": {"semantic": w_semantic, "keyword": w_keyword},
        },
    }


if __name__ == "__main__":
    print("No experience data:", compute_final_score(72.0, 50.0))
    print("With experience gap:", compute_final_score(42.0, 80.0, {"required_years": 6.0, "gap_years": 2.4}))
    print("High keyword, moderate semantic:", compute_final_score(42.0, 80.0))
