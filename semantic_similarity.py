"""
semantic_similarity.py
Computes semantic similarity between resume and JD using Sentence-BERT.
"""

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re

MODEL_NAME = "all-mpnet-base-v2"  # for tight-memory deployments, consider "all-MiniLM-L6-v2" instead

_model_cache = {}


def get_model(model_name: str = MODEL_NAME) -> SentenceTransformer:
    if model_name not in _model_cache:
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


def chunk_text(text: str, max_words: int = 120) -> list:
    words = text.split()
    if not words:
        return []
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]


def split_into_sentences(text: str) -> list:
    lines = re.split(r"[\n\r]+", text)
    sentences = []
    for line in lines:
        parts = re.split(r"(?<=[.!?])\s+", line.strip())
        sentences.extend(p.strip() for p in parts if len(p.strip()) > 8)
    return sentences


def compute_semantic_similarity(jd_text: str, resume_text: str, model_name: str = MODEL_NAME) -> dict:
    model = get_model(model_name)
    jd_chunks = chunk_text(jd_text)
    resume_chunks = chunk_text(resume_text)

    if not jd_chunks or not resume_chunks:
        return {"similarity_percent": 0.0, "chunk_scores": []}

    jd_embeddings = model.encode(jd_chunks, convert_to_numpy=True)
    resume_embeddings = model.encode(resume_chunks, convert_to_numpy=True)

    sim_matrix = cosine_similarity(jd_embeddings, resume_embeddings)
    best_match_per_jd_chunk = sim_matrix.max(axis=1)
    overall_similarity = float(np.mean(best_match_per_jd_chunk))
    similarity_percent = round(max(0.0, min(1.0, overall_similarity)) * 100, 1)

    return {"similarity_percent": similarity_percent, "chunk_scores": best_match_per_jd_chunk.tolist()}


def find_skills_semantically(candidate_skills: list, resume_text: str,
                              model_name: str = MODEL_NAME, threshold: float = 0.42) -> set:
    """
    For abstract/soft skills that resist literal keyword matching, check
    whether ANY sentence/bullet in the resume is semantically close to the
    skill concept, even with no matching keyword or synonym phrase.
    """
    model = get_model(model_name)
    sentences = split_into_sentences(resume_text)
    if not sentences or not candidate_skills:
        return set()

    sentence_embeddings = model.encode(sentences, convert_to_numpy=True)
    skill_embeddings = model.encode(candidate_skills, convert_to_numpy=True)

    sim_matrix = cosine_similarity(skill_embeddings, sentence_embeddings)
    best_per_skill = sim_matrix.max(axis=1)

    return {skill for skill, score in zip(candidate_skills, best_per_skill) if score >= threshold}


if __name__ == "__main__":
    jd = "Looking for a backend engineer skilled in Python and cloud infrastructure to build scalable APIs."
    resume = "Software engineer with 4 years building scalable backend services in Python, deployed on AWS."
    print(compute_semantic_similarity(jd, resume))
