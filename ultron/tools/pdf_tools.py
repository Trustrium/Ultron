"""PDF utilities — merge, split, info. Uses pypdf (already a dependency)."""
from __future__ import annotations
from pathlib import Path


def merge_pdfs(paths: list, output: str = "") -> str:
    """Merge multiple PDFs (in order) into one."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return "pypdf not installed (pip install pypdf)."
    if not paths or len(paths) < 2:
        return "Provide at least two PDF paths to merge."
    writer = PdfWriter()
    try:
        for p in paths:
            pp = Path(p).expanduser()
            if not pp.exists():
                return f"File not found: {pp}"
            for page in PdfReader(str(pp)).pages:
                writer.add_page(page)
        out = Path(output).expanduser() if output else Path(paths[0]).expanduser().with_name("merged.pdf")
        if out.suffix.lower() != ".pdf":
            out = out.with_suffix(".pdf")
        with open(out, "wb") as f:
            writer.write(f)
        return f"Merged {len(paths)} PDFs -> {out}"
    except Exception as e:
        return f"Merge failed: {e}"


def split_pdf(path: str, ranges: str = "") -> str:
    """Split a PDF. With no ranges, splits into one file per page.
    `ranges` like '1-3,4-6' creates a file per range (1-based, inclusive)."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return "pypdf not installed (pip install pypdf)."
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {p}"
    try:
        reader = PdfReader(str(p))
        n = len(reader.pages)
        outputs = []
        if ranges.strip():
            for r in ranges.split(","):
                a, _, b = r.strip().partition("-")
                start = int(a) - 1
                end = int(b) - 1 if b else start
                w = PdfWriter()
                for i in range(max(0, start), min(n, end + 1)):
                    w.add_page(reader.pages[i])
                out = p.with_name(f"{p.stem}_p{start+1}-{end+1}.pdf")
                with open(out, "wb") as f:
                    w.write(f)
                outputs.append(out.name)
        else:
            for i in range(n):
                w = PdfWriter()
                w.add_page(reader.pages[i])
                out = p.with_name(f"{p.stem}_page{i+1}.pdf")
                with open(out, "wb") as f:
                    w.write(f)
                outputs.append(out.name)
        return f"Split into {len(outputs)} file(s): {', '.join(outputs[:8])}" + (" ..." if len(outputs) > 8 else "")
    except Exception as e:
        return f"Split failed: {e}"


def pdf_info(path: str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "pypdf not installed (pip install pypdf)."
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {p}"
    try:
        r = PdfReader(str(p))
        meta = r.metadata or {}
        title = meta.get("/Title", "")
        author = meta.get("/Author", "")
        return (f"{p.name}: {len(r.pages)} pages"
                + (f", title '{title}'" if title else "")
                + (f", author '{author}'" if author else ""))
    except Exception as e:
        return f"Could not read PDF: {e}"
