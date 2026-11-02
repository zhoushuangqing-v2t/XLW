# -*- coding: utf-8 -*-
import sys
from docx import Document
from docx.oxml.ns import qn

path = r"C:\Users\Administrator\Desktop\xlwcc\11-1_修改稿.docx"
out = r"C:\Users\Administrator\Desktop\xlwcc\_review_work\docx_structure.txt"

doc = Document(path)

def flags(p):
    xml = p._p.xml
    f = []
    if "<w:drawing" in xml or "<w:pict" in xml:
        f.append("IMG")
    if "<m:oMath" in xml:
        f.append("MATH")
    if "<w:tab" in xml:
        f.append("TAB")
    if "<w:br" in xml:
        f.append("BR")
    return ",".join(f) if f else "-"

with open(out, "w", encoding="utf-8") as fh:
    fh.write("=== PARAGRAPHS ===\n")
    for i, p in enumerate(doc.paragraphs):
        text = p.text.replace("\n", " ").strip()
        # keep even empty paragraphs but mark them
        fh.write(f"[{i:04d}] style={p.style.name!r} flags={flags(p)} len={len(text)} | {text[:300]}\n")
    fh.write("\n=== TABLES ===\n")
    for ti, table in enumerate(doc.tables):
        fh.write(f"\n--- TABLE {ti} rows={len(table.rows)} cols={len(table.columns)} ---\n")
        for ri, row in enumerate(table.rows):
            cells = []
            for ci, cell in enumerate(row.cells):
                t = cell.text.replace("\n", " / ").strip()
                cells.append(f"c{ci}={t[:200]}")
            fh.write(f"  r{ri}: " + " | ".join(cells) + "\n")

print("WROTE", out)
print("paragraphs", len(doc.paragraphs), "tables", len(doc.tables))
