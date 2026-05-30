#!/usr/bin/env python3
"""
render_deck.py — Renders a deck-spec YAML into a ServiceNow-themed PowerPoint.

Usage: python3 render_deck.py <path-to>.deck_spec.yaml

To iterate: edit the deck_spec YAML, re-run this script.
Content lives in the spec; this file only changes when new slide types are added.
"""
import os
import sys
import zipfile
import yaml
from lxml import etree
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn

# ── ServiceNow brand colors ──────────────────────────────────────────────────
SN_TEAL      = RGBColor(0x00, 0xC7, 0xB1)
SN_NAVY      = RGBColor(0x29, 0x3E, 0x40)
SN_ORANGE    = RGBColor(0xF2, 0x6B, 0x43)
SN_SLATE     = RGBColor(0x5B, 0x7B, 0x8C)
SN_WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
SN_LIGHT     = RGBColor(0xF5, 0xF5, 0xF5)
SN_MID_GRAY  = RGBColor(0xCC, 0xCC, 0xCC)
SN_DARK_GRAY = RGBColor(0x44, 0x44, 0x44)

# Spec color name → RGBColor
COLOR_MAP = {
    "sn_teal":   SN_TEAL,
    "sn_navy":   SN_NAVY,
    "sn_orange": SN_ORANGE,
    "sn_slate":  SN_SLATE,
}
# Light tints for alternating data rows / section backgrounds
TINT_MAP = {
    "sn_teal":   RGBColor(0xE6, 0xF9, 0xF7),
    "sn_navy":   RGBColor(0xE8, 0xEC, 0xED),
    "sn_orange": RGBColor(0xFD, 0xEF, 0xE8),
    "sn_slate":  RGBColor(0xEC, 0xEF, 0xF2),
}

# ── Layout indices in the SN template ───────────────────────────────────────
L_COVER_GREEN = 0
L_TITLE_ONLY  = 10

# ── Validation ───────────────────────────────────────────────────────────────
# Required top-level spec keys
REQUIRED_SPEC_KEYS = ["template", "output", "slides"]

# Required fields per slide type — extend this dict when adding new types
REQUIRED_SLIDE_FIELDS = {
    "cover_green":         ["title"],
    "four_section_grid":   ["title", "sections"],
    "scoring_table":       ["title", "groups"],
    "scoring_table_with_rubric": ["title", "groups"],
    "scoring_guide":       ["title", "rows", "weights"],
}

def validate_spec(spec, spec_path):
    """Pre-render validation. Raises SystemExit with a clear message on failure.

    Checks:
    - Required top-level keys are present
    - Template file exists on disk
    - Output directory exists
    - All slide types are registered in RENDERERS
    - Required fields per slide type are present

    How to extend:
    - Add new type: insert into REQUIRED_SLIDE_FIELDS above
    - Add new top-level key: insert into REQUIRED_SPEC_KEYS above
    - Add new per-slide check: extend the loop body below
    """
    errors = []

    # Top-level keys
    for key in REQUIRED_SPEC_KEYS:
        if key not in spec:
            errors.append(f"  ✗ spec missing required key: '{key}'")

    if errors:
        _fail(errors, spec_path)

    # Template file
    template_path = spec["template"]
    if not os.path.isfile(template_path):
        errors.append(f"  ✗ template file not found: {template_path}")

    # Output directory
    output_path = spec["output"]
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.isdir(output_dir):
        errors.append(f"  ✗ output directory does not exist: {output_dir}")

    # Slides
    slides = spec.get("slides", [])
    if not slides:
        errors.append("  ✗ spec has no slides")

    for i, slide_def in enumerate(slides):
        slide_type = slide_def.get("type")
        if not slide_type:
            errors.append(f"  ✗ slide[{i}] missing 'type'")
            continue
        if slide_type not in RENDERERS:
            errors.append(
                f"  ✗ slide[{i}] unknown type '{slide_type}'. "
                f"Known: {', '.join(sorted(RENDERERS))}"
            )
        required = REQUIRED_SLIDE_FIELDS.get(slide_type, [])
        for field in required:
            if field not in slide_def:
                errors.append(
                    f"  ✗ slide[{i}] type='{slide_type}' missing required field '{field}'"
                )

    if errors:
        _fail(errors, spec_path)

    print(f"  ✓ spec valid  ({len(slides)} slides)")


