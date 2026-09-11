"""
Minimal stdlib-only .xlsx writer (zipfile + hand-written Open XML).
No openpyxl or any third-party dependency — matches this project's
"stdlib only" constraint (see requirements.txt).

General-purpose version of the technique used in social-mcp's build_excel.py,
factored so any caller can build a multi-sheet workbook without re-writing
the Content_Types/rels/workbook boilerplate each time.
"""

import zipfile
from xml.sax.saxutils import escape as xe

# ── Style indices (defined in DEFAULT_STYLES_XML below) ────────────────
STYLE_DEFAULT     = 0
STYLE_TITLE       = 1   # bold white on blue — sheet/section title banner
STYLE_HEADER_BLUE = 2   # bold white on dark blue — table header row
STYLE_HEADER_GOLD = 3   # bold black on gold — secondary section header
STYLE_CELL_WHITE  = 4   # plain data cell
STYLE_CELL_LIGHT  = 5   # alternating-row data cell (light pink tint)
STYLE_LINK        = 6   # underlined blue — hyperlink cell
STYLE_TOTAL       = 7   # bold data cell — totals/summary row

DEFAULT_STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="6">
    <font><sz val="10"/><name val="Segoe UI"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Segoe UI"/></font>
    <font><b/><sz val="10"/><color rgb="FF1A1A2E"/><name val="Segoe UI"/></font>
    <font><sz val="10"/><color rgb="FF1A1A2E"/><name val="Segoe UI"/></font>
    <font><b/><sz val="10"/><color rgb="FF1A1A2E"/><name val="Segoe UI"/></font>
    <font><sz val="10"/><color rgb="FF004B91"/><u/><name val="Segoe UI"/></font>
  </fonts>
  <fills count="6">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF004B91"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFC200"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFFFFF"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF0F0"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFD0D0D0"/></left>
      <right style="thin"><color rgb="FFD0D0D0"/></right>
      <top style="thin"><color rgb="FFD0D0D0"/></top>
      <bottom style="thin"><color rgb="FFD0D0D0"/></bottom>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="8">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="4" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="5" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="5" fillId="4" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
    <xf numFmtId="0" fontId="4" fillId="4" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
  </cellXfs>
</styleSheet>"""


def col_letter(n):
    """1-based column index -> spreadsheet column letters (1 -> A, 27 -> AA)."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def cell(ref, value, style=STYLE_DEFAULT, t="inlineStr"):
    """Return a <c> element. t='n' for numeric, 'inlineStr' for text."""
    if value is None or value == "":
        return f'<c r="{ref}" s="{style}"/>'
    if t == "n":
        return f'<c r="{ref}" s="{style}" t="n"><v>{value}</v></c>'
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{xe(str(value))}</t></is></c>'


def merge(r1, c1, r2, c2):
    return f'<mergeCell ref="{col_letter(c1)}{r1}:{col_letter(c2)}{r2}"/>'


def row_xml(r, cells, height=None):
    h = f' ht="{height}" customHeight="1"' if height else ""
    return f'<row r="{r}"{h}>{"".join(cells)}</row>'


def hlink(ref, url, display, rid, style=STYLE_LINK):
    """
    Return (cell_xml, (rid, url)) for a hyperlinked cell. Caller collects the
    (rid, url) pairs into a dict and passes it to rels_xml()/write_xlsx().
    rid must be unique per sheet — use an incrementing counter, not a hash
    (hashes can collide and silently overwrite another link's relationship).
    """
    c = f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{xe(str(display))}</t></is></c>'
    return c, (rid, url)


def hyperlinks_xml(hlink_entries):
    """hlink_entries: list of (ref, rid) pairs -> the <hyperlinks> block for a worksheet."""
    if not hlink_entries:
        return ""
    parts = ["<hyperlinks>"]
    for ref, rid in hlink_entries:
        parts.append(f'<hyperlink ref="{ref}" r:id="rId{rid}"/>')
    parts.append("</hyperlinks>")
    return "".join(parts)


def rels_xml(hlinks_rels):
    """hlinks_rels: dict[int rid] -> url."""
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for rid, url in hlinks_rels.items():
        parts.append(f'<Relationship Id="rId{rid}" '
                      f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                      f'Target="{xe(url)}" TargetMode="External"/>')
    parts.append("</Relationships>")
    return "\n".join(parts)


def write_xlsx(path, sheets):
    """
    sheets: list of (sheet_name, worksheet_xml, hyperlink_rels_or_None)
    hyperlink_rels: dict[int rid] -> url, or None if the sheet has no hyperlinks.
    """
    n = len(sheets)

    content_types = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
                      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
                      '<Default Extension="xml" ContentType="application/xml"/>',
                      '<Override PartName="/xl/workbook.xml" '
                      'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
    for i in range(1, n + 1):
        content_types.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                              f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    content_types.append('<Override PartName="/xl/styles.xml" '
                          'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>')
    content_types.append('</Types>')

    sheets_xml = "".join(
        f'<sheet name="{xe(name)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, (name, _, _) in enumerate(sheets, 1)
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{sheets_xml}</sheets></workbook>'
    )

    wb_rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for i in range(1, n + 1):
        wb_rels.append(f'<Relationship Id="rId{i}" '
                       f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                       f'Target="worksheets/sheet{i}.xml"/>')
    wb_rels.append(f'<Relationship Id="rId{n + 1}" '
                   f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
                   f'Target="styles.xml"/>')
    wb_rels.append('</Relationships>')

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "\n".join(content_types))
        zf.writestr("_rels/.rels",
                     '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                     '<Relationship Id="rId1" '
                     'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                     'Target="xl/workbook.xml"/></Relationships>')
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", "\n".join(wb_rels))
        zf.writestr("xl/styles.xml", DEFAULT_STYLES_XML)

        for i, (_, ws_xml, hlink_rels) in enumerate(sheets, 1):
            zf.writestr(f"xl/worksheets/sheet{i}.xml", ws_xml)
            if hlink_rels:
                zf.writestr(f"xl/worksheets/_rels/sheet{i}.xml.rels", rels_xml(hlink_rels))
