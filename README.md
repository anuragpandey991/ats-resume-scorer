# ATS Resume Scorer

Scores a resume against a job description using a hybrid approach:
- **JD auto-cleaning** — strips benefits/EEO/metadata footer boilerplate before scoring
- **Semantic similarity** via Sentence-BERT (`all-mpnet-base-v2`)
- **Keyword/skill overlap** via a curated skill taxonomy, with synonym + semantic fallback for soft skills
- **Experience-level matching** — section-aware: only scans the resume's actual Work Experience block, so education/project dates are never miscounted as work experience
- **Resume quality / ATS readiness** — weak phrasing, passive voice, quantification (with specific bullet examples), contact info, length, and real grammar checking (LanguageTool API), with false-positive filtering for both technical terms and the candidate's own name

Outputs a final weighted match score plus a separate resume-quality score, each split into **strengths** and **improvements** rather than one flat list, and shown across a tabbed dashboard.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Project structure

```
ats_scorer/
├── app.py                        # Streamlit UI (tabs: Overview / Skills / Quality)
├── text_extraction.py            # PDF/DOCX -> cleaned text (x_tolerance=1 fixes merged-word PDF bug)
├── keyword_matcher.py             # Skill taxonomy matching (exact + fuzzy + synonyms + semantic fallback)
├── semantic_similarity.py         # SBERT embedding + cosine similarity
├── experience_matcher.py          # Section-aware: only scans Work Experience block for dates
├── jd_cleaner.py                  # Strips JD boilerplate before scoring
├── resume_quality.py              # Weak phrasing, passive voice, grammar (LanguageTool), formatting
├── scoring_engine.py              # Weighted score + experience penalty + friendly verdict tiers
├── insight_generator.py           # Strengths/improvements split, JD-match insights
├── quality_insight_generator.py   # Strengths/improvements split, quality insights
├── data/
│   ├── skills_taxonomy.json
│   ├── skill_synonyms.json
│   └── known_technical_terms.json # Grammar false-positive allowlist
└── requirements.txt
```

## Known fixes worth knowing about

- **PDF word-merging bug**: some PDFs (justified/tight-kerned layouts) lose spaces between words with pdfplumber's default settings, producing garbage like "RandomForestmodelusing". Fixed via `x_tolerance=1` in `extract_text_from_pdf`.
- **Experience miscounting bug**: a naive whole-document date-range scan picks up Education section dates (e.g. a 4-year degree range) as if they were work experience. Fixed via `extract_work_experience_text()`, which isolates only the actual Work Experience section before counting.
- **Grammar false positives**: LanguageTool's dictionary doesn't know technical terms (PySpark, LangGraph) or the candidate's own name — both are filtered out via `data/known_technical_terms.json` + first-line name detection.

## Known limitations (v1 scope)

- No OCR — scanned/image-based PDFs won't extract text.
- Experience extraction relies on a recognizable "Work Experience" section header; unusually formatted resumes fall back to whole-document scanning.
- JD is pasted as text only (no JD file upload).
