import re
from pathlib import Path

CHAPTERS_DIR = Path("docs/paper/article-court/appendices/chapters")

for tex_file in CHAPTERS_DIR.glob("*.tex"):
    content = tex_file.read_text(encoding="utf-8")
    
    # 1. Replace colons in \label and \ref with hyphens
    def repl_label(m):
        cmd = m.group(1)
        lbl = m.group(2).replace(":", "-")
        return f"\\{cmd}{{{lbl}}}"
    
    content = re.sub(r"\\(label|ref)\{([^}]+)\}", repl_label, content)
    
    tex_file.write_text(content, encoding="utf-8")

print("Converted all LaTeX labels and refs from colons to hyphens.")
