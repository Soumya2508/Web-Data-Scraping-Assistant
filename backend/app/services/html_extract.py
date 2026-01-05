"""
Universal HTML record extraction.

Provides flexible extraction strategies:
1. Selector-based: User provides CSS selector for repeating elements
2. Table-based: Auto-detect and extract from HTML tables
3. Fallback: Return empty if no pattern found
"""
from __future__ import annotations

import re
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag


def _clean_key(raw: str) -> str:
    """Clean a string to make it a valid field key."""
    raw = raw.strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    return raw.strip("_")


def _extract_class_suffix(class_name: str) -> str:
    """
    Extract a meaningful field name from a CSS class.
    
    Examples:
        product__title -> title
        card-header -> header
        item_price -> price
        ProductName -> productname
    """
    # Handle BEM-style: .block__element or .block--modifier
    if "__" in class_name:
        return _clean_key(class_name.split("__")[-1])
    if "--" in class_name:
        return _clean_key(class_name.split("--")[-1])
    # Handle camelCase or single words
    return _clean_key(class_name)


def _get_element_text(element: Tag) -> str:
    """Get clean text content from an element."""
    return element.get_text(" ", strip=True)


def _get_element_attribute(element: Tag, attr: str) -> Optional[str]:
    """Get an attribute value from an element."""
    value = element.get(attr)
    if value:
        return str(value).strip() if isinstance(value, str) else value[0] if value else None
    return None


def extract_records_with_selector(html: str, css_selector: str) -> list[dict[str, Any]]:
    """
    Extract records using a user-provided CSS selector.
    
    For each matching element, extracts:
    - Text content from child elements with meaningful class names
    - Common attributes like href, src, data-* attributes
    - Falls back to full text if no structured children found
    
    Args:
        html: Raw HTML content
        css_selector: CSS selector for repeating elements (e.g., ".product-card")
    
    Returns:
        List of records (dicts) extracted from matching elements
    """
    soup = BeautifulSoup(html, "lxml")
    elements = soup.select(css_selector)
    
    if not elements:
        return []
    
    records: list[dict[str, Any]] = []
    
    for idx, element in enumerate(elements):
        record: dict[str, Any] = {"_index": idx + 1}
        
        # Strategy 1: Extract attribute if the element itself is a link or image
        if element.name == "a":
            href = _get_element_attribute(element, "href")
            if href:
                record["link"] = href
        elif element.name == "img":
            src = _get_element_attribute(element, "src") or _get_element_attribute(element, "data-src")
            if src:
                record["src"] = src
            alt = _get_element_attribute(element, "alt")
            if alt:
                record["alt"] = alt

        # Strategy 2: Extract from children with class names
        for child in element.find_all(True, class_=True):
            classes = child.get("class", [])
            for cls in classes:
                field_name = _extract_class_suffix(cls)
                if field_name and len(field_name) >= 2:  # Ignore very short names
                    text = _get_element_text(child)
                    if text and field_name not in record:
                        record[field_name] = text
                    
                    # Also get href for links
                    if child.name == "a":
                        href = _get_element_attribute(child, "href")
                        if href:
                            record[f"{field_name}_url"] = href
                    
                    # Get src for images
                    if child.name == "img":
                        src = _get_element_attribute(child, "src") or _get_element_attribute(child, "data-src")
                        if src:
                            record[f"{field_name}_image"] = src
                        alt = _get_element_attribute(child, "alt")
                        if alt:
                            record[f"{field_name}_alt"] = alt
        
        # Strategy 3: Extract from data attributes on the parent
        for attr, value in element.attrs.items():
            if attr.startswith("data-") and value:
                field_name = _clean_key(attr.replace("data-", ""))
                if field_name and isinstance(value, str):
                    record[field_name] = value
        
        # Strategy 4: If no structured text fields found, get full text
        # (i.e., we only have _index, link, src, or alt, but no child-derived 'title' etc.)
        meta_keys = {"_index", "link", "src", "alt"}
        has_content_fields = any(k not in meta_keys for k in record.keys())

        if not has_content_fields:
            full_text = _get_element_text(element)
            if full_text:
                record["text"] = full_text
        
        # Remove _index if we have other fields
        if len(record) > 2:
            record.pop("_index", None)
        
        # Only add non-empty records
        if len(record) > 1 or (len(record) == 1 and "_index" not in record):
            records.append(record)
    
    return records


