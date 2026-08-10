# 🧪 NL-to-SQL Research Protocol & Agent Directives

These are the operational rules for the AI Agent assisting with this research project, designed to maintain rigorous standards for a future research paper publication.

## 1. Documentation & Reporting
- **Experiment Logs**: After every major evaluation run or architectural change, the agent will generate a Markdown report summarizing the metrics (Accuracy, Token Usage, Failure Taxonomy).
- **Time-Series Tracking**: The agent will maintain a running log of performance improvements over time to make plotting graphs for the paper easier.
- **Hypothesis Tracking**: Changes to the core engine must be documented with the hypothesis being tested (e.g., "Adding self-correction to reduce SYNTAX_ERROR").

## 2. Experimental Rigor
- **A/B Testing**: When introducing a new technique (like schema pre-filtering), it must be toggleable so it can be directly compared against the Phase 1 Naive Baseline.
- **Reproducibility**: All prompts, model parameters (temperature, etc.), and library versions must be strictly tracked. Random seeds should be fixed where applicable.
- **Failure Analysis**: The agent will not just fix errors; it will analyze *why* the LLM failed and categorize it according to the `failure_taxonomy.json` to write about it in the paper's discussion section.

## 3. Workflow & Automation
- **Periodic Evaluation**: The agent can use the `/schedule` command to run the full benchmark suite overnight and compile a report by morning.
- **Incremental Complexity**: Development will proceed iteratively—first mastering 'easy'/'medium' queries, then tackling 'hard'/'extra' queries.

## 4. Paper-Ready Outputs
- Code should be clean, modular, and ready to be open-sourced alongside the paper.
- Tables and figures should be generated in markdown format that can be easily translated to LaTeX later.

## 5. Strict Git & Version Control Protocol
- **No Automatic Git Commands**: The AI Agent must NEVER execute `git commit`, `git push`, `git add`, `git reset`, or any Git-related terminal command automatically. All Git operations are strictly reserved for the user unless explicitly commanded.
