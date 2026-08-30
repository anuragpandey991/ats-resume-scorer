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

st.title("📄 ATS Resume Scorer")
st.write(
    "Upload your resume and paste the job description below. "
    "Get a match score and specific, actionable feedback on where you're lagging."
)

col1, col2 = st.columns(2)

with col1:
    resume_file = st.file_uploader("Upload Resume (PDF or DOCX)", type=["pdf", "docx"])

with col2:
    jd_text = st.text_area("Paste Job Description", height=200, placeholder="Paste the full job description here...")

check_grammar = st.checkbox(
    "Also run real grammar/spelling check (uses a free external API — needs internet, may be slow/rate-limited)",
    value=True,
)
auto_clean_jd = st.checkbox(
    "Auto-clean job description before scoring (removes benefits/EEO/legal boilerplate and job-board "
    "metadata footer, which otherwise dilutes the match score)",
    value=True,
)

analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)

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
    if auto_clean_jd:
        clean_result = clean_jd_text(jd_text)
        jd_to_score = clean_result["cleaned_text"] or jd_text  # never score against empty text
        removed_count = len(clean_result["removed_paragraphs"]) + (1 if clean_result["removed_footer"] else 0)
        if removed_count > 0:
            with st.expander(
                f"🧹 Auto-cleaned JD: removed {clean_result['original_word_count'] - clean_result['cleaned_word_count']} "
                f"words of boilerplate/metadata before scoring (click to review)"
            ):
                if clean_result["removed_paragraphs"]:
                    st.write("**Removed as boilerplate:**")
                    for p in clean_result["removed_paragraphs"]:
                        st.markdown(f"> {p}")
                if clean_result["removed_footer"]:
                    st.write("**Removed as metadata footer:**")
                    st.markdown(f"> {clean_result['removed_footer'][:300]}...")
                st.caption("Uncheck 'Auto-clean job description' above if this removed something you needed.")

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

    # ---- Results display ----
    st.divider()
    st.subheader("Results")

    score = final_result["final_score"]
    verdict = final_result["verdict"]

    score_col, verdict_col = st.columns([1, 2])
    with score_col:
        delta = None
        if final_result.get("experience_penalty", 0) > 0:
            delta = f"-{final_result['experience_penalty']} (experience gap)"
        st.metric("Overall Match Score", f"{score}/100", delta=delta, delta_color="inverse")
    with verdict_col:
        st.metric("Verdict", verdict)

    # Experience requirement card
    if experience_result.get("required_years") is not None:
        req = experience_result["required_years"]
        cand = experience_result["candidate_years"]
        met = experience_result["meets_requirement"]
        icon = "✅" if met else "⚠️"
        st.info(f"{icon} **Experience:** JD requires {req}+ years — your resume shows ~{cand} years.")

    # Breakdown chart
    fig = go.Figure(go.Bar(
        x=[semantic_result["similarity_percent"], keyword_result["match_percent"]],
        y=["Semantic Similarity", "Keyword Match"],
        orientation="h",
        text=[f"{semantic_result['similarity_percent']}%", f"{keyword_result['match_percent']}%"],
        textposition="auto",
        marker_color=["#4C78A8", "#F58518"],
    ))
    fig.update_layout(
        xaxis_range=[0, 100],
        height=250,
        margin=dict(l=10, r=10, t=30, b=10),
        title="Score Breakdown",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Insights
    st.subheader("💡 Actionable Insights")
    for insight in insights:
        st.markdown(f"- {insight}")

    # Raw skill detail (collapsible, for transparency)
    with st.expander("See detected skills detail"):
        st.write("**Skills found in JD:**", ", ".join(keyword_result["jd_skills"]) or "None detected")
        st.write("**Matched in your resume:**", ", ".join(keyword_result["matched_skills"]) or "None")
        st.write("**Missing from your resume:**", ", ".join(keyword_result["missing_skills"]) or "None")
        if keyword_result.get("semantic_matched_skills"):
            st.write(
                "**Matched via semantic inference (not exact keywords):**",
                ", ".join(keyword_result["semantic_matched_skills"]),
            )

    # ---- Resume Quality / ATS Readiness (independent of this specific JD) ----
    with st.spinner("Checking resume quality (grammar, phrasing, formatting)..."):
        quality_report = compute_quality_report(resume_text, check_grammar=check_grammar)
        quality_insights = generate_quality_insights(quality_report)

    st.divider()
    st.subheader("📋 Resume Quality & ATS Readiness")
    st.caption("These checks are independent of the job description — they reflect general resume quality.")

    qscore = quality_report["quality_score"]
    st.metric("Resume Quality Score", f"{qscore}/100")

    for insight in quality_insights:
        st.markdown(f"- {insight}")

    with st.expander("See full quality check details"):
        st.write("**Contact info detected:**", quality_report["contact_info"])
        st.write("**Word count:**", quality_report["length"]["word_count"])
        st.write("**Bullets with quantified metrics:**",
                  f"{quality_report['quantification']['quantified_count']} / {quality_report['quantification']['total_bullets']}")
        if quality_report['quantification'].get('unquantified_examples'):
            st.write("**Bullets that could use a number/metric:**")
            for b in quality_report['quantification']['unquantified_examples']:
                st.markdown(f"  - {b}")
        if quality_report["weak_language_bullets"]:
            st.write("**Weak-phrasing bullets:**")
            for b in quality_report["weak_language_bullets"]:
                st.markdown(f"  - {b}")
        if quality_report["grammar"].get("available"):
            g = quality_report["grammar"]
            st.write(f"**Grammar/spelling issues found:** {g.get('total_found', 0)}")
            if g.get("filtered_technical_terms", 0) > 0:
                st.caption(f"({g['filtered_technical_terms']} additional flags were recognized technical terms and skipped)")
            for issue in g["issues"]:
                word_note = f" — *\"{issue['flagged_word']}\"*" if issue.get("flagged_word") else ""
                st.markdown(f"  - **{issue['category']}**{word_note}: {issue['message']}")
        elif check_grammar:
            st.write("Grammar check was unavailable (couldn't reach the check service — check your internet connection).")

st.divider()
st.caption(
    "Note: This tool gives directional guidance based on keyword and semantic overlap with the "
    "job description. It does not replicate any specific company's actual ATS software."
)
