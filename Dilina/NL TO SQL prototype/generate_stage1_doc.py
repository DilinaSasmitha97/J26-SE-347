import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def create_stage1_document():
    doc = docx.Document()

    # Page setup - Margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Color Palette (SLIIT / Professional Academic Theme)
    PRIMARY_COLOR = RGBColor(27, 54, 93)     # Deep Navy
    SECONDARY_COLOR = RGBColor(0, 122, 120)  # Teal Accent
    DARK_TEXT = RGBColor(40, 40, 40)        # Dark Charcoal Text
    BG_LIGHT_HEX = "F0F4F8"
    BORDER_HEX = "CCCCCC"

    # Set base font
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = DARK_TEXT

    def set_cell_background(cell, hex_color):
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    def add_heading_1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(15)
        run.font.bold = True
        run.font.color.rgb = PRIMARY_COLOR
        return p

    def add_heading_2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(12)
        run.font.bold = True
        run.font.color.rgb = SECONDARY_COLOR
        return p

    # --- TITLE HEADER ---
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(4)
    run_title = title_p.add_run("STAGE 1 BASELINE BENCHMARK EVALUATION REPORT")
    run_title.font.name = 'Calibri'
    run_title.font.size = Pt(18)
    run_title.font.bold = True
    run_title.font.color.rgb = PRIMARY_COLOR

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(14)
    run_sub = sub_p.add_run("Project IT4010 (J26-SE-347) — Member 1: Schema-Aware NL-to-SQL Translation Engine")
    run_sub.font.name = 'Calibri'
    run_sub.font.size = Pt(11)
    run_sub.font.italic = True
    run_sub.font.color.rgb = SECONDARY_COLOR

    # Metadata Callout Box
    meta_table = doc.add_table(rows=5, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Project Title:", "Secure Multi-Tenant Natural Language Interface for Database Querying"),
        ("Student Name & ID:", "Sasmitha A W D (IT23143418) — Member 1 Component Lead"),
        ("Research Group:", "CoEAI - Centre of Excellence for AI (SLIIT UNI)"),
        ("Evaluated Model:", "Qwen/Qwen-2.5-Coder-32B-Instruct (via OpenRouter Paid Tier)"),
        ("Benchmark Scope:", "Spider Full dev.json Benchmark | N = 1,034 queries across all difficulty tiers")
    ]
    for idx, (label, val) in enumerate(meta_data):
        row = meta_table.rows[idx]
        row.cells[0].paragraphs[0].add_run(label).bold = True
        row.cells[0].width = Inches(2.0)
        row.cells[1].paragraphs[0].add_run(val)
        row.cells[1].width = Inches(4.5)
        set_cell_background(row.cells[0], BG_LIGHT_HEX)
        set_cell_background(row.cells[1], BG_LIGHT_HEX)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --- SECTION 1: EXECUTIVE SUMMARY ---
    add_heading_1("1. Executive Summary")
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(8)
    p.add_run(
        "This research report documents the formal empirical baseline evaluation for Stage 1 (Naive Baseline) "
        "of Member 1's research component. In this phase, the Natural Language-to-SQL translation engine operates "
        "without schema pruning or autonomous self-correction, directly prompting the foundation model with the "
        "unpruned database schema (DDL) within a Code Representation Prompt (CRP).\n\n"
        "The full Spider benchmark suite (N = 1,034 cross-domain queries) was evaluated using Alibaba Cloud's "
        "Qwen-2.5-Coder-32B-Instruct model. The engine achieved an Execution Accuracy (EX) of 68.47% (708/1,034 correct), "
        "consuming an average of 426.3 tokens per query. This benchmark establishes a rigorous, reproducible control "
        "reference for evaluating subsequent architectural enhancements in Stage 2 (Minimal-Context Schema Pruning) and "
        "Stage 3 (Automated Query Refinement Loop)."
    )

    # Key Metrics Table
    exec_table = doc.add_table(rows=6, cols=2)
    exec_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    exec_headers = [
        ("Evaluation Metric", "Empirical Baseline Value"),
        ("Total Queries Evaluated", "1,034 queries (100% of Spider dev set)"),
        ("Successful Query Matches (EX)", "708 / 1,034 (68.47% Execution Accuracy)"),
        ("Total Pipeline Failures", "326 / 1,034 (31.53%)"),
        ("Average Tokens per Query", "426.3 total (386.4 in / 40.0 out)"),
        ("Total Benchmark Runtime", "2,520.52 seconds (~42.0 minutes)")
    ]
    for r_idx, (c1, c2) in enumerate(exec_headers):
        row = exec_table.rows[r_idx]
        p1 = row.cells[0].paragraphs[0]
        p2 = row.cells[1].paragraphs[0]
        p1.add_run(c1).bold = (r_idx == 0)
        p2.add_run(c2).bold = (r_idx == 0)
        row.cells[0].width = Inches(2.8)
        row.cells[1].width = Inches(3.7)
        if r_idx == 0:
            set_cell_background(row.cells[0], "1B365D")
            set_cell_background(row.cells[1], "1B365D")
            p1.runs[0].font.color.rgb = RGBColor(255, 255, 255)
            p2.runs[0].font.color.rgb = RGBColor(255, 255, 255)
        else:
            if r_idx % 2 == 1:
                set_cell_background(row.cells[0], BG_LIGHT_HEX)
                set_cell_background(row.cells[1], BG_LIGHT_HEX)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --- SECTION 2: DIFFICULTY TIER BREAKDOWN ---
    add_heading_1("2. Performance Breakdown by Query Complexity")
    p = doc.add_paragraph(
        "The Spider benchmark stratifies queries into four standardized complexity tiers based on SQL clauses, "
        "aggregations, and join counts. The Stage 1 baseline exhibits a distinct accuracy decay curve as query complexity increases:"
    )
    p.paragraph_format.space_after = Pt(6)

    diff_table = doc.add_table(rows=6, cols=5)
    diff_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    diff_rows = [
        ("Complexity Tier", "Available Queries", "Correct (Match)", "Execution Accuracy", "Key Failure Pattern"),
        ("Easy", "458", "385", "84.06%", "High competence on single-table selections"),
        ("Medium", "332", "208", "62.65%", "Dialect confusion on 1-2 table joins & GROUP BY"),
        ("Hard", "238", "115", "48.32%", "Syntax & join path errors on 3+ table joins"),
        ("Extra Hard", "6", "0", "0.00%", "Subquery nesting & compound set operation failures"),
        ("Total / Overall", "1,034", "708", "68.47%", "Primary Stage 1 Scientific Control Baseline")
    ]
    for r_idx, row_vals in enumerate(diff_rows):
        row = diff_table.rows[r_idx]
        for c_idx, val in enumerate(row_vals):
            cell = row.cells[c_idx]
            p = cell.paragraphs[0]
            p.add_run(val).bold = (r_idx == 0 or r_idx == 5)
            if r_idx == 0:
                set_cell_background(cell, "1B365D")
                p.runs[0].font.color.rgb = RGBColor(255, 255, 255)
            elif r_idx == 5:
                set_cell_background(cell, "E2E8F0")
            elif r_idx % 2 == 1:
                set_cell_background(cell, BG_LIGHT_HEX)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --- SECTION 3: FAILURE TAXONOMY BREAKDOWN ---
    add_heading_1("3. Failure Taxonomy & Root Cause Analysis")
    p = doc.add_paragraph(
        "All 326 pipeline failures were captured and classified using the project's standardized failure taxonomy. "
        "This categorization directly identifies the engineering requirements for subsequent stages:"
    )
    p.paragraph_format.space_after = Pt(6)

    tax_table = doc.add_table(rows=6, cols=4)
    tax_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tax_rows = [
        ("Failure Category", "Count", "% of Failures", "Targeted Resolution Stage"),
        ("RESULT_MISMATCH", "175", "53.68%", "Task 4 (Entity Resolution & Semantic Disambiguation)"),
        ("SYNTAX_ERROR", "121", "37.12%", "Task 3 (Automated Query Refinement Loop)"),
        ("JOIN_ERROR", "15", "4.60%", "Task 4 (Relational Dependency Graph Closure)"),
        ("SCHEMA_LINKING_ERROR", "10", "3.07%", "Task 1 (Minimal-Context Schema Extractor)"),
        ("AGGREGATION_ERROR", "5", "1.53%", "Task 2 (Context-Aware Prompt Engineering)")
    ]
    for r_idx, row_vals in enumerate(tax_rows):
        row = tax_table.rows[r_idx]
        for c_idx, val in enumerate(row_vals):
            cell = row.cells[c_idx]
            p = cell.paragraphs[0]
            p.add_run(val).bold = (r_idx == 0)
            if r_idx == 0:
                set_cell_background(cell, "1B365D")
                p.runs[0].font.color.rgb = RGBColor(255, 255, 255)
            elif r_idx % 2 == 1:
                set_cell_background(cell, BG_LIGHT_HEX)

    p_disc = doc.add_paragraph()
    p_disc.paragraph_format.space_before = Pt(8)
    p_disc.paragraph_format.line_spacing = 1.15
    p_disc.add_run(
        "Key Research Insight on SYNTAX_ERROR:\n"
        "The 121 syntax errors (representing 37.12% of all failures) were primarily caused by dialect friction "
        "(e.g. generating T-SQL bracket escaping or pagination clauses that failed in the SQLite environment) and "
        "near-miss identifier quoting. Because these errors produce deterministic database compiler messages, they "
        "represent the primary recovery target for Stage 3's Automated Query Refinement Loop.\n\n"
        "Key Research Insight on SCHEMA_LINKING_ERROR:\n"
        "Exposing the LLM to full, unpruned schemas forced the attention mechanism to navigate distractor tables, "
        "causing column hallucinations on large schemas. This validates the premise of Stage 2's Minimal-Context Schema Extractor."
    )

    # --- SECTION 4: LATENCY & TOKEN PROFILING ---
    add_heading_1("4. Computational Efficiency & Latency Profile")
    p = doc.add_paragraph(
        "Cycle profiling reveals that remote LLM API inference constitutes 78.9% of total pipeline runtime (1,988.6s), "
        "while local database connection, schema extraction, and query execution combined account for less than 1% of time."
    )
    p.paragraph_format.space_after = Pt(6)

    # --- SECTION 5: ROADMAP HYPOTHESIS ---
    add_heading_1("5. Research Progression Hypothesis for Stages 2 & 3")
    p = doc.add_paragraph(
        "With the Stage 1 baseline established at 68.47%, the research hypothesis projects measurable accuracy gains across phases:"
    )

    prog_table = doc.add_table(rows=4, cols=4)
    prog_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    prog_rows = [
        ("Research Stage", "Primary Architectural Novelty", "Target Failure Eliminated", "Projected Accuracy"),
        ("Stage 1 (Current)", "Naive Baseline (Unpruned Schema CRP)", "None (Scientific Control)", "68.47% (Empirical)"),
        ("Stage 2 (Task 1)", "Minimal-Context Schema Extractor", "Distractor tables & Token bloat", "71.0% - 74.0%"),
        ("Stage 3 (Task 3)", "Compiler Dry-Run Self-Correction Loop", "121 SYNTAX_ERROR queries", "77.0% - 82.0%")
    ]
    for r_idx, row_vals in enumerate(prog_rows):
        row = prog_table.rows[r_idx]
        for c_idx, val in enumerate(row_vals):
            cell = row.cells[c_idx]
            p = cell.paragraphs[0]
            p.add_run(val).bold = (r_idx == 0)
            if r_idx == 0:
                set_cell_background(cell, "1B365D")
                p.runs[0].font.color.rgb = RGBColor(255, 255, 255)
            elif r_idx % 2 == 1:
                set_cell_background(cell, BG_LIGHT_HEX)

    doc.add_paragraph().paragraph_format.space_after = Pt(16)
    
    # Save document
    doc.save("Stage_1_Baseline_Report.docx")
    print("Stage_1_Baseline_Report.docx created successfully!")

if __name__ == "__main__":
    create_stage1_document()
