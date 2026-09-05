"""
app.py
Streamlit UI for the ATS Resume Scorer.
Run with: streamlit run app.py
"""

import streamlit as st

from text_extraction import extract_resume_text
from keyword_matcher import compute_keyword_match, compute_keyword_match_combined
from semantic_similarity import compute_semantic_similarity
from experience_matcher import compute_experience_match
from resume_quality import compute_quality_report
from resume_structure import compute_structure_score
from scoring_engine import compute_final_score, WEIGHT_PROFILES, DEFAULT_PROFILE
from insight_generator import generate_insights
from quality_insight_generator import generate_quality_insights
from jd_cleaner import clean_jd_text

st.set_page_config(page_title="ATS Resume Scorer", page_icon="📄", layout="centered")

# Small CSS polish: card-style containers and consistent spacing without
# fighting Streamlit's theme system.
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    div[data-testid="stMetric"] {
        background-color: rgba(128,128,128,0.08);
        border-radius: 10px;
        padding: 12px 16px;
    }
    .issue-card {
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 8px;
        border-left: 4px solid;
    }
    .issue-card.spelling { background-color: rgba(255, 99, 71, 0.08); border-left-color: #ff6347; }
    .issue-card.grammar { background-color: rgba(255, 165, 0, 0.10); border-left-color: #ffa500; }
    .issue-card.punctuation { background-color: rgba(100, 149, 237, 0.10); border-left-color: #6495ed; }
    .issue-card.style { background-color: rgba(147, 112, 219, 0.10); border-left-color: #9370db; }
    .issue-card.other { background-color: rgba(128, 128, 128, 0.10); border-left-color: #808080; }
    .issue-word { font-weight: 600; }
    .category-pill {
        display: inline-block; padding: 2px 10px; border-radius: 999px;
        font-size: 0.75rem; font-weight: 600; margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

st.title("📄 ATS Resume Scorer")
st.write("Upload your resume and paste the job description below. Get a match score and specific, actionable feedback.")

col1, col2 = st.columns(2)
with col1:
    resume_file = st.file_uploader("Upload Resume (PDF or DOCX)", type=["pdf", "docx"])
with col2:
    jd_text = st.text_area("Paste Job Description", height=200, placeholder="Paste the full job description here...")

with st.expander("⚙️ Options"):
    check_grammar = st.checkbox(
        "Run real grammar/spelling check (uses a free external API — needs internet)", value=True
    )
    auto_clean_jd = st.checkbox(
        "Auto-clean job description before scoring (removes benefits/EEO/metadata boilerplate)", value=True
    )
    use_tfidf_blend = st.checkbox(
        "Blend TF-IDF term coverage into keyword match (catches JD-specific terms outside the skill taxonomy)",
        value=True,
    )
    weight_profile = st.selectbox(
        "Scoring weight profile",
        options=list(WEIGHT_PROFILES.keys()),
        index=list(WEIGHT_PROFILES.keys()).index(DEFAULT_PROFILE),
        help="Changes how much each of the four score components (semantic, keyword, experience, structure) "
             "contributes to the final score.",
    )
    with st.popover("What do the profiles mean?"):
        for name, w in WEIGHT_PROFILES.items():
            st.write(
                f"**{name}** — semantic {int(w['semantic']*100)}%, keyword {int(w['keyword']*100)}%, "
                f"experience {int(w['experience']*100)}%, structure {int(w['structure']*100)}%"
            )

analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)


def score_bar(label: str, value: float, help_text: str = ""):
    """A clean labeled progress bar in place of a plain metric number."""
    st.markdown(f"**{label}**  —  {value}%")
    st.progress(min(1.0, max(0.0, value / 100)))
    if help_text:
        st.caption(help_text)


def render_insight_block(strengths: list, improvements: list, empty_strengths_msg: str = None):
    if strengths:
        st.markdown("**✅ What's working**")
        for s in strengths:
            st.markdown(f"- {s}")
    elif empty_strengths_msg:
        st.caption(empty_strengths_msg)

    if improvements:
        st.markdown("**🎯 Worth improving**")
        for i in improvements:
            st.markdown(f"- {i}")


CATEGORY_STYLE = {
    "spelling": {"class": "spelling", "icon": "🔤", "color": "#ff6347"},
    "typos": {"class": "spelling", "icon": "🔤", "color": "#ff6347"},
    "grammar": {"class": "grammar", "icon": "📝", "color": "#ffa500"},
    "punctuation": {"class": "punctuation", "icon": "❓", "color": "#6495ed"},
    "style": {"class": "style", "icon": "🎨", "color": "#9370db"},
}


def _style_for_category(category_name: str) -> dict:
    key = category_name.strip().lower()
    for match_key, style in CATEGORY_STYLE.items():
        if match_key in key:
            return style
    return {"class": "other", "icon": "•", "color": "#808080"}


def render_grammar_issues(issues: list, filtered_count: int):
    """
    Groups grammar/spelling issues by category and renders each as a small
    colored card (flagged word + message), instead of one long dumped
    paragraph of markdown bullets.
    """
    if not issues:
        note = "No grammar or spelling issues found." if filtered_count == 0 else \
            f"No real issues found ({filtered_count} technical term(s)/name(s) correctly skipped)."
        st.success(f"✅ {note}")
        return

    grouped = {}
    for issue in issues:
        grouped.setdefault(issue["category"], []).append(issue)

    # Order categories with the most issues first, so the biggest problem area is visible immediately.
    for category, cat_issues in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        style = _style_for_category(category)
        st.markdown(
            f'<span class="category-pill" style="background-color:{style["color"]}22; color:{style["color"]};">'
            f'{style["icon"]} {category} · {len(cat_issues)}</span>',
            unsafe_allow_html=True,
        )
        for issue in cat_issues:
            word = issue.get("flagged_word", "")
            word_html = f'<span class="issue-word">"{word}"</span> — ' if word else ""
            st.markdown(
                f'<div class="issue-card {style["class"]}">{word_html}{issue["message"]}</div>',
                unsafe_allow_html=True,
            )

    if filtered_count > 0:
        st.caption(f"({filtered_count} additional flag(s) were recognized technical terms/names and skipped.)")


if analyze_clicked:
    if not resume_file:
        st.error("Please upload a resume file.")
        st.stop()
    if not jd_text or not jd_text.strip():
        st.error("Please paste a job description.")
        st.stop()

    with st.spinner("Extracting resume text..."):
        try:
            resume_text = extract_resume_text(resume_file)
        except ValueError as e:
            st.error(str(e))
            st.stop()

    jd_to_score = jd_text
    jd_clean_info = None
    if auto_clean_jd:
        jd_clean_info = clean_jd_text(jd_text)
        jd_to_score = jd_clean_info["cleaned_text"] or jd_text

    with st.spinner("Matching skills/keywords..."):
        if use_tfidf_blend:
            keyword_result = compute_keyword_match_combined(jd_to_score, resume_text)
        else:
            keyword_result = compute_keyword_match(jd_to_score, resume_text)
            keyword_result["taxonomy_match_percent"] = keyword_result["match_percent"]

    with st.spinner("Computing semantic similarity (loading model on first run, may take a moment)..."):
        semantic_result = compute_semantic_similarity(jd_to_score, resume_text)

    with st.spinner("Checking experience requirements..."):
        experience_result = compute_experience_match(jd_to_score, resume_text)

    with st.spinner("Checking structure and formatting..."):
        structure_report = compute_structure_score(resume_text)

    final_result = compute_final_score(
        semantic_percent=semantic_result["similarity_percent"],
        keyword_percent=keyword_result["match_percent"],
        experience_result=experience_result,
        structure_percent=structure_report["structure_score"],
        weight_profile=weight_profile,
    )

    insights = generate_insights(keyword_result, semantic_result, final_result, experience_result)

    with st.spinner("Checking resume quality (grammar, phrasing, formatting)..."):
        quality_report = compute_quality_report(resume_text, check_grammar=check_grammar)
        quality_insights = generate_quality_insights(quality_report)

    st.divider()

    # ---- Top-level summary card ----
    score = final_result["final_score"]
    verdict = final_result["verdict"]
    verdict_description = final_result["verdict_description"]

    verdict_colors = {
        "Strong Fit": "🟢", "Good Fit": "🟢", "Developing Fit": "🟡", "Early-Stage Fit": "🟠",
    }
    badge = verdict_colors.get(verdict, "")

    st.subheader(f"{badge} {verdict} — {score}/100")
    st.write(verdict_description)
    st.caption(f"Weight profile: **{weight_profile}** — see breakdown below.")

    tab_overview, tab_skills, tab_quality = st.tabs(["📊 Overview", "🧩 Skills Detail", "📋 Resume Quality"])

    # ---- Overview tab ----
    with tab_overview:
        w = final_result["breakdown"]["weights"]
        score_bar("Semantic Similarity", semantic_result["similarity_percent"],
                   f"How closely your resume's overall language/experience matches the JD's context. (weight: {int(w['semantic']*100)}%)")
        score_bar("Keyword Match", keyword_result["match_percent"],
                   f"Skill-taxonomy + TF-IDF term coverage against the JD. (weight: {int(w['keyword']*100)}%)")
        score_bar("Experience Match", final_result["experience_score"],
                   f"How your estimated years of experience compare to the JD's stated requirement. (weight: {int(w['experience']*100)}%)")
        score_bar("Structure / Formatting", structure_report["structure_score"],
                   f"Section presence/order, bullet & date-format consistency, contact-info placement. (weight: {int(w['structure']*100)}%)")

        if experience_result.get("required_years") is not None:
            req = experience_result["required_years"]
            cand = experience_result["candidate_years"]
            met = experience_result["meets_requirement"]
            icon = "✅" if met else "⚠️"
            st.info(f"{icon} **Experience:** JD asks for {req}+ years — your resume shows ~{cand} years.")

        st.divider()
        render_insight_block(insights["strengths"], insights["improvements"])

        if jd_clean_info:
            removed_count = len(jd_clean_info["removed_paragraphs"]) + (1 if jd_clean_info["removed_footer"] else 0)
            if removed_count > 0:
                with st.expander(
                    f"🧹 Auto-cleaned JD: removed {jd_clean_info['original_word_count'] - jd_clean_info['cleaned_word_count']} "
                    f"words of boilerplate before scoring"
                ):
                    if jd_clean_info["removed_paragraphs"]:
                        st.write("**Removed as boilerplate:**")
                        for p in jd_clean_info["removed_paragraphs"]:
                            st.markdown(f"> {p}")
                    if jd_clean_info["removed_footer"]:
                        st.write("**Removed as metadata footer:**")
                        st.markdown(f"> {jd_clean_info['removed_footer'][:300]}...")

    # ---- Skills detail tab ----
    with tab_skills:
        st.write(f"**Skills found in JD ({len(keyword_result['jd_skills'])}):**", ", ".join(keyword_result["jd_skills"]) or "None detected")
        st.write(f"**✅ Matched ({len(keyword_result['matched_skills'])}):**", ", ".join(keyword_result["matched_skills"]) or "None")
        st.write(f"**❌ Missing ({len(keyword_result['missing_skills'])}):**", ", ".join(keyword_result["missing_skills"]) or "None")
        if keyword_result.get("semantic_matched_skills"):
            st.write("**🔍 Matched via semantic inference:**", ", ".join(keyword_result["semantic_matched_skills"]))

        if use_tfidf_blend and "tfidf_match_percent" in keyword_result:
            st.divider()
            st.write(
                f"**TF-IDF term coverage:** {keyword_result['tfidf_match_percent']}% of the JD's top weighted "
                f"terms appear in your resume (taxonomy-only match was {keyword_result.get('taxonomy_match_percent', keyword_result['match_percent'])}%)."
            )
            if keyword_result.get("tfidf_missing_terms"):
                st.caption("Top JD terms (by TF-IDF weight) not found in your resume:")
                st.write(", ".join(keyword_result["tfidf_missing_terms"][:15]))

    # ---- Resume quality tab ----
    with tab_quality:
        qscore = quality_report["quality_score"]
        col_q1, col_q2 = st.columns(2)
        with col_q1:
            st.metric("Resume Quality Score", f"{qscore}/100")
            st.caption("Independent of this specific job — reflects general resume quality.")
        with col_q2:
            st.metric("Structure/Formatting Score", f"{structure_report['structure_score']}/100")
            st.caption("Section presence/order, bullets, dates, contact placement.")

        st.divider()
        render_insight_block(quality_insights["strengths"], quality_insights["improvements"])

        st.divider()
        st.markdown("### 🔎 Spelling & Grammar")
        grammar = quality_report["grammar"]
        if grammar.get("available"):
            render_grammar_issues(grammar["issues"], grammar.get("filtered_technical_terms", 0))
        elif check_grammar:
            st.warning("Grammar check was unavailable (couldn't reach the check service).")
        else:
            st.caption("Grammar check was turned off in Options.")

        st.markdown("### 🧱 Structure & Formatting Detail")
        sc1, sc2 = st.columns(2)
        with sc1:
            sections = structure_report["sections"]
            if sections["has_all_required"]:
                st.success("✅ All key sections found (Experience, Education, Skills).")
            else:
                st.error(f"⚠️ Missing section(s): {', '.join(sections['missing_required'])}")

            bullets = structure_report["bullets"]
            if bullets.get("consistent", True):
                st.success("✅ Bullet style is consistent.")
            else:
                st.warning(f"⚠️ Mixed bullet symbols detected: {bullets.get('symbols_used')}")

        with sc2:
            dates = structure_report["dates"]
            if dates.get("consistent", True):
                st.success("✅ Date formatting is consistent.")
            else:
                st.warning(f"⚠️ Mixed date formats: {', '.join(dates.get('mixed_styles', []))}")

            contact = structure_report["contact_placement"]
            if contact["email_near_top"] and contact["phone_near_top"]:
                st.success("✅ Contact info is easy to find near the top.")
            else:
                st.warning("⚠️ Contact info isn't clearly placed near the top of the document.")

        with st.expander("See full quality check details"):
            st.write("**Contact info detected:**", quality_report["contact_info"])
            st.write("**Word count:**", quality_report["length"]["word_count"])
            st.write("**Bullets with quantified metrics:**",
                      f"{quality_report['quantification']['quantified_count']} / {quality_report['quantification']['total_bullets']}")
            if quality_report['quantification'].get('unquantified_examples'):
                st.write("**Bullets that could use a number/metric:**")
                for b in quality_report['quantification']['unquantified_examples']:
                    st.markdown(f"  - {b}")

st.divider()
st.caption(
    "Note: This tool gives directional guidance based on keyword and semantic overlap with the "
    "job description. It does not replicate any specific company's actual ATS software."
)
