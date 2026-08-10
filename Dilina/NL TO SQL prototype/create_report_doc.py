import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def create_document():
    doc = docx.Document()

    # Page setup - Margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Color Palette
    PRIMARY_COLOR = RGBColor(27, 54, 93)     # Deep Navy
    SECONDARY_COLOR = RGBColor(0, 122, 120)  # Teal/Cyan Accent
    DARK_TEXT = RGBColor(40, 40, 40)        # Dark Charcoal Text
    BG_LIGHT_HEX = "F0F4F8"
    BORDER_HEX = "CCCCCC"

    # Set base Normal Style font
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = DARK_TEXT

    # Helper function for cell background color
    def set_cell_background(cell, hex_color):
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    # Helper function for title formatting
    def add_heading_1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(16)
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
        run.font.size = Pt(13)
        run.font.bold = True
        run.font.color.rgb = SECONDARY_COLOR
        return p

    # --- COVER / TITLE HEADER ---
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(4)
    run_title = title_p.add_run("RESEARCH PROJECT PROGRESS REPORT & DEMO BRIEFING")
    run_title.font.name = 'Calibri'
    run_title.font.size = Pt(20)
    run_title.font.bold = True
    run_title.font.color.rgb = PRIMARY_COLOR

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(16)
    run_sub = sub_p.add_run("Project IT4010 (J26-SE-347) — Member 1: Schema-Aware NL-to-SQL Engine")
    run_sub.font.name = 'Calibri'
    run_sub.font.size = Pt(12)
    run_sub.font.italic = True
    run_sub.font.color.rgb = SECONDARY_COLOR

    # Meta Table (Metadata Callout Box)
    meta_table = doc.add_table(rows=4, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Project Title:", "Secure Multi-Tenant Natural Language Interface for Database Querying"),
        ("Student Name & ID:", "Sasmitha A W D (IT23143418) — Member 1 Component Lead"),
        ("Research Unit:", "CoEAI - Centre of Excellence for AI (SLIIT UNI)"),
        ("Report Date & Scope:", "August 10, 2026 | Phase 1 Baseline Implementation & Benchmark Evaluation")
    ]
    for idx, (label, val) in enumerate(meta_data):
        row = meta_table.rows[idx]
        row.cells[0].paragraphs[0].add_run(label).bold = True
        row.cells[0].width = Inches(1.8)
        row.cells[1].paragraphs[0].add_run(val)
        row.cells[1].width = Inches(4.7)
        set_cell_background(row.cells[0], BG_LIGHT_HEX)
        set_cell_background(row.cells[1], BG_LIGHT_HEX)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --- SECTION 1: EXECUTIVE SUMMARY ---
    add_heading_1("1. Executive Summary")
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(8)
    p.add_run(
        "This document provides a comprehensive progress briefing for the supervisor on Member 1's component "
        "of the IT4010 research project (Project ID: J26-SE-347). The primary objective of Member 1 is to architect a "
        "context-optimized, schema-aware Natural Language-to-SQL (NL-to-SQL) translation engine equipped with minimal-context "
        "schema extraction and autonomous self-correction capabilities.\n\n"
        "To date, Phase 1 (Month 1 Naive Baseline Engine) has been fully implemented, integrated, and evaluated against "
        "the standard Spider benchmark dataset across N = 100 queries. Empirical benchmark results indicate a baseline "
        "execution accuracy of 77.00% using Meta Llama-3.3-70B, establishing a rigorous control reference for future research iterations."
    )

    # --- SECTION 2: TECHNOLOGIES & STACK USED ---
    add_heading_1("2. Technology Stack & Frameworks")
    p = doc.add_paragraph("The engine and automated benchmark evaluation harness were developed using the following software stack:")
    p.paragraph_format.space_after = Pt(6)

    tech_table = doc.add_table(rows=5, cols=2)
    tech_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tech_headers = [("Technology Layer", "Components & Frameworks Used"),
                    ("Core Architecture", "Python 3.12, SQLite 3 Engine, SQL Server (pyodbc / sqlite3), REST API Gateway Specification"),
                    ("LLM Inference APIs", "Groq LPU Cloud API (Llama-3.3-70B, Llama-3.1-8B), OpenRouter API (Cohere North Mini Code), Google Gemini API"),
                    ("Evaluation & Analytics", "Spider Text-to-SQL Benchmark Dataset (dev.json, N = 100 queries), Custom CycleProfiler Latency Profiler"),
                    ("Environment & Security", "python-dotenv (.env key management), JSON Failure Taxonomy Exporter (failure_taxonomy.json)")]

    for r_idx, (c1, c2) in enumerate(tech_headers):
        row = tech_table.rows[r_idx]
        p1 = row.cells[0].paragraphs[0]
        p2 = row.cells[1].paragraphs[0]
        p1.add_run(c1).bold = (r_idx == 0)
        p2.add_run(c2).bold = (r_idx == 0)
        row.cells[0].width = Inches(2.2)
        row.cells[1].width = Inches(4.3)
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

    # --- SECTION 3: WHAT EXACTLY HAS BEEN BUILT ---
    add_heading_1("3. Deliverables Built & Implemented")

    add_heading_2("A. Phase 1 Naive NL-to-SQL Translation Engine (main.py)")
    p = doc.add_paragraph(
        "A functional Python translation module that accepts natural language questions, extracts relational database "
        "schema structures (CREATE DDL statements), and formats Code Representation Prompts (CRP). It communicates with LLM "
        "provider APIs via zero-shot inference to produce executable SQL queries."
    )
    p.paragraph_format.space_after = Pt(6)

    add_heading_2("B. Automated Benchmark Evaluation Harness (evaluate.py)")
    p = doc.add_paragraph(
        "An automated testing pipeline capable of iterating through benchmark questions (Spider dataset), executing predicted "
        "SQL against gold-standard database instances, comparing output result sets, tracking token consumption, profiling "
        "latency down to the microsecond level, and categorizing failures into a standardized failure taxonomy."
    )
    p.paragraph_format.space_after = Pt(6)

    add_heading_2("C. Multi-Developer System Interface Specification (team_interface_contract.md)")
    p = doc.add_paragraph(
        "A detailed API contract document specifying the REST endpoints (POST /api/v1/translate, GET /api/v1/health) "
        "and data schemas required to connect Member 1's engine with Member 3 (Federated Auth & RBAC), Member 2 (AST Security Middleware & PII Masking), "
        "and Member 4 (Vega-Lite & SARIMA Presentation Layer)."
    )
    p.paragraph_format.space_after = Pt(8)

    # --- SECTION 4: EMPIRICAL BENCHMARK RESULTS ---
    add_heading_1("4. Empirical Benchmark Results (N = 100 Queries)")
    p = doc.add_paragraph(
        "To evaluate baseline performance, N = 100 queries were evaluated across all 4 difficulty levels (easy, medium, hard, extra) "
        "using Meta Llama-3.3-70B (Baseline), Meta Llama-3.1-8B (Model Scale Comparison), and Cohere North Mini Code (Specialized Code LLM)."
    )
    p.paragraph_format.space_after = Pt(6)

    res_table = doc.add_table(rows=5, cols=5)
    res_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    res_headers = [
        ("Metric / Dimension", "Llama-3.3-70B (Groq)", "Llama-3.1-8B (Groq)", "Cohere Code (OpenRouter)", "DeepSeek V3 (SambaNova)"),
        ("Execution Accuracy", "77.00% (77/100)", "68.00% (68/100)", "71.43% (35/49 valid)", "88.89% (16/18 valid)"),
        ("Schema Linking Errors", "0 (0.0%)", "13 (13.0%)", "0 (0.0%)", "0 (0.0%)"),
        ("Primary Failure Mode", "RESULT_MISMATCH (20)", "SCHEMA_LINKING (13)", "Rate Limiting (51)", "Rate Limiting (82)"),
        ("LLM Latency Bottleneck", "99.6% (210.95s total)", "99.6% (276.32s total)", "85.4% (1063.17s total)", "66.4% (1629.11s total)")
    ]

    for r_idx, row_data in enumerate(res_headers):
        row = res_table.rows[r_idx]
        for c_idx, val in enumerate(row_data):
            cell = row.cells[c_idx]
            p_cell = cell.paragraphs[0]
            p_cell.add_run(val).bold = (r_idx == 0 or c_idx == 0)
            if r_idx == 0:
                set_cell_background(cell, "1B365D")
                p_cell.runs[0].font.color.rgb = RGBColor(255, 255, 255)
            elif r_idx % 2 == 1:
                set_cell_background(cell, BG_LIGHT_HEX)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Key Observations Callout Box
    add_heading_2("Key Findings for Literature:")
    bullet1 = doc.add_paragraph(style='List Bullet')
    bullet1.add_run("Model Scale Impact: ").bold = True
    bullet1.add_run("Reducing model size from 70B to 8B caused a 9.00% accuracy drop and triggered 13 Schema Linking Errors, proving smaller models hallucinate column mappings without schema pruning.")
    
    bullet2 = doc.add_paragraph(style='List Bullet')
    bullet2.add_run("Dialect Confusion: ").bold = True
    bullet2.add_run("All models generated T-SQL pagination syntax (OFFSET 0 ROWS FETCH NEXT 1 ROW ONLY) instead of SQLite LIMIT, proving model size alone does not resolve SQL dialect confusion.")

    bullet3 = doc.add_paragraph(style='List Bullet')
    bullet3.add_run("Latency Bottleneck: ").bold = True
    bullet3.add_run("Local database operations take < 0.4% total runtime. Over 99.6% of system latency is consumed by LLM API inference.")

    # --- SECTION 5: UPCOMING IMPROVEMENTS ---
    add_heading_1("5. Roadmap & Next Research Improvements")

    roadmap_data = [
        ("Task 1: Minimal-Context Schema Extraction", "Phase 2", "Prune large database schemas down to only question-relevant tables before prompting. Expected to cut prompt tokens by 60% and eliminate 8B schema linking errors."),
        ("Task 3: Autonomous Query Refinement Loop", "Phase 3", "Engine that intercepts SQLite execution errors (like T-SQL OFFSET errors) and feeds back error messages to the LLM to self-correct automatically (projected to boost accuracy from 77% to > 90%)."),
        ("Task 4: Contextual Entity Resolution", "Phase 4", "Explicit foreign key join mapping to eliminate RESULT_MISMATCH logic errors.")
    ]

    road_table = doc.add_table(rows=4, cols=3)
    road_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    road_headers = [("Research Objective (TAF)", "Target Phase", "Planned Improvement & Expected Impact")] + roadmap_data

    for r_idx, row_data in enumerate(road_headers):
        row = road_table.rows[r_idx]
        for c_idx, val in enumerate(row_data):
            cell = row.cells[c_idx]
            p_cell = cell.paragraphs[0]
            p_cell.add_run(val).bold = (r_idx == 0 or c_idx == 0)
            if r_idx == 0:
                set_cell_background(cell, "007A78")
                p_cell.runs[0].font.color.rgb = RGBColor(255, 255, 255)
            elif r_idx % 2 == 1:
                set_cell_background(cell, BG_LIGHT_HEX)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # --- SECTION 6: DEMO VIDEO SCRIPT ---
    add_heading_1("6. 2-Minute Demonstration Video Script for Supervisor")

    script_p = doc.add_paragraph()
    script_p.paragraph_format.line_spacing = 1.15
    script_p.add_run("Use this step-by-step walkthrough script when recording your demonstration video:\n").bold = True

    steps = [
        ("0:00 - 0:30 (Introduction & Architecture)", 
         "Show the repository structure. Explain: 'Hello, this is Sasmitha demonstrating Member 1's component for Project J26-SE-347. My role is building the Schema-Aware NL-to-SQL translation engine.'"),
        ("0:30 - 1:00 (Live Execution Demo)", 
         "Open PowerShell. Run `.\\venv\\Scripts\\python.exe main.py`. Enter a question like: 'What is the name and capacity of the stadium with the highest attendance?'. Show the generated SQL query and token count."),
        ("1:00 - 1:30 (Benchmark Evaluation Pipeline)", 
         "Run `.\\venv\\Scripts\\python.exe evaluate.py -n 10 -d all`. Show the automated evaluation harness processing Spider queries, running predicted SQL in SQLite, and outputting execution accuracy."),
        ("1:30 - 2:00 (Results & Next Steps)", 
         "Open `baseline_report_N100.md`. Highlight the 77.00% accuracy on N=100 queries, explain the failure taxonomy analysis, and outline the upcoming Minimal-Context Schema Extractor and Self-Correction Loop.")
    ]

    for timestamp, text in steps:
        p_step = doc.add_paragraph(style='List Bullet')
        p_step.add_run(f"[{timestamp}]: ").bold = True
        p_step.add_run(text)

    # Save document
    output_filename = r"D:\Secure Multi-Tenant Natural Language Interface for Database Querying\Dilina\NL TO SQL prototype\Supervisor_Progress_Report.docx"
    try:
        doc.save(output_filename)
        print(f"Document successfully created at: {output_filename}")
    except PermissionError:
        fallback_filename = r"D:\Secure Multi-Tenant Natural Language Interface for Database Querying\Dilina\NL TO SQL prototype\Supervisor_Progress_Report_v2.docx"
        doc.save(fallback_filename)
        print(f"Original file was open. Saved updated document to: {fallback_filename}")

if __name__ == "__main__":
    create_document()
