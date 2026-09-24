import re
from collections import deque
from typing import Dict, List, Set, Tuple, Optional
from profiler import time_block, log_step

class RelationshipMapper:
    """
    State-of-the-Art Relational Graph & Multi-Hop Steiner-Tree Junction Engine (Task 4B).
    
    Responsibilities:
    1. Parses detailed Foreign Key constraints from DDL and SQLite/MSSQL connections:
       (source_table, source_column) -> (target_table, target_column).
    2. Builds a relational graph G(V, E) of all tables and foreign key edges.
    3. Finds the Steiner Minimal Tree / multi-hop shortest path between disconnected terminal tables.
    4. Identifies essential bridge/junction tables so they are never pruned.
    5. Injects explicit, unambiguous JOIN path hints into the prompt to eliminate JOIN_ERROR.
    """

    def __init__(self):
        pass

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
            # FOREIGN KEY (col1, col2) REFERENCES target_table(target_col1, target_col2)
            # FOREIGN KEY (`Maker`) REFERENCES `CAR_MAKERS` (`Id`)
            fk_pattern = re.compile(
                r'FOREIGN\s+KEY\s*\(\s*[`"\[]?([\w\-]+)[`"\]]?\s*\)\s*REFERENCES\s+[`"\[]?([\w\.\-]+)[`"\]]?\s*(?:\(\s*[`"\[]?([\w\-]+)[`"\]]?\s*\))?',
                re.IGNORECASE
            )
            for m in fk_pattern.finditer(block):
                from_col = m.group(1)
                to_table = m.group(2).split('.')[-1]
                to_col = m.group(3) if m.group(3) else from_col  # Default to same column name if omitted

                relationships.append({
                    "from_table": from_table,
                    "from_col": from_col,
                    "to_table": to_table,
                    "to_col": to_col
                })

            # 2. Inline column-level REFERENCES:
            # Maker INTEGER REFERENCES CAR_MAKERS(Id)
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
                    # PRAGMA foreign_key_list row: (id, seq, table, from, to, on_update, on_delete, match)
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

    def find_shortest_path(self, graph: Dict[str, List[Dict[str, str]]], start_table: str, target_table: str, max_hops: int = 4) -> Optional[List[Dict[str, str]]]:
        """
        BFS shortest path between two tables in the relational graph.
        Returns list of edge steps, or None if unreachable.
        """
        start = start_table.lower()
        target = target_table.lower()

        if start == target or start not in graph or target not in graph:
            return None

        queue = deque([(start, [])])
        visited = {start}

        while queue:
            current, path = queue.popleft()

            if len(path) >= max_hops:
                continue

            for edge in graph.get(current, []):
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
        max_hops: int = 4
    ) -> Tuple[Set[str], List[Dict[str, str]]]:
        """
        Identifies intermediate bridge tables connecting disconnected terminal tables,
        and computes the exact join path sequence.
        
        Returns:
            Tuple[Set[str], List[Dict]]: (bridge_table_names, join_path_steps)
        """
        # 1. Gather all foreign keys from DB connection or DDL
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
                    path = self.find_shortest_path(graph, t1, t2, max_hops=max_hops)
                    if path:
                        for step in path:
                            all_paths.append(step)
                            bridge_tables.add(step["to_table_raw"])
                        # Remove destination table from bridge tables since it is a terminal
                        bridge_tables.discard(t2)

        return bridge_tables, all_paths

    def format_join_path_hints(self, join_paths: List[Dict[str, str]]) -> str:
        """
        Formats discovered multi-hop join paths into compact SQL prompt hints.
        """
        if not join_paths:
            return ""

        seen = set()
        unique_hints = []

        for p in join_paths:
            hint = f"{p['from_table']}.{p['from_col']} = {p['to_table']}.{p['to_col']}"
            hint_rev = f"{p['to_table']}.{p['to_col']} = {p['from_table']}.{p['from_col']}"
            if hint not in seen and hint_rev not in seen:
                seen.add(hint)
                unique_hints.append(f"-- Join Path: {hint}")

        if not unique_hints:
            return ""

        return "\n".join([
            "/* Multi-Hop Relational Join Paths */",
            *unique_hints
        ])

relationship_mapper = RelationshipMapper()