def validate_output(output_path, expected_slides):
    """Post-render validation. Checks the generated PPTX for known breakage patterns.

    Checks:
    - Output file exists and is non-zero
    - No duplicate zip entries (the most common source of broken PPTX)
    - Slide count in sldIdLst matches expected

    How to extend:
    - Add new check: append to the function body
    - Common repair situations to watch for:
        * Duplicate relationships (rId collision): extend clear_slides() diagnosis
        * Missing media: add check for ppt/media/ entries referenced from slides
        * Corrupt content_types: add check that [Content_Types].xml lists all parts

    To programmatically check if an EXISTING .pptx needs repair (without opening it):
        python3 render_deck.py --check-repair path/to/file.pptx
    See check_needs_repair() below.
    """
    errors = []

    if not os.path.isfile(output_path):
        errors.append(f"  ✗ output file not created: {output_path}")
        _fail(errors, output_path)

    size = os.path.getsize(output_path)
    if size == 0:
        errors.append(f"  ✗ output file is empty: {output_path}")
        _fail(errors, output_path)

    # Duplicate zip entry check
    with zipfile.ZipFile(output_path, "r") as zf:
        names = [info.filename for info in zf.infolist()]
        seen = set()
        dupes = []
        for name in names:
            if name in seen:
                dupes.append(name)
            seen.add(name)
        if dupes:
            errors.append(
                "  ✗ broken PPTX: duplicate zip entries found "
                f"(sign of orphaned slide parts): {dupes}\n"
                "    Root cause: clear_slides() did not drop OPC relationships.\n"
                "    Fix: ensure prs.part.drop_rel(rId) is called for each slide in clear_slides()."
            )

    # Slide count check
    prs_check = Presentation(output_path)
    actual = len(prs_check.slides)
    if actual != expected_slides:
        errors.append(
            f"  ✗ slide count mismatch: expected {expected_slides}, got {actual}"
        )

    if errors:
        _fail(errors, output_path)

    print(f"  ✓ output valid  ({size // 1024} KB, {actual} slides, no duplicate entries)")


def check_needs_repair(pptx_path):
    """Programmatically check if an existing .pptx file needs repair.

    Checks performed:
    1. Duplicate zip entries — indicates orphaned slide parts from a broken clear_slides()
    2. Unresolvable slide relationships — slide listed in sldIdLst but part not in zip

    Usage:
        python3 render_deck.py --check-repair path/to/file.pptx

    Returns True if repair needed, False if clean.
    Prints a human-readable diagnosis.
    """
    issues = []

    if not os.path.isfile(pptx_path):
        print(f"  ✗ file not found: {pptx_path}")
        return True

    print(f"\nChecking: {pptx_path}")

    with zipfile.ZipFile(pptx_path, "r") as zf:
        names = [info.filename for info in zf.infolist()]
        seen = set()
        dupes = []
        for name in names:
            if name in seen:
                dupes.append(name)
            seen.add(name)
        if dupes:
            issues.append(f"  ✗ duplicate zip entries: {dupes}")
        else:
            print("  ✓ no duplicate zip entries")

        # Check sldIdLst references resolve to actual parts
        from lxml import etree
        prs_xml = zf.read("ppt/presentation.xml")
        root = etree.fromstring(prs_xml)
        ns = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
              "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
        rels_xml = zf.read("ppt/_rels/presentation.xml.rels")
        rels_root = etree.fromstring(rels_xml)
        rel_map = {r.get("Id"): r.get("Target") for r in rels_root}
        sld_id_lst = root.find(".//p:sldIdLst", ns)
        if sld_id_lst is not None:
            for sld_id in sld_id_lst:
                r_id = sld_id.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                target = rel_map.get(r_id)
                if target:
                    part_path = f"ppt/{target}"
                    if part_path not in names:
                        issues.append(f"  ✗ sldIdLst rId={r_id} → {target} not found in zip")
                else:
                    issues.append(f"  ✗ sldIdLst rId={r_id} has no matching relationship")
            if not issues:
                print(f"  ✓ all {len(list(sld_id_lst))} slide relationships resolve")

    if issues:
        print("\n  NEEDS REPAIR:")
        for issue in issues:
            print(issue)
        return True

    print("  ✓ file appears healthy")
    return False


def _fail(errors, context):
    print(f"\n✗ Validation failed ({context}):")
    for e in errors:
        print(e)
    sys.exit(1)


