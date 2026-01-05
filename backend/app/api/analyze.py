from __future__ import annotations

import time
import copy
from typing import Any, Optional

from fastapi import APIRouter

from app.schemas import AnalyzeResponse, DecisionTraceEntry, DocumentAnalyzeRequest, SeleniumAnalyzeRequest, XhrAnalyzeRequest
from app.services.csv_store import write_records_to_csv
from app.services.field_filter import filter_records_by_fields
from app.services.html_extract import extract_records_from_html, extract_surface_text
from app.services.http_client import get_bytes, post_bytes, try_parse_json
from app.services.json_extract import extract_records_from_json, get_top_level_cursor
from app.services.pagination import run_pagination
from app.schemas.pagination import CursorPagination, PageParamPagination
from app.services.relevance import compute_relevance, passes_relevance
from app.services.selenium_runner import extract_records_with_selenium
from app.services.url_utils import with_query_param

router = APIRouter(prefix="/analyze", tags=["analyze"])



def _trace(step: str, ok: bool = True, ms: Optional[int] = None, details: Optional[dict[str, Any]] = None) -> DecisionTraceEntry:
    return DecisionTraceEntry(step=step, ok=ok, ms=ms, details=details)


def _inject_identifier(
    identifier: str, 
    var_name: str, 
    url: str, 
    params: dict[str, Any], 
    body: Optional[dict[str, Any]]
) -> tuple[str, dict[str, Any], Optional[dict[str, Any]]]:
    """Inject identifier into URL, params, or body (including GraphQL variables)."""
    # URL replacement: support {var_name} syntax
    new_url = url.replace(f"{{{var_name}}}", identifier)
    
    # Params
    new_params = copy.deepcopy(params)
    if var_name in new_params:
         new_params[var_name] = identifier

    # Body
    new_body = copy.deepcopy(body) if body is not None else None
    if new_body:
        if var_name in new_body:
            new_body[var_name] = identifier
        
        # GraphQL variables
        if "variables" in new_body and isinstance(new_body["variables"], dict):
            if var_name in new_body["variables"]:
                new_body["variables"][var_name] = identifier
                
    return new_url, new_params, new_body



