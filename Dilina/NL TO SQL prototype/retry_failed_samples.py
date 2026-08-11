import re
import os
import json
import time
import create_task1_doc

def run_retry_failed():
    log_path = r'C:\Users\USER\.gemini\antigravity-ide\brain\243f7ff4-f81f-4e7b-b378-3b808afba098\.system_generated\tasks\task-1067.log'
    if not os.path.exists(log_path):
        print("Log file not found:", log_path)
        return

    txt = open(log_path, 'r', encoding='utf-8', errors='ignore').read()
    
    # Extract indices of 429 failed samples
    # Pattern: Starting Sample (\d+)/1034 followed by Evaluation error: Error code: 429
    blocks = txt.split("[CYCLE] Starting Sample ")
    failed_indices = []
    
    for b in blocks[1:]:
        m = re.match(r'(\d+)/1034', b)
        if m:
            idx = int(m.group(1))
            if "Evaluation error: Error code: 429" in b:
                failed_indices.append(idx)
                
    print(f"=== Found {len(failed_indices)} rate-limited samples to re-run out of 1034 total ===")
    
    # Load dataset
    dev_json_path = r"D:\spider_data\dev.json"
    db_dir = r"D:\spider_data\database"
    
    with open(dev_json_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    print(f"Total dataset loaded: {len(dataset)} items")
    
    # Import evaluate dependencies
    from database import get_sqlite_connection, extract_sqlite_schema_as_create_statements
    from main import translate
    
    new_correct = 0
    new_errors = 0
    
    for count, idx_1based in enumerate(failed_indices, 1):
        item = dataset[idx_1based - 1]
        db_id = item["db_id"]
        question = item["question"]
        gold_sql = item["query"]
        
        db_path = os.path.join(db_dir, db_id, f"{db_id}.sqlite")
        
        print(f"\n[{count}/{len(failed_indices)}] (Original Sample #{idx_1based}) DB: {db_id} | Q: {question}")
        
        try:
            conn = get_sqlite_connection(db_path)
            conn.text_factory = lambda b: b.decode('utf-8', errors='ignore')
            full_ddl = extract_sqlite_schema_as_create_statements(conn)
            
            # Translate question to SQL
            predicted_sql, token_stats = translate(question, full_ddl)
            
            cursor = conn.cursor()
            cursor.execute(predicted_sql)
            pred_results = cursor.fetchall()
            
            cursor.execute(gold_sql)
            gold_results = cursor.fetchall()
            
            conn.close()
            
            pred_set = set([str(r) for r in pred_results])
            gold_set = set([str(r) for r in gold_results])
            
            if pred_set == gold_set:
                new_correct += 1
                print(f"  --> [MATCH] FIXED & CORRECT!")
            else:
                print(f"  --> [MISMATCH] Result mismatch / syntax difference")
        except Exception as e:
            new_errors += 1
            safe_err = str(e).encode('ascii', errors='replace').decode('ascii')
            print(f"  --> [ERROR] Error: {safe_err}")
            
        time.sleep(2.5)

    print(f"\n=== Re-run of {len(failed_indices)} Failed Samples Complete ===")
    print(f"Newly Correct: {new_correct} / {len(failed_indices)}")
    print(f"Original 643 Completed Correct: 416")
    total_correct = 416 + new_correct
    total_acc = (total_correct / 1034) * 100
    print(f"🎉 FINAL TOTAL DATASET EXECUTION ACCURACY: {total_acc:.2f}% ({total_correct}/1034)")

if __name__ == "__main__":
    run_retry_failed()
