"""
This file stores the prompt templates for the NL-to-SQL Engine 
using the Code Representation Prompt (CRP) strategy.
"""

def generate_crp_prompt(schema_context: str, user_request: str, injected_rules: str = None) -> str:
    """
    Constructs the exact string representation for the LLM based on Phase 1 rules.
    Combines strict formatting, SQL schema context in comment blocks, optional authorization/security 
    rules placeholder (reserved for Member 3 integration), and the natural language request.
    """
    
    rules_block = ""
    if injected_rules and str(injected_rules).strip():
        rules_block = f"\n/* Injected Authorization & Security Rules:\n{injected_rules}\n*/\n"

    prompt = f"""Complete Microsoft SQL Server query only and with no explanation

/* Given the following database schema:
{schema_context}
*/{rules_block}

/* Answer the following: {user_request} */
SELECT"""
    
    return prompt