@router.post("/document", response_model=AnalyzeResponse)
def analyze_document(payload: DocumentAnalyzeRequest) -> AnalyzeResponse:
    trace: list[DecisionTraceEntry] = []
    
    # Debug trace to verify payload
    trace.append(_trace("debug_config", ok=True, details={
        "batch_identifiers_count": len(payload.batch_identifiers) if payload.batch_identifiers else 0,
        "batch_var": payload.batch_variable_name
    }))

    def execute_pass(url: str) -> list[dict[str, Any]]:
        # Step 1: Fetch the HTML
        started = time.perf_counter()
        # Pass cookies if provided
        fetch = get_bytes(url, headers=payload.headers, cookies=payload.cookies)
        trace.append(_trace("fetch_document", ok=(fetch.status_code < 400), ms=int((time.perf_counter() - started) * 1000), details={"status": fetch.status_code, "final_url": fetch.url}))

        if fetch.status_code >= 400:
            trace.append(_trace("fetch_error", ok=False, details={"status": fetch.status_code, "url": url}))
            return []

        html = fetch.content.decode("utf-8", errors="replace")
        
        # Step 2: Determine extraction method
        extraction_method = "none"
        if payload.css_selector:
            extraction_method = "css_selector"
            trace.append(_trace("extraction_method", ok=True, details={"method": "css_selector", "selector": payload.css_selector}))
        else:
            extraction_method = "auto_detect"
            trace.append(_trace("extraction_method", ok=True, details={"method": "auto_detect", "note": "Will try tables, then fail if none found"}))

        # Step 3: Extract records
        preview_started = time.perf_counter()
        preview_records = extract_records_from_html(html, css_selector=payload.css_selector)
        trace.append(
            _trace(
                "extract_records",
                ok=bool(preview_records),
                ms=int((time.perf_counter() - preview_started) * 1000),
                details={"records": len(preview_records), "method": extraction_method},
            )
        )

        if not preview_records:
            # If no records, we just return empty list for this pass
            return []

        # Step 4: Pagination handling
        records: list[dict[str, Any]]

        if payload.pagination is None:
            records = preview_records
            trace.append(_trace("extract_html_records", ok=bool(records), details={"records": len(records)}))
        else:
            # Document pagination supports only page_param
            pagination = payload.pagination
            if not isinstance(pagination, PageParamPagination):
                trace.append(_trace("pagination_error", ok=False, details={"error": "Document mode supports only page_param pagination."}))
                return []

            first_page = pagination.start

            def fetch_and_parse_for_url(u: str) -> list[dict[str, Any]]:
                page_fetch = get_bytes(u, headers=payload.headers, cookies=payload.cookies)
                page_html = page_fetch.content.decode("utf-8", errors="replace")
                return extract_records_from_html(page_html, css_selector=payload.css_selector)

            def fetch_page(params: dict[str, Any]) -> list[dict[str, Any]]:
                # In document mode, we build URL with query param on the original URL (which might have injected ID)
                # Note: 'url' here is the one passed to execute_pass (already has ID injected)
                p_url = with_query_param(url, pagination.param, str(params[pagination.param]))
                return fetch_and_parse_for_url(p_url)

            pag_started = time.perf_counter()
            records, run = run_pagination(pagination=pagination, fetch_page=fetch_page)
            trace.append(
                _trace(
                    "pagination",
                    ok=True,
                    ms=int((time.perf_counter() - pag_started) * 1000),
                    details={
                        "type": pagination.type,
                        "pages_fetched": run.pages_fetched,
                        "records_total": run.records_total,
                        "stopped_reason": run.stopped_reason,
                        "start": first_page,
                        "end": pagination.end,
                    },
                )
            )
        
        return records

    all_records: list[dict[str, Any]] = []
    # Treat empty list the same as None
    identifiers = payload.batch_identifiers if payload.batch_identifiers else [None]

    for idx, identifier in enumerate(identifiers):
        curr_url = payload.url
        if identifier is not None:
             # Unconditional injection to fix 403 errors on unreplaced {id}
             target = f"{{{payload.batch_variable_name}}}"
             curr_url = curr_url.replace(target, str(identifier))
             
             trace.append(_trace("batch_iteration", ok=True, details={"identifier": identifier, "url": curr_url}))
        
        try:
            pass_records = execute_pass(curr_url)
            all_records.extend(pass_records)
        except Exception as e:
            trace.append(_trace("batch_error", ok=False, details={"identifier": identifier, "error": str(e)}))
        
        if payload.delay_ms > 0 and idx < len(identifiers) - 1:
            time.sleep(payload.delay_ms / 1000.0)

    records = all_records

    if not records:
        message = "No records found."
        if payload.css_selector:
            message += f" Selector '{payload.css_selector}' might be incorrect."
        else:
            message += " Auto-detection failed."

        return AnalyzeResponse(
            mode_used="document",
            has_data=False,
            message=message,
            csv_url=None,
            record_count=0,
            decision_trace=trace,
        )

    # Apply field filtering if requested_fields is provided
    original_count = len(records)
    filtered_records, field_match = filter_records_by_fields(records, payload.requested_fields)
    
    trace.append(
        _trace(
            "field_filtering",
            ok=True,
            details={
                "requested_fields": payload.requested_fields,
                "all_available_fields": field_match.all_available_fields,
                "matched_fields": field_match.matched_fields,
                "unmatched_requested": field_match.unmatched_requested,
                "records_before": original_count,
                "records_after": len(filtered_records),
            },
        )
    )

    # Use filtered records if filtering was applied, otherwise use all
    final_records = filtered_records if payload.requested_fields else records

    if not final_records:
        return AnalyzeResponse(
            mode_used="document",
            has_data=False,
            message=f"No records matched the requested fields. Available fields: {', '.join(field_match.all_available_fields[:10])}",
            csv_url=None,
            record_count=0,
            decision_trace=trace,
        )

    export = write_records_to_csv(final_records)
    trace.append(_trace("write_csv", ok=True, details={"export_id": export.export_id, "records": len(final_records)}))

    field_info = ""
    if payload.requested_fields and field_match.matched_fields:
        field_info = f" Filtered to {len(field_match.matched_fields)} fields."

    return AnalyzeResponse(
        mode_used="document",
        has_data=True,
        message=f"Extracted {len(final_records)} records from Document(s).{field_info}",
        csv_url=f"/download/{export.export_id}.csv",
        record_count=len(final_records),
        decision_trace=trace,
    )


