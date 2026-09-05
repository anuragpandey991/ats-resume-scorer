"""
app.py
Streamlit UI for the ATS Resume Scorer.
Run with: streamlit run app.py
"""

import streamlit as st
import plotly.graph_objects as go

from text_extraction import extract_resume_text
from keyword_matcher import compute_keyword_match
from semantic_similarity import compute_semantic_similarity
from experience_matcher import compute_experience_match
from resume_quality import compute_quality_report
from scoring_engine import compute_final_score
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
        keyword_result = compute_keyword_match(jd_to_score, resume_text)

    with st.spinner("Computing semantic similarity (loading model on first run, may take a moment)..."):
        semantic_result = compute_semantic_similarity(jd_to_score, resume_text)

    with st.spinner("Checking experience requirements..."):
        experience_result = compute_experience_match(jd_to_score, resume_text)

    final_result = compute_final_score(
        semantic_percent=semantic_result["similarity_percent"],
        keyword_percent=keyword_result["match_percent"],
        experience_result=experience_result,
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

    if final_result.get("experience_penalty", 0) > 0:
        st.caption(f"(Includes a -{final_result['experience_penalty']} point adjustment for an experience gap — see details below.)")

    tab_overview, tab_skills, tab_quality = st.tabs(["📊 Overview", "🧩 Skills Detail", "📋 Resume Quality"])

    # ---- Overview tab ----
    with tab_overview:
        score_bar("Semantic Similarity", semantic_result["similarity_percent"],
                   "How closely your resume's overall language/experience matches the JD's context.")
        score_bar("Keyword Match", keyword_result["match_percent"],
                   "Percentage of the JD's named skills found in your resume.")

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

    # ---- Resume quality tab ----
    with tab_quality:
        qscore = quality_report["quality_score"]
        st.metric("Resume Quality Score", f"{qscore}/100")
        st.caption("Independent of this specific job — reflects general resume quality.")
        st.divider()

        render_insight_block(quality_insights["strengths"], quality_insights["improvements"])

        with st.expander("See full quality check details"):
            st.write("**Contact info detected:**", quality_report["contact_info"])
            st.write("**Word count:**", quality_report["length"]["word_count"])
            st.write("**Bullets with quantified metrics:**",
                      f"{quality_report['quantification']['quantified_count']} / {quality_report['quantification']['total_bullets']}")
            if quality_report['quantification'].get('unquantified_examples'):
                st.write("**Bullets that could use a number/metric:**")
                for b in quality_report['quantification']['unquantified_examples']:
                    st.markdown(f"  - {b}")
            if quality_report["grammar"].get("available"):
                g = quality_report["grammar"]
                st.write(f"**Grammar/spelling issues found:** {g.get('total_found', 0)}")
                if g.get("filtered_technical_terms", 0) > 0:
                    st.caption(f"({g['filtered_technical_terms']} additional flags were recognized technical terms/names and skipped)")
                for issue in g["issues"]:
                    word_note = f" — *\"{issue['flagged_word']}\"*" if issue.get("flagged_word") else ""
                    st.markdown(f"  - **{issue['category']}**{word_note}: {issue['message']}")
            elif check_grammar:
                st.write("Grammar check was unavailable (couldn't reach the check service).")

st.divider()
st.caption(
    "Note: This tool gives directional guidance based on keyword and semantic overlap with the "
    "job description. It does not replicate any specific company's actual ATS software."
)
