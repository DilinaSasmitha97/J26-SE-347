import json

with open("mismatches_stage4_1.json", 'r', encoding='utf-8') as f:
    m = json.load(f)

items = [x for x in m if x['analysis']['cluster'] == 'LITERAL_VALUE_CHOICE_MISMATCH' and 'REPLACE' not in x['predicted_sql']]
for x in items[:8]:
    print(f"Sample {x['sample_idx']} ({x['db_id']}): Q: {x['question']}")
    print(f"  PRED: {x['predicted_sql']}")
    print(f"  GOLD: {x['gold_sql']}")
    print(f"  DIFF: {x['analysis']['details']}")
    print("-" * 50)
