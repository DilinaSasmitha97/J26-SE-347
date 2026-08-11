import re
import os
import json

def parse_log_summary(log_file_path):
    print(f"Parsing benchmark log file: {log_file_path}")
    
    if not os.path.exists(log_file_path):
        print("Log file not found!")
        return
        
    with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    # Extract all MATCH / MISMATCH / ERROR lines
    matches = len(re.findall(r'\[MATCH\] Results are identical', content))
    mismatches = len(re.findall(r'\[MISMATCH\] Results differ', content))
    schema_errors = len(re.findall(r'Category: SCHEMA_LINKING_ERROR', content))
    syntax_errors = len(re.findall(r'Category: SYNTAX_ERROR', content))
    join_errors = len(re.findall(r'Category: JOIN_ERROR', content))
    rate_limit_errors = len(re.findall(r'All 3 retries failed for LLM Call', content))
    
    # Extract total samples evaluated prior to rate limit exhaustion
    sample_starts = re.findall(r'\[(\d+)/1034\] DB:', content)
    total_started = len(sample_starts)
    
    valid_evaluated = matches + mismatches + syntax_errors + join_errors + schema_errors
    accuracy = (matches / valid_evaluated * 100.0) if valid_evaluated > 0 else 0.0
    
    print("\n==================================================")
    print(f"   EMPIRICAL BENCHMARK SUMMARY (N={valid_evaluated} Completed Queries)")
    print("==================================================")
    print(f"Total Queries Attempted  : {total_started}")
    print(f"Valid Evaluated Queries  : {valid_evaluated}")
    print(f"Correct SQL Matches      : {matches}")
    print(f"Execution Accuracy       : {accuracy:.2f}%")
    print(f"Rate-Limit Exhausted     : {rate_limit_errors} queries at end of daily quota")
    print("--------------------------------------------------")
    print("Failure Taxonomy Breakdown:")
    print(f"  * SCHEMA_LINKING_ERROR : {schema_errors}")
    print(f"  * SYNTAX_ERROR         : {syntax_errors}")
    print(f"  * JOIN_ERROR           : {join_errors}")
    print(f"  * RESULT_MISMATCH      : {mismatches}")
    print("==================================================\n")
    
    return {
        "valid_evaluated": valid_evaluated,
        "correct": matches,
        "accuracy": round(accuracy, 2),
        "schema_linking_errors": schema_errors,
        "syntax_errors": syntax_errors,
        "join_errors": join_errors,
        "result_mismatches": mismatches
    }

if __name__ == "__main__":
    log_path = r"C:\Users\USER\.gemini\antigravity-ide\brain\243f7ff4-f81f-4e7b-b378-3b808afba098\.system_generated\tasks\task-845.log"
    parse_log_summary(log_path)
