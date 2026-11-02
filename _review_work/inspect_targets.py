# -*- coding: utf-8 -*-
from docx import Document
from docx.oxml.ns import qn

path = r"C:\Users\Administrator\Desktop\xlwcc\11-1_修改稿.docx"
out = r"C:\Users\Administrator\Desktop\xlwcc\_review_work\targets.txt"

doc = Document(path)
targets = [0,1,2,9,10,139,155,160,165,173,174,186,187,189,190,191,192,194,196,198,202,203,204,205,206,207,209,210,213,217,218,220,221,222,223,224,225,226,228,229,230,231]

with open(out, "w", encoding="utf-8") as fh:
    for i in targets:
        p = doc.paragraphs[i]
        fh.write(f"\n===== P{i} style={p.style.name!r} align={p.alignment} =====\n")
        fh.write("TEXT: " + p.text + "\n")
        fh.write(f"RUNS: {len(p.runs)}\n")
        for j, r in enumerate(p.runs):
            f = r.font
            fh.write(f"  r{j}: bold={f.bold} italic={f.italic} size={f.size} name={f.name!r} text={r.text!r}\n")
    fh.write("\n===== TABLE STYLES =====\n")
    for ti, t in enumerate(doc.tables):
        fh.write(f"TABLE {ti}: style={t.style.name!r} rows={len(t.rows)} cols={len(t.columns)}\n")
        fh.write("  tblPr: " + (t._tbl.tblPr.xml[:800] if t._tbl.tblPr is not None else "None") + "\n")

print("WROTE", out)
