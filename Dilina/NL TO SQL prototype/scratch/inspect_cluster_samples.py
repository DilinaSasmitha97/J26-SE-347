import json

with open(r"D:\Secure Multi-Tenant Natural Language Interface for Database Querying\Dilina\NL TO SQL prototype\mismatches_stage4_1.json", 'r', encoding='utf-8') as f:
    mismatches = json.load(f)

by_cluster = {}
for m in mismatches:
    c = m["analysis"]["cluster"]
    by_cluster.setdefault(c, []).append(m)

for cluster_name, items in sorted(by_cluster.items(), key=lambda x: len(x[1]), reverse=True):
    print("=" * 80)
    print(f"CLUSTER: {cluster_name} (Total: {len(items)})")
    print("=" * 80)
    for sample in items[:2]:
        print(f"  [Sample {sample['sample_idx']}] DB: {sample['db_id']} | Tier: {sample['complexity']}")
        print(f"  Q:    {sample['question']}")
        print(f"  PRED: {sample['predicted_sql']}")
        print(f"  GOLD: {sample['gold_sql']}")
        print(f"  DIFF: {sample['analysis']['details']}")
        print("-" * 50)
    print()