# ── Helpers ──────────────────────────────────────────────────────────────────
def load_spec(path):
    with open(path) as f:
        return yaml.safe_load(f)

def clear_slides(prs):
    """Remove slides AND their OPC relationships.

    drop_rel is the fix: without it, old slide parts stay in the package graph.
    New slides get the same partnames -> duplicate zip entries -> broken PPTX.
    """
    xml_slides = prs.slides._sldIdLst
    for sld_id in list(xml_slides):
        rId = sld_id.get(qn("r:id"))
        if rId:
            prs.part.drop_rel(rId)   # severs the part from the package graph
        xml_slides.remove(sld_id)


def add_slide(prs, layout_idx):
    return prs.slides.add_slide(prs.slide_layouts[layout_idx])

def ph(slide, idx):
    for p in slide.placeholders:
        if p.placeholder_format.idx == idx:
            return p
    return None

def set_ph_text(slide, ph_idx, text, size=None, bold=False):
    p = ph(slide, ph_idx)
    if not p:
        return
    tf = p.text_frame
    tf.clear()
    para = tf.paragraphs[0]
    run = para.add_run()
    run.text = text
    if size:
        run.font.size = Pt(size)
    if bold:
        run.font.bold = True

def clear_footer(slide):
    """Clear the template's footer placeholder so 'Footer' boilerplate doesn't appear."""
    fp = ph(slide, 11)
    if fp:
        fp.text = ""

def add_textbox(slide, left, top, width, height, text, size=12, bold=False,
                color=None, bg=None, align=PP_ALIGN.LEFT, wrap=True):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    if bg:
        tb.fill.solid()
        tb.fill.fore_color.rgb = bg
    tf = tb.text_frame
    tf.word_wrap = wrap
    para = tf.paragraphs[0]
    para.alignment = align
    run = para.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = color
    return tb

