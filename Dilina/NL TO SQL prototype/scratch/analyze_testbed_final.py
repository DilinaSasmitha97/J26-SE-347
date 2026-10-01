import re

log_path = r"C:\Users\USER\.gemini\antigravity-ide\brain\41ea6217-4925-49a6-aa04-40a1e22a4743\.system_generated\tasks\task-1646.log"

with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Split by sample blocks
samples = re.findall(r'\[(\d+)/206\]\s+Sample\s+#(\d+)\s+\|\s+DB:\s+([\w\.\-]+)\s+\((\w+)\)\s+\|\s+Cluster:\s+([\w_]+)(.*?)(?=\[\d+/206\]|=================================================================)', content, re.DOTALL)

strict_by_cluster = {}
perm_by_cluster = {}
still_by_cluster = {}

for s in samples:
    seq_idx, s_idx, db_id, comp, cluster, body = s
    if "[STRICT MATCH]" in body:
        strict_by_cluster[cluster] = strict_by_cluster.get(cluster, 0) + 1
    elif "[PERMUTATION MATCH]" in body:
        perm_by_cluster[cluster] = perm_by_cluster.get(cluster, 0) + 1
    elif "[STILL MISMATCH]" in body:
        still_by_cluster[cluster] = still_by_cluster.get(cluster, 0) + 1

print("="*65)
print("     TESTBED HEALING ANALYSIS BY CLUSTER (N = 206)")
print("="*65)
all_clusters = set(list(strict_by_cluster.keys()) + list(perm_by_cluster.keys()) + list(still_by_cluster.keys()))
for c in sorted(all_clusters):
    st = strict_by_cluster.get(c, 0)
    pe = perm_by_cluster.get(c, 0)
    mi = still_by_cluster.get(c, 0)
    tot = st + pe + mi
    print(f"{c:<38}: Strict={st:>2} | Perm={pe:>2} | Still Mismatch={mi:>2} (Total={tot:>2})")
print("="*65)
