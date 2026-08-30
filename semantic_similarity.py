"""
semantic_similarity.py
Computes semantic similarity between resume and JD using Sentence-BERT.
Model is loaded once and cached (see get_model()) to avoid reloading on every run.
"""

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

MODEL_NAME = "all-mpnet-base-v2"

_model_cache = {}


def get_model(model_name: str = MODEL_NAME) -> SentenceTransformer:
    """Load and cache the SBERT model so it's only loaded once per session."""
    if model_name not in _model_cache:
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


def chunk_text(text: str, max_words: int = 120) -> list:
    """
    Split long text into rough word-count chunks.
    Chunking (vs one giant embedding) gives slightly better signal because
    SBERT embeddings degrade for very long documents, and it lets us do
    a max-similarity comparison across sections instead of one blurred vector.
    """
    words = text.split()
    if not words:
        return []
    chunks = [
        " ".join(words[i:i + max_words])
        for i in range(0, len(words), max_words)
    ]
    return chunks


def split_into_sentences(text: str) -> list:
    """
    Rough sentence/bullet splitter for per-skill semantic checks. Splits on
    sentence-ending punctuation AND bullet-style line breaks, since resumes
    are mostly bullet points rather than full sentences.
    """
    import re
    # Split on newlines first (bullets), then on sentence-ending punctuation
    lines = re.split(r"[\n\r]+", text)
    sentences = []
    for line in lines:
        parts = re.split(r"(?<=[.!?])\s+", line.strip())
        sentences.extend(p.strip() for p in parts if len(p.strip()) > 8)  # skip tiny fragments
    return sentences


def find_skills_semantically(candidate_skills: list, resume_text: str,
                              model_name: str = MODEL_NAME, threshold: float = 0.42) -> set:
    """
    For abstract/soft skills that resist literal keyword matching (e.g.
    "Communication", "Data Analysis", "Problem Solving"), check whether ANY
    sentence/bullet in the resume is semantically close to the skill concept,
    even if no matching keyword or synonym phrase exists.

    threshold: cosine similarity cutoff (0-1). 0.42 is a starting point —
    tune based on false positive/negative rate you observe in testing.
    """
    model = get_model(model_name)
    sentences = split_into_sentences(resume_text)
    if not sentences or not candidate_skills:
        return set()

    sentence_embeddings = model.encode(sentences, convert_to_numpy=True)
    skill_embeddings = model.encode(candidate_skills, convert_to_numpy=True)

    sim_matrix = cosine_similarity(skill_embeddings, sentence_embeddings)
    best_per_skill = sim_matrix.max(axis=1)

    found = {
        skill for skill, score in zip(candidate_skills, best_per_skill)
        if score >= threshold
    }
    return found


def compute_semantic_similarity(jd_text: str, resume_text: str, model_name: str = MODEL_NAME) -> dict:
    """
    Compute semantic similarity between JD and resume.

    Strategy: chunk both texts, embed all chunks, then for each JD chunk find
    its best-matching resume chunk (max similarity). Average those best-matches
    to get a final score. This rewards resumes that cover each JD requirement
    somewhere, rather than penalizing them for unrelated sections diluting a
    single whole-document vector.
    """
    model = get_model(model_name)

    jd_chunks = chunk_text(jd_text)
    resume_chunks = chunk_text(resume_text)

    if not jd_chunks or not resume_chunks:
        return {"similarity_percent": 0.0, "chunk_scores": []}

    jd_embeddings = model.encode(jd_chunks, convert_to_numpy=True)
    resume_embeddings = model.encode(resume_chunks, convert_to_numpy=True)

    sim_matrix = cosine_similarity(jd_embeddings, resume_embeddings)  # shape: (jd_chunks, resume_chunks)

    best_match_per_jd_chunk = sim_matrix.max(axis=1)  # best resume match for each JD chunk
    overall_similarity = float(np.mean(best_match_per_jd_chunk))

    # Clip and rescale: raw cosine sim for unrelated text rarely goes below ~0.1-0.2,
    # so a small rescale makes the final percentage more intuitive/spread out.
    similarity_percent = round(max(0.0, min(1.0, overall_similarity)) * 100, 1)

    return {
        "similarity_percent": similarity_percent,
        "chunk_scores": best_match_per_jd_chunk.tolist(),
    }


if __name__ == "__main__":
    jd = "Looking for a backend engineer skilled in Python and cloud infrastructure to build scalable APIs."
    resume = "Software engineer with 4 years building scalable backend services in Python, deployed on AWS."
    print(compute_semantic_similarity(jd, resume))
