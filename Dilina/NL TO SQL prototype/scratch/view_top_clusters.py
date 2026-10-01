import json

with open("mismatches_stage4_1.json", 'r', encoding='utf-8') as f:
    mismatches = json.load(f)

for target in ["LITERAL_VALUE_CHOICE_MISMATCH", "PREDICATE_LOGIC_MISMATCH"]:
    items = [m for m in mismatches if m["analysis"]["cluster"] == target]
    print("=" * 80)
    print(f"CLUSTER: {target} (Total: {len(items)})")
    print("=" * 80)
    for sample in items[:3]:
        print(f"  [Sample {sample['sample_idx']}] DB: {sample['db_id']} | Tier: {sample['complexity']}")
        print(f"  Q:    {sample['question']}")
        print(f"  PRED: {sample['predicted_sql']}")
        print(f"  GOLD: {sample['gold_sql']}")
        print(f"  DIFF: {sample['analysis']['details']}")
        print("-" * 50)
    print()