@router.post("/xhr", response_model=AnalyzeResponse)
def analyze_xhr(payload: XhrAnalyzeRequest) -> AnalyzeResponse:
    trace: list[DecisionTraceEntry] = []
    
    # Log the configuration
    trace.append(_trace("xhr_config", ok=True, details={
        "method": payload.method,
        "has_body": payload.body is not None,
        "has_cookies": bool(payload.cookies),
        "delay_ms": payload.delay_ms,
        "max_retries": payload.max_retries,
    }))

    def extract_records_from_response(content: bytes, headers: dict[str, str]) -> tuple[list[dict[str, Any]], str]:
        content_type = (headers.get("Content-Type") or "").lower()
        parsed = try_parse_json(content)
        if parsed is not None or "application/json" in content_type:
            parsed = parsed if parsed is not None else try_parse_json(content)
            result = extract_records_from_json(parsed)
            if result is None:
                return ([], "json_no_records")
            trace.append(_trace("json_records", ok=True, details={"path": result.path, "records": len(result.records)}))
            return (result.records, "json")

        # Treat as HTML
        html = content.decode("utf-8", errors="replace")
        records = extract_records_from_html(html)
        trace.append(_trace("html_records_from_xhr", ok=bool(records), details={"records": len(records)}))
        return (records, "html")

    def execute_pass(url: str, params: dict[str, Any], body: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
        
        def fetch_once(fetch_params: dict[str, Any], body_override: Optional[dict[str, Any]] = None) -> tuple[bytes, dict[str, str], int]:
            started = time.perf_counter()
            if payload.method == "POST":
                final_body = body_override if body_override is not None else body
                res = post_bytes(url, headers=payload.headers, body=final_body, cookies=payload.cookies, max_retries=payload.max_retries)
            else:
                res = get_bytes(url, headers=payload.headers, params=fetch_params, cookies=payload.cookies, max_retries=payload.max_retries)
            
            trace.append(_trace("fetch_xhr", ok=(res.status_code < 400), ms=int((time.perf_counter()-started)*1000), details={"status": res.status_code}))
            return res.content, res.headers, res.status_code

        cursor_holder = {"cursor": None}
        def cursor_getter() -> Optional[str]: return cursor_holder["cursor"]
        def cursor_setter(v: Optional[str]) -> None: cursor_holder["cursor"] = v
        
        def fetch_page(p_params: dict[str, Any]) -> list[dict[str, Any]]:
            if payload.delay_ms > 0: time.sleep(payload.delay_ms / 1000.0)
            c, h, _ = fetch_once(p_params)
            recs, mode = extract_records_from_response(c, h)
            
            if payload.pagination and isinstance(payload.pagination, CursorPagination):
                parsed_json = try_parse_json(c)
                cursor_setter(get_top_level_cursor(parsed_json, payload.pagination.cursor_field))
                trace.append(_trace("cursor_update", ok=True, details={"cursor": cursor_getter()}))
                
            trace.append(_trace("xhr_extract", ok=True, details={"mode": mode, "records": len(recs)}))
            return recs

        if payload.pagination is None:
            c, h, _ = fetch_once(params)
            recs, mode = extract_records_from_response(c, h)
            trace.append(_trace("xhr_single", ok=True, details={"mode": mode, "records": len(recs)}))
            return recs
        else:
            pag_started = time.perf_counter()
            recs, run = run_pagination(
                pagination=payload.pagination, 
                fetch_page=fetch_page, 
                base_params=params,
                cursor_getter=cursor_getter if isinstance(payload.pagination, CursorPagination) else None,
                cursor_setter=cursor_setter if isinstance(payload.pagination, CursorPagination) else None
            )
            trace.append(_trace("pagination", ok=True, ms=int((time.perf_counter()-pag_started)*1000), details={"total": run.records_total, "pages": run.pages_fetched}))
            return recs

    all_records: list[dict[str, Any]] = []
    identifiers = payload.batch_identifiers or [None]
    
    for idx, identifier in enumerate(identifiers):
        curr_url, curr_params, curr_body = payload.api_url, dict(payload.params), payload.body
        
        if identifier is not None:
            curr_url, curr_params, curr_body = _inject_identifier(identifier, payload.batch_variable_name, curr_url, curr_params, curr_body)
            trace.append(_trace("batch_iteration", ok=True, details={"identifier": identifier}))
            
        try:
            pass_records = execute_pass(curr_url, curr_params, curr_body)
            all_records.extend(pass_records)
        except Exception as e:
            trace.append(_trace("batch_error", ok=False, details={"identifier": identifier, "error": str(e)}))
        
        # Delay between batch items (using same delay_ms setting)
        if payload.delay_ms > 0 and idx < len(identifiers) - 1:
            time.sleep(payload.delay_ms / 1000.0)
            
    records = all_records

    if not records:
        return AnalyzeResponse(
            mode_used="xhr",
            has_data=False,
            message="XHR response did not contain extractable records. If this endpoint is correct but requires JS rendering, enable Selenium explicitly.",
            csv_url=None,
            record_count=0,
            decision_trace=trace,
        )

    # Apply field filtering if requested_fields is provided
    original_count = len(records)
    filtered_records, field_match = filter_records_by_fields(records, payload.requested_fields)
    
    trace.append(
        _trace(
            "field_filtering",
            ok=True,
            details={
                "requested_fields": payload.requested_fields,
                "all_available_fields": field_match.all_available_fields,
                "matched_fields": field_match.matched_fields,
                "unmatched_requested": field_match.unmatched_requested,
                "records_before": original_count,
                "records_after": len(filtered_records),
            },
        )
    )

    # Use filtered records if filtering was applied, otherwise use all
    final_records = filtered_records if payload.requested_fields else records

    if not final_records:
        return AnalyzeResponse(
            mode_used="xhr",
            has_data=False,
            message=f"No records matched the requested fields. Available fields: {', '.join(field_match.all_available_fields[:10])}",
            csv_url=None,
            record_count=0,
            decision_trace=trace,
        )

    export = write_records_to_csv(final_records)
    trace.append(_trace("write_csv", ok=True, details={"export_id": export.export_id, "records": len(final_records)}))

    field_info = ""
    if payload.requested_fields and field_match.matched_fields:
        field_info = f" Filtered to {len(field_match.matched_fields)} fields."

    return AnalyzeResponse(
        mode_used="xhr",
        has_data=True,
        message=f"Extracted {len(final_records)} records from XHR response.{field_info}",
        csv_url=f"/download/{export.export_id}.csv",
        record_count=len(final_records),
        decision_trace=trace,
    )


@router.post("/selenium", response_model=AnalyzeResponse)
def analyze_selenium(payload: SeleniumAnalyzeRequest) -> AnalyzeResponse:
    trace: list[DecisionTraceEntry] = []

    def execute_pass(url: str) -> list[dict[str, Any]]:
        def fetch_and_extract(u: str) -> list[dict[str, Any]]:
            return extract_records_with_selenium(
                url=u,
                css_selector=payload.css_selector,
                wait_time=payload.wait_time,
                cookies=payload.cookies,
                scroll_count=payload.scroll_count,
                scroll_delay_ms=payload.scroll_delay_ms,
            )

        if payload.pagination is None:
            started = time.perf_counter()
            try:
                recs = fetch_and_extract(url)
                trace.append(_trace("selenium_extract", ok=bool(recs), ms=int((time.perf_counter()-started)*1000), details={"records": len(recs)}))
                return recs
            except Exception as exc:
                trace.append(_trace("selenium_extract", ok=False, details={"error": str(exc)}))
                return []
        else:
            if not isinstance(payload.pagination, PageParamPagination):
                trace.append(_trace("pagination_error", ok=False, details={"error": "Invalid pagination type"}))
                return []
            
            def fetch_page(params: dict[str, Any]) -> list[dict[str, Any]]:
                # Pagination param injection
                p_url = with_query_param(url, payload.pagination.param, str(params[payload.pagination.param]))
                return fetch_and_extract(p_url)
                
            pag_started = time.perf_counter()
            try:
                recs, run = run_pagination(payload.pagination, fetch_page)
                trace.append(_trace("pagination", ok=True, ms=int((time.perf_counter()-pag_started)*1000), details={"total": run.records_total, "pages": run.pages_fetched}))
                return recs
            except Exception as exc:
                 trace.append(_trace("pagination", ok=False, details={"error": str(exc)}))
                 return []

    all_records: list[dict[str, Any]] = []
    identifiers = payload.batch_identifiers or [None]

    for idx, identifier in enumerate(identifiers):
        curr_url = payload.url
        if identifier is not None:
             curr_url, _, _ = _inject_identifier(identifier, payload.batch_variable_name, curr_url, {}, None)
             trace.append(_trace("batch_iteration", ok=True, details={"identifier": identifier}))
        
        try:
            pass_records = execute_pass(curr_url)
            all_records.extend(pass_records)
        except Exception as e:
             trace.append(_trace("batch_error", ok=False, details={"identifier": identifier, "error": str(e)}))
             
        if payload.delay_ms > 0 and idx < len(identifiers) - 1:
            time.sleep(payload.delay_ms / 1000.0)

    records = all_records

    if not records:
        return AnalyzeResponse(
            mode_used="selenium",
            has_data=False,
            message="Selenium rendered the page, but no matching DOM elements produced records.",
            csv_url=None,
            record_count=0,
            decision_trace=trace,
        )

    # Apply field filtering if requested_fields is provided
    original_count = len(records)
    filtered_records, field_match = filter_records_by_fields(records, payload.requested_fields)
    
    trace.append(
        _trace(
            "field_filtering",
            ok=True,
            details={
                "requested_fields": payload.requested_fields,
                "all_available_fields": field_match.all_available_fields,
                "matched_fields": field_match.matched_fields,
                "unmatched_requested": field_match.unmatched_requested,
                "records_before": original_count,
                "records_after": len(filtered_records),
            },
        )
    )

    # Use filtered records if filtering was applied, otherwise use all
    final_records = filtered_records if payload.requested_fields else records

    if not final_records:
        return AnalyzeResponse(
            mode_used="selenium",
            has_data=False,
            message=f"No records matched the requested fields. Available fields: {', '.join(field_match.all_available_fields[:10])}",
            csv_url=None,
            record_count=0,
            decision_trace=trace,
        )

    export = write_records_to_csv(final_records)
    trace.append(_trace("write_csv", ok=True, details={"export_id": export.export_id, "records": len(final_records)}))

    field_info = ""
    if payload.requested_fields and field_match.matched_fields:
        field_info = f" Filtered to {len(field_match.matched_fields)} fields."

    return AnalyzeResponse(
        mode_used="selenium",
        has_data=True,
        message=f"Extracted {len(final_records)} records using Selenium.{field_info}",
        csv_url=f"/download/{export.export_id}.csv",
        record_count=len(final_records),
        decision_trace=trace,
    )
