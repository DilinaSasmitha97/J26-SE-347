import re

log_path = r"C:\Users\USER\.gemini\antigravity-ide\brain\41ea6217-4925-49a6-aa04-40a1e22a4743\.system_generated\tasks\task-1631.log"

with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

strict_matches = re.findall(r'\[STRICT MATCH\]', content)
perm_matches = re.findall(r'\[PERMUTATION MATCH\]', content)
still_mismatch = re.findall(r'\[STILL MISMATCH\]', content)

total_evaluated = len(strict_matches) + len(perm_matches) + len(still_mismatch)

print("="*60)
print(f"PARTIAL TESTBED PROGRESS (Completed {total_evaluated} / 206 before server restart):")
print("="*60)
print(f"Strict Matches (Newly Correct)     : {len(strict_matches)} ({len(strict_matches)/total_evaluated*100:.1f}%)")
print(f"Permutation Matches (Semantically Valid): {len(perm_matches)} ({len(perm_matches)/total_evaluated*100:.1f}%)")
print(f"Still Mismatch                      : {len(still_mismatch)} ({len(still_mismatch)/total_evaluated*100:.1f}%)")
print(f"Total Recovered / Validated         : {len(strict_matches) + len(perm_matches)} / {total_evaluated} ({(len(strict_matches) + len(perm_matches))/total_evaluated*100:.1f}%)")
print("="*60)
