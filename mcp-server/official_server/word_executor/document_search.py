"""
Document Search Module
Search and locate paragraphs in Word documents using keyword matching
Strategy: Match longest possible sentence to ensure uniqueness
"""

from typing import List, Dict, Any, Optional, Tuple
import re


class DocumentSearcher:
    """Search and locate specific paragraphs in Word documents"""

    def __init__(self):
        pass

    def find_paragraph_by_text(
        self,
        paragraphs: List[Dict[str, Any]],
        search_text: str,
        min_match_length: int = 10
    ) -> Optional[int]:
        """
        Find paragraph containing the search text (longest match strategy)

        Args:
            paragraphs: List of paragraph info from DocumentReader
            search_text: Text to search for (should be as long as possible)
            min_match_length: Minimum length of search text (default: 10 chars)

        Returns:
            Index of first matching paragraph, or None if not found
        """

        if len(search_text.strip()) < min_match_length:
            raise ValueError(
                f"Search text too short ({len(search_text)} chars). "
                f"Minimum: {min_match_length} chars for unique matching."
            )

        # Normalize search text (remove extra spaces, case-insensitive)
        search_normalized = self._normalize_text(search_text)

        for para in paragraphs:
            para_text_normalized = self._normalize_text(para["text"])

            if search_normalized in para_text_normalized:
                return para["index"]

        return None

    def find_paragraph_by_keywords(
        self,
        paragraphs: List[Dict[str, Any]],
        keywords: List[str],
        require_all: bool = True
    ) -> Optional[int]:
        """
        Find paragraph containing keywords

        Args:
            paragraphs: List of paragraph info
            keywords: List of keywords to search for
            require_all: If True, all keywords must be present. If False, any keyword matches.

        Returns:
            Index of first matching paragraph, or None
        """

        if not keywords:
            raise ValueError("Keywords list cannot be empty")

        # Normalize keywords
        keywords_normalized = [self._normalize_text(kw) for kw in keywords]

        for para in paragraphs:
            para_text_normalized = self._normalize_text(para["text"])

            if require_all:
                # All keywords must be present
                if all(kw in para_text_normalized for kw in keywords_normalized):
                    return para["index"]
            else:
                # Any keyword matches
                if any(kw in para_text_normalized for kw in keywords_normalized):
                    return para["index"]

        return None

    def find_all_paragraphs_by_text(
        self,
        paragraphs: List[Dict[str, Any]],
        search_text: str
    ) -> List[int]:
        """
        Find all paragraphs containing search text

        Returns:
            List of matching paragraph indices
        """

        search_normalized = self._normalize_text(search_text)
        matches = []

        for para in paragraphs:
            para_text_normalized = self._normalize_text(para["text"])

            if search_normalized in para_text_normalized:
                matches.append(para["index"])

        return matches

    def extract_long_sentence_from_image_analysis(
        self,
        modification_prompt: str,
        min_length: int = 15
    ) -> Optional[str]:
        """
        Extract the longest sentence from modification prompt for searching

        Strategy: Find longest continuous text segment (likely from image OCR)

        Args:
            modification_prompt: The prompt from Stage 1
            min_length: Minimum sentence length to consider

        Returns:
            Longest extracted sentence, or None
        """

        # Look for sentences in the prompt (split by common delimiters)
        sentences = re.split(r'[。！？\n]', modification_prompt)

        # Filter and sort by length
        valid_sentences = [
            s.strip() for s in sentences
            if len(s.strip()) >= min_length
        ]

        if not valid_sentences:
            return None

        # Return longest sentence
        return max(valid_sentences, key=len)

    def extract_search_keywords_from_prompt(
        self,
        modification_prompt: str
    ) -> Dict[str, Any]:
        """
        Extract search information from modification prompt

        Looks for patterns like:
        - "定位关键词: xxx"
        - "关键句子: xxx"
        - "target text: xxx"

        Returns:
            {
                "long_text": str or None,     # Longest text for unique matching
                "keywords": List[str],         # Individual keywords
                "search_method": "text" or "keywords"
            }
        """

        result = {
            "long_text": None,
            "keywords": [],
            "search_method": "text"
        }

        # Pattern 1: Look for explicit "定位关键词" or "关键句子"
        keyword_patterns = [
            r'定位关键词[：:]\s*(.+)',
            r'关键句子[：:]\s*(.+)',
            r'target text[：:]\s*(.+)',
            r'search text[：:]\s*(.+)',
        ]

        for pattern in keyword_patterns:
            match = re.search(pattern, modification_prompt, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                # Remove quotes if present
                extracted = extracted.strip('"\'')

                if len(extracted) >= 15:
                    result["long_text"] = extracted
                    result["search_method"] = "text"
                    return result
                else:
                    # Too short, use as keywords
                    result["keywords"] = [kw.strip() for kw in extracted.split(',')]
                    result["search_method"] = "keywords"
                    return result

        # Pattern 2: Extract longest sentence from prompt (fallback)
        long_sentence = self.extract_long_sentence_from_image_analysis(modification_prompt)

        if long_sentence:
            result["long_text"] = long_sentence
            result["search_method"] = "text"
        else:
            # Last resort: extract any meaningful words
            words = re.findall(r'[\u4e00-\u9fa5]+', modification_prompt)
            result["keywords"] = [w for w in words if len(w) >= 2][:5]
            result["search_method"] = "keywords"

        return result

    def search_paragraph(
        self,
        paragraphs: List[Dict[str, Any]],
        modification_prompt: str
    ) -> Tuple[Optional[int], Dict[str, Any]]:
        """
        Smart search: automatically extract search info from prompt and find paragraph

        Returns:
            (paragraph_index or None, search_info dict)
        """

        # Extract search information
        search_info = self.extract_search_keywords_from_prompt(modification_prompt)

        # Try text search first (most reliable)
        if search_info["long_text"]:
            index = self.find_paragraph_by_text(
                paragraphs,
                search_info["long_text"],
                min_match_length=10
            )

            if index is not None:
                search_info["matched_index"] = index
                search_info["match_method"] = "long_text"
                return index, search_info

        # Fallback to keyword search
        if search_info["keywords"]:
            index = self.find_paragraph_by_keywords(
                paragraphs,
                search_info["keywords"],
                require_all=True
            )

            if index is not None:
                search_info["matched_index"] = index
                search_info["match_method"] = "keywords_all"
                return index, search_info

            # Try any keyword match
            index = self.find_paragraph_by_keywords(
                paragraphs,
                search_info["keywords"],
                require_all=False
            )

            if index is not None:
                search_info["matched_index"] = index
                search_info["match_method"] = "keywords_any"
                return index, search_info

        # Not found
        search_info["matched_index"] = None
        search_info["match_method"] = "none"
        return None, search_info

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (lowercase, remove extra spaces)"""

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        # Convert to lowercase
        text = text.lower()

        return text.strip()


def demo():
    """Demo usage"""

    searcher = DocumentSearcher()

    # Mock paragraphs
    paragraphs = [
        {"index": 0, "text": "这是文档的第一段，介绍了项目背景。"},
        {"index": 1, "text": "第二段描述了系统架构设计，包括前端和后端模块。"},
        {"index": 2, "text": "第三段详细说明了数据库设计方案，采用 PostgreSQL 数据库。"},
        {"index": 3, "text": "第四段介绍了API接口规范，使用 RESTful 风格。"},
        {"index": 4, "text": "最后一段总结了项目的关键技术点。"},
    ]

    print("=== Document Search Demo ===\n")

    # Test 1: Long text search
    print("Test 1: Search by long text")
    search_text = "详细说明了数据库设计方案"
    index = searcher.find_paragraph_by_text(paragraphs, search_text)
    print(f"Search text: '{search_text}'")
    print(f"Found at index: {index}")
    if index is not None:
        print(f"Paragraph: {paragraphs[index]['text']}\n")

    # Test 2: Keyword search
    print("Test 2: Search by keywords")
    keywords = ["API", "RESTful"]
    index = searcher.find_paragraph_by_keywords(paragraphs, keywords)
    print(f"Keywords: {keywords}")
    print(f"Found at index: {index}")
    if index is not None:
        print(f"Paragraph: {paragraphs[index]['text']}\n")

    # Test 3: Smart search from prompt
    print("Test 3: Smart search from modification prompt")
    prompt = """
    根据截图分析，需要修改数据库相关段落。
    定位关键词: 详细说明了数据库设计方案
    修改操作: 将 PostgreSQL 改为 MySQL
    """
    index, search_info = searcher.search_paragraph(paragraphs, prompt)
    print(f"Modification prompt:\n{prompt}")
    print(f"\nExtracted search info: {search_info}")
    print(f"Found at index: {index}")
    if index is not None:
        print(f"Paragraph: {paragraphs[index]['text']}")


if __name__ == "__main__":
    demo()