def extract_records_from_tables(html: str) -> list[dict[str, Any]]:
    """
    Extract records from HTML tables.
    
    Finds the largest table and extracts rows as records.
    
    Args:
        html: Raw HTML content
    
    Returns:
        List of records from the best table found
    """
    soup = BeautifulSoup(html, "lxml")
    
    best_records: list[dict[str, Any]] = []
    best_len = 0
    
    for table in soup.find_all("table"):
        headers: list[str] = []
        header_row = table.find("tr")
        
        if header_row:
            ths = header_row.find_all("th")
            if ths:
                headers = [th.get_text(" ", strip=True) for th in ths]
        
        if not headers and header_row:
            # Fallback: use first row cells as headers
            tds = header_row.find_all("td")
            headers = [td.get_text(" ", strip=True) for td in tds]
        
        # Clean headers
        headers = [h if h else f"col_{i+1}" for i, h in enumerate(headers)]
        
        if not headers:
            continue
        
        rows = table.find_all("tr")
        records: list[dict[str, Any]] = []
        
        for tr in rows[1:]:  # Skip header row
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])[:len(headers)]]
            if not any(cells):
                continue
            row = {headers[i]: (cells[i] if i < len(cells) else None) for i in range(len(headers))}
            records.append(row)
        
        if len(records) > best_len:
            best_len = len(records)
            best_records = records
    
    return best_records


def extract_records_from_html(
    html: str,
    css_selector: Optional[str] = None
) -> list[dict[str, Any]]:
    """
    Main extraction function following the priority:
    
    1. If CSS selector provided -> use selector-based extraction
    2. Else if tables detected -> use table extraction
    3. Else -> return empty list (caller should suggest XHR/Selenium)
    
    Args:
        html: Raw HTML content
        css_selector: Optional CSS selector for repeating elements
    
    Returns:
        List of extracted records
    """
    # Priority 1: User-provided selector
    if css_selector and css_selector.strip():
        return extract_records_with_selector(html, css_selector.strip())
    
    # Priority 2: Table extraction
    table_records = extract_records_from_tables(html)
    if table_records:
        return table_records
    
    # Priority 3: No pattern found
    return []


def extract_surface_text(html: str, *, max_table_rows: int = 3) -> tuple[str, str]:
    """
    Extract surface text for relevance checking.
    
    Returns title, headings, and sample table content.
    """
    soup = BeautifulSoup(html, "lxml")
    
    parts: list[str] = []
    
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if title:
        parts.append(title)
    
    for tag_name in ["h1", "h2", "h3"]:
        for tag in soup.find_all(tag_name)[:10]:
            text = tag.get_text(" ", strip=True)
            if text:
                parts.append(text)
    
    table_headers: list[str] = []
    for table in soup.find_all("table")[:5]:
        for th in table.find_all("th")[:50]:
            text = th.get_text(" ", strip=True)
            if text:
                table_headers.append(text)
        
        rows = table.find_all("tr")
        for tr in rows[:max_table_rows + 1]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])[:20]]
            parts.extend([c for c in cells if c])
    
    if table_headers:
        return (" \n".join(parts), "title_headings_tables")
    
    return (" \n".join(parts), "title_headings")


def detect_repeated_elements(html: str, min_count: int = 5) -> list[dict[str, Any]]:
    """
    Analyze HTML and suggest CSS selectors for repeated elements.
    
    Returns a list of suggestions with class name and count.
    """
    soup = BeautifulSoup(html, "lxml")
    
    class_counts: dict[str, int] = {}
    
    for element in soup.find_all(True, class_=True):
        for cls in element.get("class", []):
            class_counts[cls] = class_counts.get(cls, 0) + 1
    
    # Filter and sort by count
    suggestions = [
        {"selector": f".{cls}", "count": count}
        for cls, count in class_counts.items()
        if count >= min_count and len(cls) >= 3  # Ignore very short class names
    ]
    
    suggestions.sort(key=lambda x: x["count"], reverse=True)
    
    return suggestions[:10]  # Top 10 suggestions
