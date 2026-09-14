"""
DOM Context Extractor — Intelligent Page HTML Trimming for LLM Input

Extracts a focused DOM fragment from the live page HTML, centered around
the probable location of a broken locator. This trimmed context is sent
to the LLM to minimize token usage while providing enough structural
information for accurate locator healing.

Key techniques:
- BeautifulSoup-based HTML parsing and traversal
- Script/style stripping to remove noise
- Parent-level expansion for structural context
- Character budget enforcement to stay within LLM token limits
"""

import re
import logging
from typing import Optional

from bs4 import BeautifulSoup, Tag, Comment

logger = logging.getLogger(__name__)


class DOMContextExtractor:
    """
    Extracts relevant DOM fragments from page HTML for LLM-based
    locator healing.

    The extractor trims the full page HTML to a focused fragment
    around the area where the broken element was expected, reducing
    token consumption while preserving the structural context needed
    for the LLM to suggest accurate replacement selectors.
    """

    def __init__(
        self,
        max_chars: int = 2000,
        include_parent_levels: int = 3,
        strip_scripts: bool = True,
        strip_styles: bool = True,
    ):
        """
        Initialize the DOM context extractor.

        Args:
            max_chars: Maximum character budget for the extracted DOM fragment.
            include_parent_levels: Number of parent levels to include above
                                   a located element for structural context.
            strip_scripts: Whether to remove <script> elements.
            strip_styles: Whether to remove <style> elements and style attributes.
        """
        self.max_chars = max_chars
        self.include_parent_levels = include_parent_levels
        self.strip_scripts = strip_scripts
        self.strip_styles = strip_styles

    def extract(
        self,
        page_html: str,
        broken_selector: str,
        selector_strategy: str = "css",
    ) -> str:
        """
        Extract a focused DOM fragment from page HTML.

        Strategy:
        1. Parse the full HTML with BeautifulSoup
        2. Try to find elements near the broken selector's context
        3. If found, expand to include parent elements for structure
        4. If not found, return a cleaned version of the <body>
        5. Trim to fit within the character budget

        Args:
            page_html: Full HTML source of the page.
            broken_selector: The CSS/XPath selector that failed.
            selector_strategy: Strategy type ("css", "xpath", "id", "text").

        Returns:
            Cleaned, trimmed HTML fragment as a string.
        """
        soup = BeautifulSoup(page_html, "lxml")

        # Step 1: Clean the DOM — remove noise
        self._clean_dom(soup)

        # Step 2: Try to locate context around the broken selector
        context_element = self._find_context_region(
            soup, broken_selector, selector_strategy
        )

        if context_element:
            # Step 3: Expand to parent levels for structural context
            fragment = self._expand_to_parents(context_element)
            result = self._prettify_and_trim(fragment)
            logger.info(
                "Extracted focused DOM context (%d chars) around selector: %s",
                len(result), broken_selector
            )
        else:
            # Step 4: Fallback — return the cleaned <body>
            body = soup.find("body")
            if body:
                result = self._prettify_and_trim(body)
            else:
                result = self._prettify_and_trim(soup)
            logger.info(
                "Could not locate context for selector '%s', "
                "returning cleaned body (%d chars)",
                broken_selector, len(result)
            )

        return result

    def extract_full_cleaned(self, page_html: str) -> str:
        """
        Return the full page HTML after cleaning (no context focusing).

        Useful when the broken selector gives no clues about location.

        Args:
            page_html: Full HTML source of the page.

        Returns:
            Cleaned HTML string within the character budget.
        """
        soup = BeautifulSoup(page_html, "lxml")
        self._clean_dom(soup)
        body = soup.find("body") or soup
        return self._prettify_and_trim(body)

    def _clean_dom(self, soup: BeautifulSoup):
        """Remove scripts, styles, comments, and other noise from the DOM."""
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Remove script elements
        if self.strip_scripts:
            for script in soup.find_all("script"):
                script.decompose()

        # Remove style elements
        if self.strip_styles:
            for style in soup.find_all("style"):
                style.decompose()

            # Remove inline style attributes (but keep class and id)
            for tag in soup.find_all(True):
                if tag.get("style"):
                    del tag["style"]

        # Remove hidden elements
        for tag in soup.find_all(True, attrs={"hidden": True}):
            tag.decompose()

        # Remove SVG and other non-essential elements
        for tag in soup.find_all(["svg", "noscript", "iframe", "meta", "link"]):
            tag.decompose()

    def _find_context_region(
        self,
        soup: BeautifulSoup,
        broken_selector: str,
        strategy: str,
    ) -> Optional[Tag]:
        """
        Attempt to find a DOM region related to the broken selector.

        Even though the exact selector is broken, we can often infer
        the region from partial matches (e.g., if the ID changed from
        'login-btn' to 'loginButton', we might find elements with
        'login' in their attributes).

        Args:
            soup: Parsed BeautifulSoup document.
            broken_selector: The broken selector string.
            strategy: Selector strategy ("css", "xpath", "id", "text").

        Returns:
            A Tag element near the probable location, or None.
        """
        # Extract meaningful tokens from the selector
        tokens = self._extract_selector_tokens(broken_selector, strategy)

        if not tokens:
            return None

        # Try to find elements with matching attributes
        for token in tokens:
            # Search by ID fragment
            for tag in soup.find_all(True, id=re.compile(token, re.IGNORECASE)):
                return tag

            # Search by class fragment
            for tag in soup.find_all(True, class_=re.compile(token, re.IGNORECASE)):
                return tag

            # Search by text content
            for tag in soup.find_all(True, string=re.compile(token, re.IGNORECASE)):
                return tag

            # Search by any attribute value
            for tag in soup.find_all(True):
                for attr_val in tag.attrs.values():
                    if isinstance(attr_val, str) and token.lower() in attr_val.lower():
                        return tag
                    elif isinstance(attr_val, list):
                        for v in attr_val:
                            if isinstance(v, str) and token.lower() in v.lower():
                                return tag

        return None

    def _extract_selector_tokens(
        self, selector: str, strategy: str
    ) -> list[str]:
        """
        Extract meaningful tokens from a selector for fuzzy matching.

        Examples:
            "#login-button" -> ["login", "button"]
            ".nav-bar .user-menu" -> ["nav", "bar", "user", "menu"]
            "//div[@id='main-content']" -> ["main", "content"]
        """
        # Remove common selector syntax
        cleaned = re.sub(r'[#.\[\]@=\'"():/]', ' ', selector)

        # Split on non-alphanumeric
        parts = re.split(r'[^a-zA-Z0-9]+', cleaned)

        # Filter out noise words and very short tokens
        noise_words = {
            "div", "span", "input", "button", "a", "p", "h1", "h2", "h3",
            "h4", "h5", "h6", "form", "table", "tr", "td", "th", "ul", "li",
            "id", "class", "type", "name", "value", "text", "xpath", "css",
            "contains", "and", "or", "not", "the",
        }

        tokens = [
            t for t in parts
            if len(t) >= 3 and t.lower() not in noise_words
        ]

        # Also split camelCase and PascalCase
        expanded = []
        for token in tokens:
            camel_parts = re.sub(r'([a-z])([A-Z])', r'\1 \2', token).split()
            expanded.extend([p for p in camel_parts if len(p) >= 3])

        return expanded if expanded else tokens

    def _expand_to_parents(self, element: Tag) -> Tag:
        """
        Expand the context by traversing up to parent elements.

        This provides structural context (forms, containers, nav bars)
        that helps the LLM understand what region of the page the
        broken element belongs to.

        Args:
            element: The located DOM element.

        Returns:
            A parent element providing sufficient context.
        """
        current = element
        for _ in range(self.include_parent_levels):
            parent = current.parent
            if parent and parent.name not in ("html", "[document]", "body"):
                current = parent
            else:
                break
        return current

    def _prettify_and_trim(self, element) -> str:
        """
        Convert a BeautifulSoup element to a prettified, trimmed string.

        Args:
            element: BeautifulSoup Tag or NavigableString.

        Returns:
            String representation within the character budget.
        """
        html = element.prettify() if hasattr(element, "prettify") else str(element)

        # Remove excessive whitespace
        html = re.sub(r'\n\s*\n', '\n', html)
        html = re.sub(r'  +', ' ', html)

        if len(html) <= self.max_chars:
            return html

        # Trim to budget, preserving complete tags
        trimmed = html[:self.max_chars]

        # Find the last complete tag boundary
        last_close = trimmed.rfind(">")
        if last_close > 0:
            trimmed = trimmed[:last_close + 1]

        trimmed += "\n<!-- ... DOM truncated for LLM context ... -->"

        return trimmed
