import os
import json
import time
from typing import List, Dict, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from dotenv import load_dotenv

load_dotenv()

class ExemplarSelector:
    """
    DAIL-SQL Style Dynamic In-Context Exemplar Selector (Task 2.5).
    Indexes the Spider training corpus (train_spider.json, N=7,000) using an in-memory
    TF-IDF n-gram index to retrieve structurally relevant (Question, SQL) demonstration
    pairs in < 3ms without remote LLM latency.
    """
    _instance = None

    def __init__(self, train_path: str = os.getenv("SPIDER_TRAIN_PATH", r"D:\spider_data\train_spider.json")):
        self.train_path = train_path
        self.examples: List[Dict] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self._is_initialized = False

    @classmethod
    def get_instance(cls, train_path: str = os.getenv("SPIDER_TRAIN_PATH", r"D:\spider_data\train_spider.json")):
        if cls._instance is None:
            cls._instance = cls(train_path)
            cls._instance.initialize()
        return cls._instance

    def initialize(self):
        if self._is_initialized:
            return

        if not os.path.exists(self.train_path):
            print(f"[WARN] ExemplarSelector: Training dataset not found at {self.train_path}. Exemplars disabled.")
            return

        start_t = time.perf_counter()
        with open(self.train_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        # Store deduplicated questions and their gold queries
        seen_questions = set()
        clean_data = []
        for item in raw_data:
            q = item.get("question", "").strip()
            sql = item.get("query", "").strip()
            if q and sql and q not in seen_questions:
                seen_questions.add(q)
                clean_data.append({
                    "question": q,
                    "sql": sql,
                    "db_id": item.get("db_id", "")
                })

        self.examples = clean_data
        questions = [ex["question"] for ex in self.examples]

        # Use unigram + bigram TF-IDF with sublinear term frequency
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True,
            min_df=2
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(questions)
        self._is_initialized = True

        init_ms = (time.perf_counter() - start_t) * 1000
        # Fast initialization log
        # print(f"[INFO] ExemplarSelector initialized ({len(self.examples)} training exemplars, {init_ms:.1f}ms).")

    def retrieve(self, query: str, k: int = 2) -> List[Dict]:
        """
        Retrieves top-k most structurally relevant training question-SQL pairs.
        Runs in ~1-3ms in pure local matrix operations.
        """
        if not self._is_initialized or not self.vectorizer or not self.examples:
            return []

        q_vec = self.vectorizer.transform([query])
        scores = self.tfidf_matrix.dot(q_vec.T).toarray().ravel()
        
        # Get top-k indices
        top_k_indices = np.argsort(scores)[::-1][:k]
        
        results = []
        for idx in top_k_indices:
            if scores[idx] > 0.05: # threshold to avoid completely irrelevant noise
                results.append(self.examples[idx])
        return results

    def format_exemplars(self, exemplars: List[Dict]) -> str:
        """
        Formats retrieved exemplars into clean, minimal SQL reference comments for CRP v2.
        """
        if not exemplars:
            return ""

        lines = [
            "/*",
            "=============================================================================",
            "REFERENCE SQL SYNTHESIS PATTERNS (FEW-SHOT DEMONSTRATIONS)",
            "Study the projection clauses, ordering, and subquery logic in these examples:",
            "============================================================================="
        ]
        
        for i, ex in enumerate(exemplars, 1):
            q_clean = ex["question"].strip()
            sql_clean = ex["sql"].strip().rstrip(";")
            lines.append(f"-- Example {i}:")
            lines.append(f"-- Question: {q_clean}")
            lines.append(f"{sql_clean};")
            lines.append("")

        lines.append("*/")
        return "\n".join(lines).strip()

exemplar_selector = ExemplarSelector.get_instance()
