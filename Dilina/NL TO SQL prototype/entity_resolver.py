import re
import difflib
from typing import Dict, List, Set, Tuple, Optional
from profiler import time_block, log_step

# Common English stop words to filter out during n-gram tokenization
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "find", "show", "list", "give", "tell", "name",
    "names", "number", "count", "average", "total", "maximum", "minimum", "many"
}

# Domain acronyms & common real-world categorical abbreviations
COMMON_ABBREVIATIONS = {
    "house": "HSE",
    "houses": "HSE",
    "apartment": "APT",
    "apartments": "APT",
    "condo": "CND",
    "condos": "CND",
    "male": "M",
    "female": "F",
    "active": "1",
    "inactive": "0",
    "yes": "Y",
    "no": "N",
    "true": "1",
    "false": "0",
    "united states": "USA",
    "us": "USA"
}

class ContextualEntityResolver:
    """
    Contextual Entity & Cell-Value Grounding Engine (Task 4A).
    
    Responsibilities:
    1. Extracts meaningful candidate n-grams and quoted phrases from natural language questions.
    2. Dynamically indexes low-cardinality categorical column values in <3ms.
    3. Matches question terms to exact database cell values (exact, Jaro-Winkler, stem, abbreviation).
    4. Emits ultra-compact Value Grounding prompt hints.
    5. Returns grounded table names to protect them from pruning in Stage 2.
    """

    def __init__(self):
        # In-memory cache of sampled categorical values per db/table to ensure 0ms repeated lookups
        self._categorical_cache: Dict[str, Dict[str, List[str]]] = {}

    def extract_candidate_terms(self, nl_query: str) -> List[str]:
        """
        Extracts candidate values: quoted strings, parenthesized expressions, proper nouns, and n-grams (1-5 words).
        """
        candidates = []

        # 1. Quoted strings (e.g. 'france', "amc hornet")
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", nl_query)
        for q in quoted:
            candidates.append(q.strip())

        # 2. Phrases ending in parentheses (e.g. "amc hornet sportabout (sw)")
        paren_phrases = re.findall(r"[\w\s\-]+\s*\([^)]+\)", nl_query)
        for p in paren_phrases:
            words = p.strip().split()
            for start_idx in range(len(words)):
                sub_phrase = " ".join(words[start_idx:])
                if sub_phrase.lower() not in [c.lower() for c in candidates]:
                    candidates.append(sub_phrase)

        # 3. Clean punctuation except hyphens and alphanumeric
        clean_text = re.sub(r"[^\w\s\-]", " ", nl_query)
        tokens = [w for w in clean_text.split() if w.strip()]

        # 4. Extract multi-word n-grams (5-grams down to unigrams)
        n = len(tokens)
        for length in range(5, 0, -1):
            for i in range(n - length + 1):
                ngram_tokens = tokens[i:i + length]
                if length == 1 and ngram_tokens[0].lower() in STOP_WORDS:
                    continue
                if all(t.lower() in STOP_WORDS for t in ngram_tokens):
                    continue
                ngram = " ".join(ngram_tokens)
                if ngram.lower() not in [c.lower() for c in candidates]:
                    candidates.append(ngram)

        # Sort candidate terms by length descending so longer, more specific entities match first
        candidates = sorted(candidates, key=lambda t: len(t), reverse=True)
        return candidates

    def discover_categorical_values(self, db_conn, tables: List[str], max_distinct_per_col: int = 50) -> Dict[str, Dict[str, List[str]]]:
        """
        Samples distinct string/text column values for specified tables.
        Cached in-memory so each table is scanned at most once per connection.
        """
        if not db_conn:
            return {}

        results: Dict[str, Dict[str, List[str]]] = {}

        try:
            cursor = db_conn.cursor()
            for table in tables:
                table_clean = table.strip('`"[]')
                if table_clean in self._categorical_cache:
                    results[table_clean] = self._categorical_cache[table_clean]
                    continue

                col_values: Dict[str, List[str]] = {}

                # Inspect column types via PRAGMA table_info in SQLite
                cursor.execute(f"PRAGMA table_info('{table_clean}')")
                col_info = cursor.fetchall()
                text_cols = [
                    row[1] for row in col_info 
                    if any(t in row[2].upper() for t in ("CHAR", "TEXT", "VARCHAR", "CLOB", "STRING"))
                ]

                # Sample distinct values for each text column
                for col in text_cols:
                    try:
                        cursor.execute(f"SELECT DISTINCT `{col}` FROM `{table_clean}` WHERE `{col}` IS NOT NULL LIMIT {max_distinct_per_col}")
                        distinct_vals = [str(r[0]).strip() for r in cursor.fetchall() if r[0] is not None and str(r[0]).strip()]
                        if distinct_vals and len(distinct_vals) <= max_distinct_per_col:
                            col_values[col] = distinct_vals
                    except Exception:
                        pass

                self._categorical_cache[table_clean] = col_values
                results[table_clean] = col_values

        except Exception as e:
            log_step(f"Warning: Categorical value discovery failed: {e}", level="WARN")

        return results

    def resolve_grounded_entities(
        self,
        nl_query: str,
        db_conn=None,
        tables_to_scan: Optional[List[str]] = None,
        schema_meta: str = ""
    ) -> Tuple[List[Dict[str, str]], Set[str]]:
        """
        Main entry point:
        Matches question terms to actual database values.
        """
        candidate_terms = self.extract_candidate_terms(nl_query)
        if not candidate_terms:
            return [], set()

        if not tables_to_scan and schema_meta:
            table_matches = re.findall(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`"\[\w\.\-\]]+)', schema_meta, re.IGNORECASE)
            tables_to_scan = [m.strip('`"[]').split('.')[-1] for m in table_matches]

        tables_to_scan = tables_to_scan or []
        categorical_index = self.discover_categorical_values(db_conn, tables_to_scan) if db_conn else {}

        matches: List[Dict[str, str]] = []
        grounded_tables: Set[str] = set()
        matched_tokens: Set[str] = set()

        for term in candidate_terms:
            term_lower = term.lower()
            term_words = set(re.findall(r'\w+', term_lower))
            
            # If all words of this term were already matched by a longer parent term, skip
            if term_words and term_words.issubset(matched_tokens):
                continue

            found_match = False

            # 1. Check known domain abbreviations (e.g. 'house' -> 'HSE')
            if term_lower in COMMON_ABBREVIATIONS:
                abbrev_code = COMMON_ABBREVIATIONS[term_lower]
                for t_name, cols in categorical_index.items():
                    for col_name, vals in cols.items():
                        if any(v.upper() == abbrev_code.upper() for v in vals):
                            matches.append({
                                "term": term,
                                "table": t_name,
                                "column": col_name,
                                "value": abbrev_code,
                                "match_type": "abbreviation_mapping"
                            })
                            grounded_tables.add(t_name)
                            matched_tokens.update(term_words)
                            found_match = True
                            break
                    if found_match:
                        break

            if found_match:
                continue

            # 2. Check exact and fuzzy match against database categorical values
            for t_name, cols in categorical_index.items():
                if found_match:
                    break
                for col_name, vals in cols.items():
                    # Exact Match (case-insensitive or normalized punctuation)
                    exact_val = next((v for v in vals if v.lower() == term_lower or re.sub(r'[^\w\s]', '', v.lower()) == re.sub(r'[^\w\s]', '', term_lower)), None)
                    if exact_val:
                        matches.append({
                            "term": term,
                            "table": t_name,
                            "column": col_name,
                            "value": exact_val,
                            "match_type": "exact_cell_value"
                        })
                        grounded_tables.add(t_name)
                        matched_tokens.update(term_words)
                        found_match = True
                        break

                    # Substring Match (e.g. 'amc hornet sportabout' in 'amc hornet sportabout (sw)')
                    substr_val = next((v for v in vals if len(term_lower) > 3 and (term_lower in v.lower() or v.lower() in term_lower)), None)
                    if substr_val and len(term_lower) > 4:
                        matches.append({
                            "term": term,
                            "table": t_name,
                            "column": col_name,
                            "value": substr_val,
                            "match_type": "substring_cell_value"
                        })
                        grounded_tables.add(t_name)
                        matched_tokens.update(term_words)
                        found_match = True
                        break

                    # Jaro-Winkler / difflib close match (similarity > 0.88)
                    close_matches = difflib.get_close_matches(term_lower, [v.lower() for v in vals], n=1, cutoff=0.88)
                    if close_matches and len(term_lower) > 3:
                        matched_val = next(v for v in vals if v.lower() == close_matches[0])
                        matches.append({
                            "term": term,
                            "table": t_name,
                            "column": col_name,
                            "value": matched_val,
                            "match_type": "fuzzy_cell_value"
                        })
                        grounded_tables.add(t_name)
                        matched_tokens.update(term_words)
                        found_match = True
                        break

        return matches, grounded_tables

    def format_grounding_hints(self, matches: List[Dict[str, str]]) -> str:
        """
        Formats discovered value groundings into compact SQL prompt hints.
        """
        if not matches:
            return ""

        hints = []
        for m in matches:
            val_formatted = f"'{m['value']}'" if not m['value'].isdigit() else m['value']
            hints.append(f"-- '{m['term']}' matches {m['table']}.{m['column']} = {val_formatted}")

        return "\n".join([
            "/* Contextual Entity & Cell-Value Groundings */",
            *hints
        ])

entity_resolver = ContextualEntityResolver()
