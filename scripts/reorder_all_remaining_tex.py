import re
from pathlib import Path

CHAPTERS = Path("docs/paper/article-court/appendices/chapters")

def reorder_file(path: Path):
    text = path.read_text(encoding="utf-8")
    
    # Extract all floats: table, table*, figure, figure*
    # Float pattern
    float_pattern = re.compile(r"\\begin\{(table\*?|figure\*?)\}.*?\\end\{\1\}", re.DOTALL)
    
    # We want each float to be placed right above the first paragraph that \ref's its label.
    floats = list(float_pattern.finditer(text))
    if not floats:
        return
    
    # Map label -> (float_text, float_start, float_end)
    label_pattern = re.compile(r"\\label\{([^}]+)\}")
    
    # Let's inspect each float
    for fl in reversed(floats):
        fl_str = fl.group(0)
        m_lbl = label_pattern.search(fl_str)
        if not m_lbl:
            continue
        lbl = m_lbl.group(1)
        ref_str = f"\\ref{{{lbl}}}"
        
        # Find position of ref_str in text
        pos_ref = text.find(ref_str)
        if pos_ref != -1 and pos_ref < fl.start():
            # The ref is BEFORE the float! We need to move the float before the ref.
            # Remove float from its current place
            text = text[:fl.start()] + text[fl.end():]
            # Find the paragraph or sentence start before pos_ref
            # Let's find previous double newline before pos_ref
            para_start = text.rfind("\n\n", 0, pos_ref)
            if para_start == -1:
                para_start = 0
            else:
                para_start += 2
            # Insert float right at para_start
            text = text[:para_start] + fl_str + "\n\n" + text[para_start:]
    
    path.write_text(text, encoding="utf-8")
    print(f"✓ Reordered floats in {path.name}")

for fname in ["04_prompts_and_traces.tex", "05_news_shocks.tex", "06_stratified_errors.tex", "08_factorial_generalization.tex"]:
    reorder_file(CHAPTERS / fname)

