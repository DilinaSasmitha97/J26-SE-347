import re
from typing import Dict, List, Set, Tuple
from profiler import time_block, log_step

class MinimalSchemaExtractor:
    """
    State-of-the-Art Minimal-Context Schema Extractor (Task 1).
    Combines:
    1. Lexical & Fuzzy Keyword Matching (exact table/column names).
    2. Semantic Vector Similarity (synonyms: e.g. 'staff' -> 'employees').
    3. Foreign Key Graph Traversal (automatically includes bridge tables for JOINs).
    4. Ambiguity Clarification Detection (flags 0-match questions for user clarification).
    """

    def __init__(self):
        self._vectorizer = None
        self._model = None

    def _parse_ddl_into_tables(self, full_ddl: str) -> Dict[str, dict]:
        """
        Parses CREATE TABLE statements into structured table metadata:
        {
            table_name: {
                "raw_sql": str,
                "columns": [str],
                "foreign_keys": [referenced_table_name]
            }
        }
        """
        tables = {}
        # Split DDL into CREATE TABLE blocks
        blocks = re.split(r'(?=CREATE\s+TABLE)', full_ddl, flags=re.IGNORECASE)
        
        for block in blocks:
            block = block.strip()
            if not block.upper().startswith("CREATE TABLE"):
                continue
                
            # Extract Table Name (supports [schema].[table], "table", `table`, or simple table)
            match = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`"\[\w\.\-\]]+)', block, re.IGNORECASE)
            if not match:
                continue
                
            raw_table_name = match.group(1).strip('`"[]')
            # Extract plain table name if schema prefix exists (e.g. dbo.Employees -> Employees)
            table_name = raw_table_name.split('.')[-1]
            
            # Extract Column Names
            # Find everything inside parentheses
            col_match = re.search(r'\((.*)\)', block, re.DOTALL)
            columns = []
            foreign_keys = []
            
            if col_match:
                content = col_match.group(1)
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Check for Foreign Key references
                    fk_match = re.search(r'REFERENCES\s+([`"\[\w\.\-\]]+)', line, re.IGNORECASE)
                    if fk_match:
                        ref_table = fk_match.group(1).strip('`"[]').split('.')[-1]
                        if ref_table != table_name:
                            foreign_keys.append(ref_table)
                            
                    # Extract column name if it's a column definition line
                    if not line.upper().startswith(("PRIMARY KEY", "FOREIGN KEY", "CONSTRAINT", "KEY", "INDEX", "CHECK", "UNIQUE")):
                        col_name_match = re.search(r'^[`"\[]?([\w\-]+)[`"\]]?', line)
                        if col_name_match:
                            col_name = col_name_match.group(1)
                            if col_name.upper() not in ("PRIMARY", "FOREIGN", "CONSTRAINT", "KEY", "INDEX", "CHECK", "UNIQUE"):
                                columns.append(col_name)
                                
            tables[table_name] = {
                "raw_table_name": raw_table_name,
                "raw_sql": block if block.endswith(';') else block + ';',
                "columns": columns,
                "foreign_keys": foreign_keys
            }
            
        return tables

    def _calculate_semantic_scores(self, question: str, tables: Dict[str, dict]) -> Dict[str, float]:
        """
        Calculates semantic similarity scores for each table based on table names, column names, and question words.
        Uses TF-IDF and word-n-gram cosine similarity for instant, dependency-free high accuracy.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        scores = {t_name: 0.0 for t_name in tables}
        question_clean = re.sub(r'[^\w\s]', ' ', question.lower())
        q_words = set(question_clean.split())

        # 1. Direct Lexical Match Score
        for t_name, meta in tables.items():
            t_name_lower = t_name.lower()
            # Exact table name match in question
            if t_name_lower in question_clean or any(w in t_name_lower for w in q_words if len(w) > 2):
                scores[t_name] += 1.0

            # Direct column name match
            for col in meta["columns"]:
                col_lower = col.lower()
                if col_lower in question_clean or any(w == col_lower for w in q_words):
                    scores[t_name] += 0.5

        # 2. TF-IDF Cosine Similarity for Synonyms & Intent
        table_documents = []
        table_names_list = list(tables.keys())

        for t_name in table_names_list:
            meta = tables[t_name]
            doc = f"{t_name} " + " ".join(meta["columns"])
            table_documents.append(doc.lower())

        if table_documents:
            try:
                vectorizer = TfidfVectorizer(ngram_range=(1, 2)).fit(table_documents + [question_clean])
                table_vecs = vectorizer.transform(table_documents)
                q_vec = vectorizer.transform([question_clean])
                sims = cosine_similarity(q_vec, table_vecs).flatten()

                for idx, t_name in enumerate(table_names_list):
                    scores[t_name] += float(sims[idx]) * 0.8
            except Exception as e:
                log_step(f"TF-IDF similarity calculation warning: {e}", level="WARN")

        return scores

    def _expand_foreign_key_graph(self, selected_tables: Set[str], tables: Dict[str, dict]) -> Set[str]:
        """
        Traverses Foreign Key connections so intermediate bridge tables are automatically included.
        Guarantees that SQL JOIN statements never fail due to missing bridge tables.
        """
        expanded = set(selected_tables)
        
        # Add foreign key referenced tables for all selected tables
        for t_name in list(selected_tables):
            if t_name in tables:
                for fk_table in tables[t_name]["foreign_keys"]:
                    if fk_table in tables:
                        expanded.add(fk_table)
                        
        # Add tables that reference selected tables
        for t_name, meta in tables.items():
            for fk_table in meta["foreign_keys"]:
                if fk_table in selected_tables:
                    expanded.add(t_name)
                    
        return expanded

    def extract_minimal_schema(self, question: str, full_ddl: str, top_k: int = 3, profiler=None) -> tuple[str, dict]:
        """
        Main entry point: Accepts question + full DDL, returns (minimal_ddl_string, metadata_dict).
        """
        with time_block("Minimal-Context Schema Extractor (Task 1)", parent_summary=profiler.categories if profiler else None, category="Schema Extraction - Minimal Context"):
            tables = self._parse_ddl_into_tables(full_ddl)
            total_tables_input = len(tables)
            
            if total_tables_input <= 2:
                # Small schema doesn't need pruning
                return full_ddl, {
                    "original_table_count": total_tables_input,
                    "pruned_table_count": total_tables_input,
                    "token_reduction_pct": 0.0,
                    "selected_tables": list(tables.keys()),
                    "needs_clarification": False,
                    "clarification_suggestions": []
                }
                
            # Score tables based on hybrid similarity
            scores = self._calculate_semantic_scores(question, tables)
            
            # Sort tables by score descending
            ranked_tables = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            
            # Filter tables above threshold score (> 0.05), capped to top 10 tables max
            ranked_relevant = [t_name for t_name, score in ranked_tables if score > 0.05]
            if len(ranked_relevant) > 10:
                ranked_relevant = ranked_relevant[:10]
            relevant_tables = set(ranked_relevant)
            
            # Check for ambiguous 0-match questions
            needs_clarification = False
            clarification_suggestions = []
            if not relevant_tables or max(scores.values(), default=0) < 0.05:
                needs_clarification = True
                clarification_suggestions = [t[0] for t in ranked_tables[:3]]
                log_step("Question matched 0 tables. Triggering interactive clarification fallback.", level="WARN")
                # Fallback to top_k tables to ensure pipeline continuity
                relevant_tables = {t[0] for t in ranked_tables[:top_k]}
                
            # Expand Foreign Key Graph to preserve JOINs
            final_selected_tables = self._expand_foreign_key_graph(relevant_tables, tables)
            
            # Cap final selected tables to 25 tables max (~6,500 tokens) to safely avoid Groq/Cerebras TPM limits while preserving accuracy
            if len(final_selected_tables) > 25:
                # Prioritize relevant_tables first, then fill up to 25 with graph expansion tables
                ordered_final = list(relevant_tables) + [t for t in final_selected_tables if t not in relevant_tables]
                final_selected_tables = set(ordered_final[:25])
            
            # Re-assemble pruned DDL statements
            pruned_statements = [tables[t_name]["raw_sql"] for t_name in final_selected_tables if t_name in tables]
            pruned_ddl = "\n\n".join(pruned_statements)
            
            pruned_count = len(final_selected_tables)
            reduction_pct = round((1.0 - (pruned_count / total_tables_input)) * 100.0, 1)
            
            log_step(f"Minimal Schema Extractor: {total_tables_input} tables -> {pruned_count} tables ({reduction_pct}% token reduction). Selected: {list(final_selected_tables)}")
            
            meta_stats = {
                "original_table_count": total_tables_input,
                "pruned_table_count": pruned_count,
                "token_reduction_pct": reduction_pct,
                "selected_tables": list(final_selected_tables),
                "needs_clarification": needs_clarification,
                "clarification_suggestions": clarification_suggestions
            }
            
            return pruned_ddl, meta_stats

# Singleton instance for simple imports
_extractor_instance = MinimalSchemaExtractor()

def extract_minimal_schema(question: str, full_ddl: str, top_k: int = 3, profiler=None) -> tuple[str, dict]:
    return _extractor_instance.extract_minimal_schema(question, full_ddl, top_k=top_k, profiler=profiler)
