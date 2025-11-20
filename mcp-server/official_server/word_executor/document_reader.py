"""
Document Reader Module
Reads Word documents and extracts paragraph information including text, style, and formatting
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from docx import Document
from docx.text.paragraph import Paragraph
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import RGBColor


class DocumentReader:
    """Read and parse Word documents"""

    def __init__(self):
        pass

    def read_word_document(self, file_path: str) -> Dict[str, Any]:
        """
        Read complete Word document with full metadata

        Args:
            file_path: Path to Word document (.docx)

        Returns:
            {
                "file_path": str,
                "total_paragraphs": int,
                "paragraphs": [
                    {
                        "index": int,
                        "text": str,
                        "style": str,
                        "alignment": str,
                        "font_name": str,
                        "font_size": float,
                        "bold": bool,
                        "italic": bool,
                        "underline": bool,
                        "color_rgb": tuple or None
                    },
                    ...
                ]
            }
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        if path.suffix.lower() not in ['.docx']:
            raise ValueError(f"Unsupported file type: {path.suffix}. Only .docx is supported.")

        doc = Document(str(path))

        paragraphs_info = []
        for idx, para in enumerate(doc.paragraphs):
            para_info = self._extract_paragraph_info(para, idx)
            paragraphs_info.append(para_info)

        return {
            "file_path": str(path.resolve()),
            "total_paragraphs": len(paragraphs_info),
            "paragraphs": paragraphs_info
        }

    def _extract_paragraph_info(self, paragraph: Paragraph, index: int) -> Dict[str, Any]:
        """Extract detailed information from a paragraph"""

        # Basic text and style
        text = paragraph.text
        style_name = paragraph.style.name if paragraph.style else "Normal"

        # Alignment
        alignment = self._get_alignment_name(paragraph.alignment)

        # Font information (from first run, or default)
        font_info = self._extract_font_info(paragraph)

        return {
            "index": index,
            "text": text,
            "style": style_name,
            "alignment": alignment,
            "font_name": font_info.get("font_name"),
            "font_size": font_info.get("font_size"),
            "bold": font_info.get("bold", False),
            "italic": font_info.get("italic", False),
            "underline": font_info.get("underline", False),
            "color_rgb": font_info.get("color_rgb")
        }

    def _extract_font_info(self, paragraph: Paragraph) -> Dict[str, Any]:
        """Extract font information from paragraph runs"""

        if not paragraph.runs:
            return {
                "font_name": None,
                "font_size": None,
                "bold": False,
                "italic": False,
                "underline": False,
                "color_rgb": None
            }

        # Get info from first run (representative)
        first_run = paragraph.runs[0]
        font = first_run.font

        # Font size (in points)
        font_size = None
        if font.size:
            font_size = font.size.pt

        # Color
        color_rgb = None
        if font.color and font.color.rgb:
            color_rgb = (font.color.rgb[0], font.color.rgb[1], font.color.rgb[2])

        return {
            "font_name": font.name,
            "font_size": font_size,
            "bold": font.bold or False,
            "italic": font.italic or False,
            "underline": font.underline or False,
            "color_rgb": color_rgb
        }

    def _get_alignment_name(self, alignment) -> str:
        """Convert alignment enum to readable string"""

        if alignment is None:
            return "LEFT"

        alignment_map = {
            WD_ALIGN_PARAGRAPH.LEFT: "LEFT",
            WD_ALIGN_PARAGRAPH.CENTER: "CENTER",
            WD_ALIGN_PARAGRAPH.RIGHT: "RIGHT",
            WD_ALIGN_PARAGRAPH.JUSTIFY: "JUSTIFY"
        }

        return alignment_map.get(alignment, "LEFT")

    def get_paragraph_by_index(self, doc_info: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
        """Get specific paragraph by index"""

        paragraphs = doc_info.get("paragraphs", [])

        if 0 <= index < len(paragraphs):
            return paragraphs[index]

        return None

    def get_context_paragraphs(
        self,
        doc_info: Dict[str, Any],
        target_index: int,
        context_size: int = 2
    ) -> Dict[str, Any]:
        """
        Get target paragraph with surrounding context

        Args:
            doc_info: Document information from read_word_document()
            target_index: Index of target paragraph
            context_size: Number of paragraphs before/after to include

        Returns:
            {
                "target": {...},
                "before": [{...}, {...}],
                "after": [{...}, {...}],
                "target_index": int
            }
        """

        paragraphs = doc_info.get("paragraphs", [])
        total = len(paragraphs)

        if not 0 <= target_index < total:
            raise ValueError(f"Invalid target_index: {target_index}. Total paragraphs: {total}")

        # Get context range
        start_idx = max(0, target_index - context_size)
        end_idx = min(total, target_index + context_size + 1)

        before = paragraphs[start_idx:target_index]
        target = paragraphs[target_index]
        after = paragraphs[target_index + 1:end_idx]

        return {
            "target": target,
            "before": before,
            "after": after,
            "target_index": target_index
        }


def demo():
    """Demo usage"""

    reader = DocumentReader()

    # Example: Read a Word document
    doc_path = Path(__file__).parent / "test_space" / "test.docx"

    if not doc_path.exists():
        print(f"Demo document not found: {doc_path}")
        print("Please create a test.docx file in test_space/")
        return

    print("Reading Word document...")
    doc_info = reader.read_word_document(str(doc_path))

    print(f"\nDocument: {doc_info['file_path']}")
    print(f"Total paragraphs: {doc_info['total_paragraphs']}")
    print("\nFirst 5 paragraphs:")

    for para in doc_info['paragraphs'][:5]:
        print(f"\n[{para['index']}] {para['style']}")
        print(f"  Text: {para['text'][:100]}")
        print(f"  Font: {para['font_name']}, Size: {para['font_size']}")
        print(f"  Bold: {para['bold']}, Italic: {para['italic']}")
        print(f"  Alignment: {para['alignment']}")


if __name__ == "__main__":
    demo()
