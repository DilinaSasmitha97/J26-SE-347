import re
from collections import deque
from typing import Dict, List, Set, Tuple, Optional
from profiler import time_block, log_step

NEGATION_PATTERN = re.compile(
    r"\b(no|not|never|neither|nor|without|except|excluding|don\'t|doesn\'t|didn\'t)\b", 
    re.IGNORECASE
)

class RelationshipMapper:
    """
    State-of-the-Art Relational Graph & Multi-Hop Steiner-Tree Junction Engine (Task 4B / Stage 8A).
    
    Responsibilities:
    1. Parses detailed Foreign Key constraints from DDL and SQLite/MSSQL connections:
       (source_table, source_column) -> (target_table, target_column).
    2. Builds a relational graph G(V, E) of all tables and foreign key edges.
    3. Finds the Steiner Minimal Tree / multi-hop shortest path between disconnected terminal tables,
       with lexical intent edge weighting to disambiguate competing foreign keys.
    4. Identifies essential bridge/junction tables so they are never pruned.
    5. Injects explicit, intent-weighted, negation-guarded canonical JOIN skeletons into the prompt.
    """

    def __init__(self):
        pass

    def detect_negation_intent(self, nl_query: str) -> bool:
        """
        Detects whether natural language query expresses a negative or exclusion intent.
        When True, prevents inappropriate INNER JOIN guidance that would suppress anti-joins.
        """
        if not nl_query or not isinstance(nl_query, str):
            return False
        return bool(NEGATION_PATTERN.search(nl_query))

    def _tokenize_identifier(self, ident: str) -> List[str]:
        if not ident:
            return []
        s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', str(ident))
        s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s)
        return [t.lower() for t in re.findall(r'[a-zA-Z0-9]+', s) if t]

    def _score_edge_lexical_intent(self, edge: Dict[str, str], nl_tokens: Set[str]) -> int:
        """
        Calculates lexical relevance score for an edge given query tokens.
        Higher score = stronger alignment with user intent (e.g. DestAirport vs SourceAirport).
        """
        if not nl_tokens:
            return 0
        
        score = 0
        cols = [edge.get("from_col", ""), edge.get("to_col", "")]
        for col in cols:
            tokens = self._tokenize_identifier(col)
            for tok in tokens:
                if tok in nl_tokens and len(tok) >= 3:
                    score += 2
                elif any(t.startswith(tok) or tok.startswith(t) for t in nl_tokens if len(t) >= 4 and len(tok) >= 4):
                    score += 1
        return score

    def parse_foreign_keys_from_ddl(self, full_ddl: str) -> List[Dict[str, str]]:
        """
        Extracts exact foreign key definitions from DDL statements:
        Returns list of dicts:
        [
            {
                "from_table": "MODEL_LIST",
                "from_col": "Maker",
                "to_table": "CAR_MAKERS",
                "to_col": "Id"
            }, ...
        ]
        """
        relationships = []
        blocks = re.split(r'(?=CREATE\s+TABLE)', full_ddl, flags=re.IGNORECASE)

        for block in blocks:
            block = block.strip()
            if not block.upper().startswith("CREATE TABLE"):
                continue

            match = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`"\[\w\.\-\]]+)', block, re.IGNORECASE)
            if not match:
                continue

            raw_table_name = match.group(1).strip('`"[]')
            from_table = raw_table_name.split('.')[-1]

            # 1. Table-level FOREIGN KEY constraints:
            fk_pattern = re.compile(
                r'FOREIGN\s+KEY\s*\(\s*[`"\[]?([\w\-]+)[`"\]]?\s*\)\s*REFERENCES\s+[`"\[]?([\w\.\-]+)[`"\]]?\s*(?:\(\s*[`"\[]?([\w\-]+)[`"\]]?\s*\))?',
                re.IGNORECASE
            )
            for m in fk_pattern.finditer(block):
                from_col = m.group(1)
                to_table = m.group(2).split('.')[-1]
                to_col = m.group(3) if m.group(3) else from_col

                relationships.append({
                    "from_table": from_table,
                    "from_col": from_col,
                    "to_table": to_table,
                    "to_col": to_col
                })

            # 2. Inline column-level REFERENCES:
            inline_pattern = re.compile(
                r'[`"\[]?([\w\-]+)[`"\]]?\s+[\w\(\)\s]+?\s+REFERENCES\s+[`"\[]?([\w\.\-]+)[`"\]]?\s*(?:\(\s*[`"\[]?([\w\-]+)[`"\]]?\s*\))?',
                re.IGNORECASE
            )
            for line in block.split('\n'):
                line = line.strip()
                if line.upper().startswith(("FOREIGN KEY", "CONSTRAINT", "PRIMARY KEY")):
                    continue
                m_inline = inline_pattern.search(line)
                if m_inline:
                    from_col = m_inline.group(1)
                    to_table = m_inline.group(2).split('.')[-1]
                    to_col = m_inline.group(3) if m_inline.group(3) else from_col
                    if to_table != from_table:
                        relationships.append({
                            "from_table": from_table,
                            "from_col": from_col,
                            "to_table": to_table,
                            "to_col": to_col
                        })

        return relationships

    def parse_foreign_keys_from_sqlite(self, db_conn) -> List[Dict[str, str]]:
        """
        Directly queries SQLite catalog via PRAGMA foreign_key_list for 100% ground-truth accuracy.
        """
        relationships = []
        try:
            cursor = db_conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]

            for t_name in tables:
                cursor.execute(f"PRAGMA foreign_key_list('{t_name}')")
                for row in cursor.fetchall():
                    to_table = row[2]
                    from_col = row[3]
                    to_col = row[4]
                    if to_table and from_col:
                        relationships.append({
                            "from_table": t_name,
                            "from_col": from_col,
                            "to_table": to_table,
                            "to_col": to_col if to_col else from_col
                        })
        except Exception as e:
            log_step(f"Warning: SQLite foreign key PRAGMA failed: {e}", level="WARN")

        return relationships

    def build_relational_graph(self, relationships: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
        """
        Builds undirected adjacency list for bidirectional relational traversal.
        """
        adj: Dict[str, List[Dict[str, str]]] = {}

        for rel in relationships:
            t1 = rel["from_table"].lower()
            t2 = rel["to_table"].lower()

            if t1 not in adj:
                adj[t1] = []
            if t2 not in adj:
                adj[t2] = []

            # Forward edge
            adj[t1].append({
                "neighbor": t2,
                "neighbor_raw": rel["to_table"],
                "from_col": rel["from_col"],
                "to_col": rel["to_col"],
                "direction": "forward"
            })
            # Reverse edge (for joining in opposite direction)
            adj[t2].append({
                "neighbor": t1,
                "neighbor_raw": rel["from_table"],
                "from_col": rel["to_col"],
                "to_col": rel["from_col"],
                "direction": "reverse"
            })

        return adj

    def find_shortest_path(
        self, 
        graph: Dict[str, List[Dict[str, str]]], 
        start_table: str, 
        target_table: str, 
        nl_query: str = None,
        max_hops: int = 4
    ) -> Optional[List[Dict[str, str]]]:
        """
        BFS shortest path between two tables with intent-weighted edge tie-breaking.
        Returns list of edge steps, or None if unreachable.
        """
        start = start_table.lower()
        target = target_table.lower()

        if start == target or start not in graph or target not in graph:
            return None

        nl_tokens = set(re.findall(r'[a-zA-Z0-9]+', (nl_query or "").lower()))

        queue = deque([(start, [])])
        visited = {start}

        while queue:
            current, path = queue.popleft()

            if len(path) >= max_hops:
                continue

            # Sort edges so higher lexical intent edges are evaluated first
            edges = sorted(
                graph.get(current, []),
                key=lambda e: self._score_edge_lexical_intent(e, nl_tokens),
                reverse=True
            )

            for edge in edges:
                neighbor = edge["neighbor"]
                step = {
                    "from_table": current,
                    "to_table": neighbor,
                    "to_table_raw": edge["neighbor_raw"],
                    "from_col": edge["from_col"],
                    "to_col": edge["to_col"]
                }
                new_path = path + [step]

                if neighbor == target:
                    return new_path

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, new_path))

        return None

    def resolve_multi_hop_bridges(
        self,
        terminal_tables: Set[str],
        schema_meta: str,
        db_conn=None,
        nl_query: str = None,
        max_hops: int = 4
    ) -> Tuple[Set[str], List[Dict[str, str]]]:
        """
        Identifies intermediate bridge tables connecting disconnected terminal tables,
        and computes the exact intent-weighted join path sequence.
        
        Returns:
            Tuple[Set[str], List[Dict]]: (bridge_table_names, join_path_steps)
        """
        if db_conn is not None:
            relationships = self.parse_foreign_keys_from_sqlite(db_conn)
            if not relationships:
                relationships = self.parse_foreign_keys_from_ddl(schema_meta)
        else:
            relationships = self.parse_foreign_keys_from_ddl(schema_meta)

        graph = self.build_relational_graph(relationships)
        terminals = [t.lower() for t in terminal_tables if t.lower() in graph]

        bridge_tables = set()
        all_paths: List[Dict[str, str]] = []

        # Find paths between every pair of disconnected terminal tables
        for i in range(len(terminals)):
            for j in range(i + 1, len(terminals)):
                t1 = terminals[i]
                t2 = terminals[j]

                # Check if already directly connected by 1 hop
                direct = any(edge["neighbor"] == t2 for edge in graph.get(t1, []))
                if not direct:
                    path = self.find_shortest_path(graph, t1, t2, nl_query=nl_query, max_hops=max_hops)
                    if path:
                        for step in path:
                            all_paths.append(step)
                            bridge_tables.add(step["to_table_raw"])
                        bridge_tables.discard(t2)

        return bridge_tables, all_paths

    def format_canonical_join_skeleton(
        self, 
        join_paths: List[Dict[str, str]], 
        nl_query: str = None
    ) -> str:
        """
        Formats discovered relational join paths into compact, actionable SQL prompt guidance.
        Incorporates negation guards to prevent INNER JOIN bias on negative queries.
        """
        if not join_paths:
            return ""

        is_negation = self.detect_negation_intent(nl_query) if nl_query else False

        seen = set()
        unique_conditions = []

        for p in join_paths:
            t1 = p['from_table']
            c1 = p['from_col']
            t2 = p['to_table']
            c2 = p['to_col']
            cond = f"{t1}.{c1} = {t2}.{c2}"
            cond_rev = f"{t2}.{c2} = {t1}.{c1}"
            if cond not in seen and cond_rev not in seen:
                seen.add(cond)
                unique_conditions.append(cond)

        if not unique_conditions:
            return ""

        # Limit to top 2-3 most relevant relationships to stay strictly within token budget (< 35 tokens)
        unique_conditions = unique_conditions[:3]

        if is_negation:
            lines = [
                "/* Relational Guidance (Negative / Exclusion Condition):",
                "-- Notice: Exclusion intent detected; use NOT IN, NOT EXISTS, or EXCEPT (do NOT force INNER JOIN)."
            ]
            for cond in unique_conditions:
                lines.append(f"-- Key Relationship: {cond}")
            lines.append("*/")
            return "\n".join(lines)
        else:
            lines = [
                "/* Relational Guidance (Foreign Key Joins):",
                "-- Prefer explicit JOIN over scalar subqueries when combining multi-row relationships."
            ]
            for cond in unique_conditions:
                lines.append(f"-- Join Condition: {cond}")
            lines.append("*/")
            return "\n".join(lines)

    def format_join_path_hints(self, join_paths: List[Dict[str, str]], nl_query: str = None) -> str:
        """
        Backwards-compatible wrapper routing to format_canonical_join_skeleton.
        """
        return self.format_canonical_join_skeleton(join_paths, nl_query=nl_query)

    def get_subgraph_join_paths(
        self,
        selected_tables: Set[str],
        schema_meta: str,
        nl_query: str = None,
        db_conn=None
    ) -> str:
        """
        Extracts foreign key relationships between any pair of tables in selected_tables.
        Strict Minimal Gating: If selected_tables < 2, returns empty string immediately.
        """
        if not selected_tables or len(selected_tables) < 2:
            return ""

        if db_conn is not None:
            relationships = self.parse_foreign_keys_from_sqlite(db_conn)
            if not relationships:
                relationships = self.parse_foreign_keys_from_ddl(schema_meta)
        else:
            relationships = self.parse_foreign_keys_from_ddl(schema_meta)

        if not relationships:
            return ""

        norm_selected = {t.lower(): t for t in selected_tables}
        nl_tokens = set(re.findall(r'[a-zA-Z0-9]+', (nl_query or "").lower()))

        subgraph_paths = []
        for rel in relationships:
            f_norm = rel["from_table"].lower()
            t_norm = rel["to_table"].lower()
            if f_norm in norm_selected and t_norm in norm_selected:
                subgraph_paths.append({
                    "from_table": norm_selected[f_norm],
                    "from_col": rel["from_col"],
                    "to_table": norm_selected[t_norm],
                    "to_col": rel["to_col"]
                })

        # Sort by lexical intent score
        subgraph_paths.sort(
            key=lambda p: self._score_edge_lexical_intent(p, nl_tokens),
            reverse=True
        )

        return self.format_canonical_join_skeleton(subgraph_paths, nl_query=nl_query)

relationship_mapper = RelationshipMapper()