def add_rect(slide, left, top, width, height, fill_color, line_color=None):
    shape = slide.shapes.add_shape(1, Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color:
        shape.line.color.rgb = line_color
    else:
        shape.line.fill.background()
    return shape

def cell_text(cell, text, size=10, bold=False, italic=False,
              bg=None, fg=SN_NAVY, align=PP_ALIGN.LEFT):
    """Set a single run in a table cell with full formatting control."""
    cell.text = ""
    if bg:
        cell.fill.solid()
        cell.fill.fore_color.rgb = bg
    para = cell.text_frame.paragraphs[0]
    para.alignment = align
    run = para.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = fg


# ── SLIDE: cover_green ────────────────────────────────────────────────────────
def render_cover(prs, spec, slide_def):
    s = add_slide(prs, L_COVER_GREEN)
    set_ph_text(s, 0,  slide_def["title"])
    set_ph_text(s, 10, slide_def.get("subtitle", ""))
    set_ph_text(s, 11, slide_def.get("date", ""))
    return s


# ── SLIDE: four_section_grid ──────────────────────────────────────────────────
#
# 2×2 grid. Each section:
#   - Left strip  (tab_w=0.42"): solid group color, label text rotated 90° (reads upward)
#   - Body area   (box_w - tab_w): group color at 20% opacity (translucent over white)
#
# Layout (13.33" × 7.5" widescreen slide):
#   col_x = [0.22, 6.78]   row_y = [1.65, 4.47]   box_w = 6.33"   box_h = 2.65"
#
def render_four_section_grid(prs, spec, slide_def):
    s = add_slide(prs, L_TITLE_ONLY)
    clear_footer(s)
    set_ph_text(s, 0, slide_def["title"], size=20, bold=True)
    add_textbox(s, 0.22, 1.25, 12.89, 0.32,
                slide_def.get("subtitle", ""), size=11, color=SN_DARK_GRAY)

    sections = slide_def.get("sections", [])
    col_x  = [0.22, 6.78]
    row_y  = [1.65, 4.33]   # gap ≈ 0.13" between rows
    box_w  = 6.33
    box_h  = 2.55            # lower bottom: 4.33+2.55=6.88" (clear of footer)
    hdr_h  = 0.38            # solid color header band height
    body_h = box_h - hdr_h  # translucent body height

    positions = [
        (col_x[0], row_y[0]),
        (col_x[1], row_y[0]),
        (col_x[0], row_y[1]),
        (col_x[1], row_y[1]),
    ]

    SN_OFFWHITE = RGBColor(0xDD, 0xDD, 0xDD)

    for i, section in enumerate(sections[:4]):
        lx, ty = positions[i]
        color  = COLOR_MAP.get(section.get("color", "sn_navy"), SN_NAVY)

        # ── Header band (solid color, horizontal title) ────────────────────
        hdr = add_rect(s, lx, ty, box_w, hdr_h, fill_color=color)
        tf  = hdr.text_frame
        tf.word_wrap   = False
        tf.margin_left = Inches(0.12)
        tf.margin_top  = Inches(0.05)
        para = tf.paragraphs[0]
        para.alignment = PP_ALIGN.LEFT
        run = para.add_run()
        run.text           = section["label"].upper()
        run.font.size      = Pt(10)
        run.font.bold      = True
        run.font.color.rgb = SN_WHITE

        # ── Body area (translucent group color, 40% opacity) ───────────────
        body = add_rect(s, lx, ty + hdr_h, box_w, body_h, fill_color=color)
        try:
            xClr = body.fill.fore_color._xClr
            for el in xClr.findall(qn('a:alpha')):
                xClr.remove(el)
            alpha_el = etree.SubElement(xClr, qn('a:alpha'))
            alpha_el.set('val', '40000')   # 40% opaque
        except Exception:
            pass

        tf = body.text_frame
        tf.word_wrap    = True
        tf.margin_left  = Inches(0.13)
        tf.margin_right = Inches(0.08)
        tf.margin_top   = Inches(0.10)

        first = True
        for item in section.get("items", []):
            para = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            para.alignment = PP_ALIGN.LEFT
            if ":" in item:
                label_txt, rest = item.split(":", 1)
                r1 = para.add_run()
                r1.text           = label_txt + ":"
                r1.font.bold      = True
                r1.font.size      = Pt(9.5)
                r1.font.color.rgb = SN_WHITE
                r2 = para.add_run()
                r2.text           = rest
                r2.font.size      = Pt(9.5)
                r2.font.color.rgb = SN_OFFWHITE
            else:
                run = para.add_run()
                run.text           = item
                run.font.size      = Pt(9.5)
                run.font.color.rgb = SN_WHITE

    return s


# ── SLIDE: scoring_table ─────────────────────────────────────────────────────
#
# Column layout:
#   No systems (reference mode):   # (0.5) | Criterion (2.5) | Rubric Indicator (rest)
#   With systems (scoring mode):   # (0.5) | Criterion (2.0) | Rubric Indicator (rest) | sys×n
#
# Group membership is shown via colored header rows and colored ID cells.
# Anecdotes appear as italic gray text below the rubric indicator in the same cell.
#
def render_scoring_table(prs, spec, slide_def):
    s = add_slide(prs, L_TITLE_ONLY)
    clear_footer(s)
    set_ph_text(s, 0, slide_def["title"], size=20, bold=True)
    add_textbox(s, 0.45, 1.3, 12.4, 0.32,
                slide_def.get("subtitle", ""), size=11, color=SN_DARK_GRAY)

    systems   = slide_def.get("systems", [])
    groups    = slide_def.get("groups", [])
    sys_w     = 1.05
    crit_w    = 2.0 if systems else 2.5
    fixed_w   = 0.5 + crit_w + (sys_w * len(systems))
    assess_w  = 12.5 - fixed_w
    col_widths = [0.5, crit_w, assess_w] + [sys_w] * len(systems)
    headers    = ["#", "Criterion", "Rubric Indicator"] + systems

    # Flatten to: ("header", grp) | ("row", color_key, cr, parity)
    flat_rows = []
    for grp in groups:
        flat_rows.append(("header", grp))
        for parity, cr in enumerate(grp.get("criteria", [])):
            flat_rows.append(("row", grp.get("color", "sn_navy"), cr, parity % 2))

    # Table height: fill available space down to a guaranteed bottom margin
    TABLE_TOP     = 1.72
    SLIDE_H       = 7.5
    BOTTOM_MARGIN = 0.62   # clear of the template's footer/logo band
    table_h = SLIDE_H - TABLE_TOP - BOTTOM_MARGIN   # = 5.16"

    tbl = s.shapes.add_table(
        1 + len(flat_rows), len(col_widths),
        Inches(0.45), Inches(TABLE_TOP), Inches(12.5), Inches(table_h)
    ).table
    for ci, w in enumerate(col_widths):
        tbl.columns[ci].width = Inches(w)

    def cfmt_assess(cell, assess, anecdote, bg):
        cell.text = ""
        if bg:
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
        tf = cell.text_frame
        tf.word_wrap = True
        p1 = tf.paragraphs[0]
        r1 = p1.add_run()
        r1.text = assess
        r1.font.size = Pt(8.5)
        r1.font.color.rgb = SN_DARK_GRAY
        if anecdote:
            p2 = tf.add_paragraph()
            r2 = p2.add_run()
            r2.text = anecdote
            r2.font.size = Pt(8)
            r2.font.italic = True
            r2.font.color.rgb = RGBColor(0x77, 0x77, 0x77)

    # Header row
    for ci, hdr in enumerate(headers):
        cell_text(tbl.cell(0, ci), hdr, size=9, bold=True, bg=SN_NAVY, fg=SN_WHITE,
                  align=PP_ALIGN.CENTER if ci == 0 or ci >= 3 else PP_ALIGN.LEFT)

    # Data rows
    for ri, entry in enumerate(flat_rows):
        row_idx = ri + 1
        if entry[0] == "header":
            grp   = entry[1]
            color = COLOR_MAP.get(grp.get("color", "sn_navy"), SN_NAVY)
            for ci in range(len(col_widths)):
                c = tbl.cell(row_idx, ci)
                if ci == 1:
                    cell_text(c, grp.get("name", "").upper(), size=9, bold=True,
                              bg=color, fg=SN_WHITE)
                else:
                    cell_text(c, "", bg=color, fg=SN_WHITE)
        else:
            _, color_key, cr, parity = entry
            color  = COLOR_MAP.get(color_key, SN_NAVY)
            tint   = TINT_MAP.get(color_key, SN_LIGHT)
            row_bg = tint if parity == 0 else SN_WHITE

            cell_text(tbl.cell(row_idx, 0), cr["id"], size=9, bold=True,
                      bg=color, fg=SN_WHITE, align=PP_ALIGN.CENTER)
            cell_text(tbl.cell(row_idx, 1), cr["name"], size=9, bold=True,
                      bg=row_bg, fg=color)
            cfmt_assess(tbl.cell(row_idx, 2),
                        cr.get("assess", ""),
                        cr.get("anecdote", ""),
                        row_bg)
            for si in range(len(systems)):
                cell_text(tbl.cell(row_idx, 3 + si), "", size=9,
                          bg=row_bg, align=PP_ALIGN.CENTER)
    return s


# ── SLIDE: scoring_guide ──────────────────────────────────────────────────────
#
# Left  (x=0.45, w=5.6):  Score 0-3 table (Score | Meaning | What it means)
# Right (x=6.6,  w=6.5):  Group max-scores table (Group | Max Score | Note)
#
def render_scoring_guide(prs, spec, slide_def):
    s = add_slide(prs, L_TITLE_ONLY)
    clear_footer(s)
    set_ph_text(s, 0, slide_def["title"], size=20, bold=True)
    add_textbox(s, 0.45, 1.3, 12.4, 0.32,
                slide_def.get("subtitle", ""), size=11, color=SN_DARK_GRAY)

    score_rows = slide_def.get("rows", [])
    weights    = slide_def.get("weights", [])

    score_bg = [
        RGBColor(0x22, 0x7A, 0x5A),   # 3 — green
        RGBColor(0x2E, 0x7D, 0xB5),   # 2 — blue
        RGBColor(0xF2, 0x6B, 0x43),   # 1 — orange
        RGBColor(0xAA, 0x33, 0x22),   # 0 — red
    ]

    # ── Scoring guide table (left) ──
    sg_col_w = [0.55, 1.55, 3.5]
    row_h    = 0.52   # height per row (header + 4 data rows = 5 total)
    sg_tbl   = s.shapes.add_table(
        1 + len(score_rows), 3,
        Inches(0.45), Inches(1.75),
        Inches(sum(sg_col_w)),
        Inches(row_h * (1 + len(score_rows)))
    ).table
    for ci, w in enumerate(sg_col_w):
        sg_tbl.columns[ci].width = Inches(w)

    for ci, hdr in enumerate(["Score", "Meaning", "What it means"]):
        cell_text(sg_tbl.cell(0, ci), hdr, size=10, bold=True,
                  bg=SN_NAVY, fg=SN_WHITE,
                  align=PP_ALIGN.CENTER if ci == 0 else PP_ALIGN.LEFT)

    for ri, row in enumerate(score_rows):
        row_bg = SN_LIGHT if ri % 2 == 0 else SN_WHITE
        cell_text(sg_tbl.cell(ri+1, 0), row["score"], size=18, bold=True,
                  bg=score_bg[ri], fg=SN_WHITE, align=PP_ALIGN.CENTER)
        cell_text(sg_tbl.cell(ri+1, 1), row["meaning"], size=11, bold=True,
                  bg=row_bg, fg=SN_NAVY)
        cell_text(sg_tbl.cell(ri+1, 2), row["detail"], size=11,
                  bg=row_bg, fg=SN_DARK_GRAY)

    # ── Group max-scores table (right) ──
    tw_col_w = [2.8, 1.0, 2.7]
    tw_tbl   = s.shapes.add_table(
        1 + len(weights), 3,
        Inches(6.6), Inches(1.75),
        Inches(sum(tw_col_w)),
        Inches(row_h * (1 + len(weights)))
    ).table
    for ci, w in enumerate(tw_col_w):
        tw_tbl.columns[ci].width = Inches(w)

    for ci, hdr in enumerate(["Group", "Max Score", "Note"]):
        cell_text(tw_tbl.cell(0, ci), hdr, size=10, bold=True,
                  bg=SN_NAVY, fg=SN_WHITE,
                  align=PP_ALIGN.CENTER if ci == 1 else PP_ALIGN.LEFT)

    group_colors = [SN_TEAL, SN_ORANGE, SN_SLATE, SN_NAVY, SN_DARK_GRAY]
    for ri, row in enumerate(weights):
        is_total = row["tier"] == "Total"
        row_bg   = SN_NAVY if is_total else (SN_LIGHT if ri % 2 == 0 else SN_WHITE)
        fg_std   = SN_WHITE if is_total else SN_NAVY
        gc       = group_colors[ri] if ri < len(group_colors) and not is_total else SN_WHITE

        cell_text(tw_tbl.cell(ri+1, 0), row["tier"], size=11, bold=is_total,
                  bg=row_bg, fg=fg_std)
        cell_text(tw_tbl.cell(ri+1, 1), row["max"], size=11, bold=is_total,
                  bg=row_bg, fg=SN_ORANGE if not is_total else SN_WHITE,
                  align=PP_ALIGN.CENTER)
        cell_text(tw_tbl.cell(ri+1, 2), row.get("note", ""), size=10,
                  bg=row_bg, fg=SN_WHITE if is_total else SN_DARK_GRAY)
    return s


# ── MAIN ─────────────────────────────────────────────────────────────────────
RENDERERS = {
    "cover_green":               render_cover,
    "four_section_grid":         render_four_section_grid,
    "scoring_table":             render_scoring_table,
    "scoring_table_with_rubric": render_scoring_table,   # legacy alias
    "scoring_guide":             render_scoring_guide,
}


def main(spec_path):
    print(f"\nSpec: {spec_path}")

    spec = load_spec(spec_path)

    print("\n── Validating spec ─────────────────────────────────────────────")
    validate_spec(spec, spec_path)

    prs = Presentation(spec["template"])
    clear_slides(prs)

    print("\n── Rendering slides ────────────────────────────────────────────")
    for slide_def in spec["slides"]:
        renderer = RENDERERS.get(slide_def["type"])
        renderer(prs, spec, slide_def)
        print(f"  ✓ {slide_def['type']}: {slide_def.get('title', '')[:55]}")

    prs.save(spec["output"])

    print("\n── Validating output ───────────────────────────────────────────")
    validate_output(spec["output"], len(spec["slides"]))

    print(f"\nSaved → {spec['output']}\n")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--check-repair":
        needs = check_needs_repair(sys.argv[2])
        sys.exit(1 if needs else 0)
    elif len(sys.argv) >= 2:
        main(sys.argv[1])
    else:
        print("Usage:")
        print("  python3 render_deck.py <spec>.deck_spec.yaml          # render")
        print("  python3 render_deck.py --check-repair <file>.pptx     # check health")
        sys.exit(1)
