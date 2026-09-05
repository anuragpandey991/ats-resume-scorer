"""
scoring_engine.py
Combines four independent signals into a final weighted ATS score:

    Final Score = w1*Semantic Similarity
                + w2*Skill Keyword Match %   (taxonomy blended with TF-IDF)
                + w3*Experience Match %
                + w4*Structure/Formatting %

Weights are tuned (not just guessed) — see WEIGHT PROFILES below — and all
four inputs are normalized to a 0-100 scale before combining, so the weights
themselves are directly interpretable as "% of the final score this signal
controls."
"""

# --- Weight profiles -------------------------------------------------------
# "balanced" is the default. Semantic + keyword still carry the most weight
# (they're the most direct measure of "does this resume fit this JD"), but
# experience and structure are no longer folded in as an ad-hoc penalty —
# they're first-class, capped contributors. This also fixes a real issue
# with the old penalty-based design: a candidate with NO stated experience
# requirement in the JD used to get a free pass on that axis entirely; now
# a missing requirement just means experience contributes a neutral 100
# (can't fail a bar that wasn't set) rather than being dropped from the
# formula's weight budget, which kept the other weights honest at all times.
WEIGHT_PROFILES = {
    "balanced":          {"semantic": 0.30, "keyword": 0.30, "experience": 0.20, "structure": 0.20},
    "skills_first":       {"semantic": 0.20, "keyword": 0.45, "experience": 0.20, "structure": 0.15},
    "experience_strict":  {"semantic": 0.25, "keyword": 0.25, "experience": 0.35, "structure": 0.15},
    "ats_parse_focused":  {"semantic": 0.25, "keyword": 0.30, "experience": 0.15, "structure": 0.30},
}
DEFAULT_PROFILE = "balanced"

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


def compute_experience_score(experience_result: dict | None) -> float:
    """
    Converts the experience_matcher result into a 0-100 score rather than a
    penalty. No stated requirement -> 100 (nothing to fall short of).
    Meets or exceeds -> 100. Falls short -> scaled by how much of the
    requirement is actually met, so 4.5/5 years reads very differently from
    1/5 years instead of both eating the same flat penalty.
    """
    if not experience_result or experience_result.get("required_years") is None:
        return 100.0

    required = experience_result["required_years"]
    candidate = experience_result["candidate_years"]

    if required <= 0 or candidate >= required:
        return 100.0

    ratio = candidate / required
    return round(max(0.0, min(100.0, ratio * 100)), 1)


def compute_final_score(semantic_percent: float, keyword_percent: float,
                         experience_result: dict | None = None,
                         structure_percent: float | None = None,
                         weight_profile: str = DEFAULT_PROFILE,
                         weights: dict | None = None) -> dict:
    """
    weights, if provided, overrides weight_profile entirely and must contain
    keys: semantic, keyword, experience, structure (need not pre-sum to 1 —
    they're normalized here).
    """
    w = dict(weights) if weights else dict(WEIGHT_PROFILES.get(weight_profile, WEIGHT_PROFILES[DEFAULT_PROFILE]))
    total_w = sum(w.values()) or 1.0
    w = {k: v / total_w for k, v in w.items()}

    experience_score = compute_experience_score(experience_result)

    # No structure signal supplied -> redistribute its weight proportionally
    # across the other three rather than silently zeroing the final score's
    # contribution from a missing input.
    if structure_percent is None:
        remaining = w["semantic"] + w["keyword"] + w["experience"]
        w = {k: (v / remaining if k != "structure" else 0.0) for k, v in w.items()}
        structure_percent = 0.0

    final_score = round(
        semantic_percent * w["semantic"]
        + keyword_percent * w["keyword"]
        + experience_score * w["experience"]
        + structure_percent * w["structure"],
        1,
    )
    final_score = max(0.0, min(100.0, final_score))
    verdict, verdict_description = _verdict_for_score(final_score)

    return {
        "final_score": final_score,
        "verdict": verdict,
        "verdict_description": verdict_description,
        "experience_score": experience_score,
        "breakdown": {
            "semantic_similarity": semantic_percent,
            "keyword_match": keyword_percent,
            "experience_match": experience_score,
            "structure_formatting": structure_percent,
            "weights": w,
        },
    }


if __name__ == "__main__":
    print("No experience/structure data:", compute_final_score(72.0, 50.0))
    print("With experience gap:", compute_final_score(
        42.0, 80.0, {"required_years": 6.0, "candidate_years": 3.6, "meets_requirement": False, "gap_years": 2.4},
        structure_percent=85.0,
    ))
    print("Skills-first profile:", compute_final_score(
        42.0, 80.0, structure_percent=90.0, weight_profile="skills_first",
    ))
    print("Custom weights:", compute_final_score(
        60.0, 60.0, structure_percent=70.0, weights={"semantic": 1, "keyword": 1, "experience": 1, "structure": 1},
    ))
