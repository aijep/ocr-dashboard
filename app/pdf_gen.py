"""
Generates a simple, readable PDF from extracted OCR text using reportlab.
"""
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from xml.sax.saxutils import escape


def text_to_pdf(text: str, output_path: str | Path, title: str = "Extracted Text") -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(title), styles["Title"]), Spacer(1, 0.3 * inch)]

    if not text.strip():
        story.append(Paragraph("<i>No text was detected in this image.</i>", styles["Normal"]))
    else:
        # Preserve paragraph breaks; escape to avoid breaking reportlab's mini-markup
        for para in text.split("\n\n"):
            para = para.strip()
            if not para:
                continue
            safe = escape(para).replace("\n", "<br/>")
            story.append(Paragraph(safe, styles["Normal"]))
            story.append(Spacer(1, 0.15 * inch))

    doc.build(story)
    return output_path
