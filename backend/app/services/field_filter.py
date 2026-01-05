"""
Field filtering and fuzzy matching utilities.

Provides normalization-based fuzzy matching to filter extracted records
to only include user-requested fields.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


def normalize_field_name(name: str) -> str:
    """
    Normalize a field name for fuzzy matching.
    
    Removes underscores, dashes, spaces and lowercases everything.
    Examples:
        company_name -> companyname
        companyName -> companyname
        Company Name -> companyname
        rating_count -> ratingcount
    """
    # Lowercase
    name = name.lower()
    # Remove underscores, dashes, spaces, and other non-alphanumeric
    name = re.sub(r"[^a-z0-9]", "", name)
    return name


@dataclass
class FieldMatchResult:
    """Result of matching requested fields against available fields."""
    matched_fields: dict[str, str]  # requested -> actual field name
    unmatched_requested: list[str]  # requested fields that had no match
    all_available_fields: list[str]  # all fields found in records


def match_requested_fields(
    records: list[dict[str, Any]],
    requested_fields: list[str],
) -> FieldMatchResult:
    """
    Match requested field names against actual fields in records using fuzzy matching.
    
    Args:
        records: List of extracted records (dicts)
        requested_fields: User-specified field names to filter for
    
    Returns:
        FieldMatchResult with matched/unmatched info
    """
    if not records:
        return FieldMatchResult(
            matched_fields={},
            unmatched_requested=list(requested_fields),
            all_available_fields=[],
        )
    
    # Collect all unique field names from all records
    all_fields: set[str] = set()
    for record in records:
        all_fields.update(record.keys())
    
    all_fields_list = sorted(all_fields)
    
    # Build normalized -> actual field mapping
    normalized_to_actual: dict[str, str] = {}
    for field in all_fields_list:
        norm = normalize_field_name(field)
        # If multiple fields normalize to the same thing, prefer shorter/simpler names
        if norm not in normalized_to_actual or len(field) < len(normalized_to_actual[norm]):
            normalized_to_actual[norm] = field
    
    # Match requested fields
    matched: dict[str, str] = {}
    unmatched: list[str] = []
    
    for req in requested_fields:
        req_norm = normalize_field_name(req)
        if not req_norm:
            continue
        
        # Try exact normalized match first
        if req_norm in normalized_to_actual:
            matched[req] = normalized_to_actual[req_norm]
        else:
            # Try partial match (requested is substring of actual or vice versa)
            found = False
            for norm, actual in normalized_to_actual.items():
                if req_norm in norm or norm in req_norm:
                    matched[req] = actual
                    found = True
                    break
            if not found:
                unmatched.append(req)
    
    return FieldMatchResult(
        matched_fields=matched,
        unmatched_requested=unmatched,
        all_available_fields=all_fields_list,
    )


def filter_records_by_fields(
    records: list[dict[str, Any]],
    requested_fields: list[str],
) -> tuple[list[dict[str, Any]], FieldMatchResult]:
    """
    Filter records to only include requested fields.
    
    If requested_fields is empty, returns all records unchanged.
    Uses fuzzy matching to find the best field matches.
    
    Args:
        records: List of extracted records
        requested_fields: User-specified fields to keep
    
    Returns:
        Tuple of (filtered_records, match_result)
    """
    # If no specific fields requested, return all
    if not requested_fields:
        all_fields: set[str] = set()
        for record in records:
            all_fields.update(record.keys())
        
        return records, FieldMatchResult(
            matched_fields={},
            unmatched_requested=[],
            all_available_fields=sorted(all_fields),
        )
    
    match_result = match_requested_fields(records, requested_fields)
    
    if not match_result.matched_fields:
        # No matches found, return empty records but preserve match info
        return [], match_result
    
    # Get the actual field names to keep
    fields_to_keep = set(match_result.matched_fields.values())
    
    # Filter each record
    filtered: list[dict[str, Any]] = []
    for record in records:
        filtered_record = {k: v for k, v in record.items() if k in fields_to_keep}
        if filtered_record:  # Only include non-empty records
            filtered.append(filtered_record)
    
    return filtered, match_result
