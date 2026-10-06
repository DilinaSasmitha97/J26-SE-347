import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def create_stage8a_document():
    doc = docx.Document()

    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    PRIMARY_COLOR = RGBColor(27, 54, 93)     # Deep Navy
    SECONDARY_COLOR = RGBColor(0, 122, 120)  # Teal Accent
    DARK_TEXT = RGBColor(40, 40, 40)        # Dark Charcoal Text
    BG_LIGHT_HEX = "F0F4F8"

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

    # Title Header
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(2)
    title_run = title_p.add_run("Stage 8A: Intent-Weighted Canonical Join Routing Report")
    title_run.font.name = 'Calibri'
    title_run.font.size = Pt(20)
    title_run.font.bold = True
    title_run.font.color.rgb = PRIMARY_COLOR

    subtitle_p = doc.add_paragraph()
    subtitle_p.paragraph_format.space_after = Pt(12)
    sub_run = subtitle_p.add_run("Eliminating Relational Subgraph Confusion via Dijkstra Join Routing and Negation Guards (Yale EX: 84.24%)")
    sub_run.font.name = 'Calibri'
    sub_run.font.size = Pt(11)
    sub_run.font.italic = True
    sub_run.font.color.rgb = SECONDARY_COLOR

    # Metadata Box
    meta_table = doc.add_table(rows=6, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Research Component:", "Member 1 — Schema-Aware NL-to-SQL Translation Engine (Sasmitha A W D)"),
        ("Research Entity:", "Centre of Excellence in AI (CoEAI), SLIIT UNI"),
        ("Target Baseline:", "Stage 7 Probing Baseline (83.56% Yale EX / 80.37% Strict EX)"),
        ("Stage 8A Outcome:", "84.24% Yale Execution Accuracy (871 / 1,034) [+7 net queries / New SOTA]"),
        ("Standardized Model:", "Qwen/Qwen-2.5-Coder-32B-Instruct (OpenRouter Paid Tier)"),
        ("Git Milestone:", "Branch: dilina-nl-to-sql-prototype-stage-8a-join-router")
    ]
    for r_idx, (lbl, val) in enumerate(meta_data):
        row = meta_table.rows[r_idx]
        cell_lbl, cell_val = row.cells[0], row.cells[1]
        p_l = cell_lbl.paragraphs[0]
        r_l = p_l.add_run(lbl)
        r_l.bold = True
        r_l.font.color.rgb = PRIMARY_COLOR
        p_v = cell_val.paragraphs[0]
        p_v.add_run(val)
        set_cell_background(cell_lbl, BG_LIGHT_HEX)
        set_cell_background(cell_val, "FFFFFF")

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Section 1: Executive Overview
    add_heading_1("1. Architectural Breakthrough & Executive Summary")
    p = doc.add_paragraph(
        "Stage 8A was engineered to resolve the primary failure bottleneck remaining from Stage 7: the increase in Join Errors "
        "from 15 to 23 caused by model over-reliance on modular nested subqueries. By enhancing RelationshipMapper with intent-weighted "
        "Dijkstra edge traversal, negation intent detection (preventing inner join bias on negative queries), and canonical join skeleton "
        "guidance, Stage 8A achieved a new all-time high of 84.24% Yale Execution Accuracy (871 / 1,034) and 81.24% Strict Set Accuracy "
        "(840 / 1,034).\n\n"
        "Critically, strict minimal gating ensured that single-table queries received zero prompt commentary, strictly preserving "
        "Easy-tier accuracy at 89.74% (411 / 458) with zero degradation."
    )

    # Section 2: Comparative Results Table
    add_heading_1("2. Comparative Evaluation Matrix (Stage 5 vs Stage 7 vs Stage 8A)")
    res_table = doc.add_table(rows=12, cols=5)
    res_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    res_data = [
        ("Metric Dimension", "Stage 5: Exemplar", "Stage 7: Probing", "Stage 8A: Join Router", "Stage 8A Delta"),
        ("Yale EX Accuracy", "82.30% (851)", "83.56% (864)", "84.24% (871 / 1,034)", "+0.68% (+7 net)"),
        ("Strict Set Accuracy", "79.11% (818)", "80.37% (831)", "81.24% (840 / 1,034)", "+0.87% (+9 net)"),
        ("Total Query Failures", "181 (17.5%)", "165 (16.0%)", "161 (15.6%)", "-4 failures"),
        ("Schema Linking Errors", "0 (0.0%)", "0 (0.0%)", "0 (0.0%)", "100% Extinct"),
        ("Join Errors", "15 (8.3%)", "23 (13.9%)", "20 (12.4%)", "-3 errors"),
        ("Aggregation Errors", "8 (4.4%)", "9 (5.5%)", "10 (6.2%)", "+1 error"),
        ("Syntax Errors", "4 (2.2%)", "0 (0.0%)", "3 (1.9%)", "Minor variance"),
        ("Result Mismatches", "154 (85.1%)", "133 (80.6%)", "128 (79.5%)", "-5 errors"),
        ("Avg Tokens / Query", "638.8", "575.6", "596.1", "+20.5 tokens"),
        ("Local Latency / Query", "< 28.0 ms", "< 25.0 ms", "< 25.0 ms", "2.2ms local graph"),
        ("Total Evaluation Time", "1,884s (~31.4m)", "2,344s (~39.1m)", "2,516s (~41.9m)", "~41.9 minutes")
    ]
    for r_idx, row_vals in enumerate(res_data):
        row = res_table.rows[r_idx]
        for c_idx, val in enumerate(row_vals):
            cell = row.cells[c_idx]
            p = cell.paragraphs[0]
            p.add_run(val).bold = (r_idx in (0, 1, 2, 4, 6))
            if r_idx == 0:
                set_cell_background(cell, "1B365D")
                p.runs[0].font.color.rgb = RGBColor(255, 255, 255)
            elif r_idx in (1, 2):
                set_cell_background(cell, "D4EDDA" if c_idx == 3 else "E2E8F0")
            elif r_idx % 2 == 1:
                set_cell_background(cell, BG_LIGHT_HEX)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Section 3: Difficulty Tier Table
    add_heading_1("3. Performance Across Complexity Tiers")
    tier_table = doc.add_table(rows=6, cols=4)
    tier_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tier_data = [
        ("Complexity Tier", "Stage 7 Accuracy", "Stage 8A Accuracy", "Net Shift"),
        ("Easy (N = 458)", "89.74% (411)", "89.74% (411)", "0 (Zero Regression)"),
        ("Medium (N = 332)", "82.83% (275)", "84.04% (279)", "+4 queries (+1.21%)"),
        ("Hard (N = 238)", "73.53% (175)", "74.79% (178)", "+3 queries (+1.26%)"),
        ("Extra Hard (N = 6)", "50.00% (3)", "50.00% (3)", "0 (Stable)"),
        ("Total Suite (N = 1,034)", "83.56% (864)", "84.24% (871)", "+7 net queries (SOTA!)")
    ]
    for r_idx, row_vals in enumerate(tier_data):
        row = tier_table.rows[r_idx]
        for c_idx, val in enumerate(row_vals):
            cell = row.cells[c_idx]
            p = cell.paragraphs[0]
            p.add_run(val).bold = (r_idx == 0 or r_idx == 5)
            if r_idx == 0:
                set_cell_background(cell, "1B365D")
                p.runs[0].font.color.rgb = RGBColor(255, 255, 255)
            elif r_idx == 5:
                set_cell_background(cell, "D4EDDA" if c_idx == 2 else "E2E8F0")
            elif r_idx % 2 == 1:
                set_cell_background(cell, BG_LIGHT_HEX)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Section 4: Forensic Case Studies & Stage 8B Next Steps
    add_heading_1("4. Forensic Confusion Matrix Audit & Directives for Stage 8B")
    p = doc.add_paragraph(
        "A query-by-query diff between Stage 7 and Stage 8A revealed 28 healed queries and 24 regressed queries:\n\n"
        "• Healed Complex Subgraphs (Idx 152, 153, 769, 770): In car_1, the engine previously hallucinated that car_names.MakeId "
        "joined car_makers.Id. Stage 8A's join router correctly guided the 4-table join chain through model_list. In world_1, "
        "it eliminated scalar subquery truncation by generating a canonical JOIN.\n"
        "• Root Cause of Regressions (14 queries with DISTINCT Mismatch): In queries such as Idx 76 (students with pets), "
        "generating explicit joins caused parent row duplication. The model omitted SELECT DISTINCT, producing a multiset mismatch.\n\n"
        "This empirical evidence directly defines Stage 8B: Cardinality & DISTINCT Reform, targeting row multiplicity to push "
        "Yale Execution Accuracy past the 85.5% mark."
    )

    output_path = os.path.join(os.path.dirname(__file__), "Stage_8A_Routing_Report.docx")
    doc.save(output_path)
    print(f"[SUCCESS] Exported Stage 8A Report to {output_path}")

if __name__ == "__main__":
    create_stage8a_document()
