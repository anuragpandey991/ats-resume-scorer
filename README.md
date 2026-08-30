# ATS Resume Scorer

Scores a resume against a job description using a hybrid approach:
- **JD auto-cleaning** — strips benefits/EEO/legal boilerplate and job-board metadata footers before scoring, so they don't dilute the semantic similarity score
- **Semantic similarity** via Sentence-BERT (`all-mpnet-base-v2`)
- **Keyword/skill overlap** via a curated skill taxonomy (with synonym + semantic fallback for soft skills)
- **Experience-level matching** — extracts required years from the JD and estimates candidate years from resume date ranges
- **Resume quality / ATS readiness** — weak phrasing, passive voice, quantification (with specific bullet examples), contact info, length, and real grammar checking (LanguageTool API, filtered against a technical-term allowlist to avoid false positives on tool/library names)

Outputs a final weighted match score plus a separate resume-quality score, each with specific, actionable feedback.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

First run will download the SBERT model (~420MB) — needs internet access, only happens once.

## Run

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Upload a resume (PDF/DOCX), paste a job description, click Analyze.

## Project structure

```
ats_scorer/
├── app.py                    # Streamlit UI — entry point
├── text_extraction.py        # PDF/DOCX -> cleaned text
├── keyword_matcher.py        # Skill taxonomy matching (exact + fuzzy)
├── semantic_similarity.py    # SBERT embedding + cosine similarity
├── experience_matcher.py     # Required vs. candidate years of experience
├── jd_cleaner.py             # Strips JD boilerplate (benefits/EEO/metadata footer) before scoring
├── resume_quality.py          # Weak phrasing, passive voice, grammar (LanguageTool), formatting checks
├── quality_insight_generator.py  # Converts quality report into readable feedback
├── scoring_engine.py         # Weighted score combination + experience penalty
├── insight_generator.py      # Converts scores into readable feedback
├── data/
│   └── skills_taxonomy.json  # Curated skill list (edit to expand coverage)
└── requirements.txt
```

## Tuning

- **Scoring weights**: edit `WEIGHT_SEMANTIC` / `WEIGHT_KEYWORD` in `scoring_engine.py` (default 55/45).
- **Skill taxonomy**: add more skills/categories to `data/skills_taxonomy.json` — no code changes needed.
- **Fuzzy match strictness**: `FUZZY_THRESHOLD` in `keyword_matcher.py` (default 85, higher = stricter).
- **Skill synonyms**: add alternate phrasings to `data/skill_synonyms.json` (e.g. "data analytics" → counts as "Data Analysis"). Catches paraphrasing that exact/fuzzy name matching alone would miss.
- **Semantic fallback for soft skills**: `SEMANTIC_FALLBACK_SKILLS` in `keyword_matcher.py` — abstract skills (Communication, Data Analysis, Leadership, etc.) get one more check via SBERT similarity against resume sentences if exact/synonym matching misses them. Restricted to soft skills only — concrete tools (AWS, Docker) are deliberately excluded to avoid false positives. Tune the similarity cutoff via the `threshold` param in `find_skills_semantically()` (semantic_similarity.py, default 0.42).
- **Resume quality scoring**: deduction weights (weak language, passive voice, pronouns, quantification, missing contact info, grammar issue count) are all tunable constants inside `compute_quality_report()` in `resume_quality.py`.
- **Grammar checking**: uses the free public LanguageTool API (`https://api.languagetool.org/v2/check`). Needs internet access at runtime; the free tier has rate limits, so it's toggleable in the UI. Fails gracefully (skips grammar results, keeps everything else) if unreachable. Spelling flags are cross-checked against `data/known_technical_terms.json` + the skill taxonomy first, so tool/library names (PySpark, LangGraph, etc.) aren't falsely flagged as typos.
- **JD auto-cleaning**: `BOILERPLATE_PHRASES` and `METADATA_FIELD_LABELS` in `jd_cleaner.py` control what gets stripped. Conservative by design — only removes paragraphs that confidently match known patterns, and shows exactly what was removed in an expandable UI panel before scoring.
- **Experience penalty**: `MAX_EXPERIENCE_PENALTY` / `PENALTY_PER_MISSING_YEAR` in `scoring_engine.py`.

## Known limitations (v1 scope)

- No OCR — scanned/image-based PDFs won't extract text.
- No section-aware parsing (Experience vs Skills vs Education treated as one text blob).
- Experience matching relies on finding clear date ranges (e.g. "Jan 2020 - Present") in the resume text —
  experience described without explicit dates won't be counted.
- JD is pasted as text only (no JD file upload) to keep scope tight.

These were deliberately deferred to keep this a ~10-12 hour build. See project notes for the fuller roadmap (KeyBERT keyword extraction, section parsing, structure/formatting checks).
