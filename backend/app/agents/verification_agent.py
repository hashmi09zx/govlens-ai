import logging
from typing import List, Dict, Any
from app.graph.state import ResearchState
from app.services.search.official import OfficialSourceSearch
from app.services.search.general import GeneralWebSearch
from app.services.fetcher import FetcherService
from app.services.llm import get_llm_service
from app.models.domain import Fact, classify_source_authority

logger = logging.getLogger(__name__)

EXHAUSTED_FALLBACK_STR = "Information could not be reliably determined from the available sources."

HIGH_RISK_FIELDS = [
    "application_deadline",
    "eligibility_education",
    "eligibility_age_limit",
    "vacancies_total",
    "application_fee_general",
    "exam_date",
    "application_portal_url",
]

BAD_CONVERSATIONAL_MARKERS = [
    "unable to",
    "forbidden",
    "403",
    "cannot view",
    "cannot retrieve",
    "as an ai",
    "sorry",
    "i'll need",
    "please provide",
    "i'm unable",
]


def verification_agent_node(state: ResearchState) -> ResearchState:
    """
    Node 6: Enforces Progressive Source Fallback across official (Levels 1-4) and secondary (Levels 5-7) sources.
    Never auto-claims non-official sources as official, corroborates multiple secondary sources when available,
    and only defaults to EXHAUSTED_FALLBACK_STR when all sources fail.
    """
    facts: List[Dict[str, Any]] = list(state.get("extracted_facts") or [])
    conflicts: List[Dict[str, Any]] = state.get("conflicts") or []
    rec = state.get("recruitment") or {}
    retry_counts: Dict[str, int] = dict(state.get("field_retry_counts") or {})

    logger.info("VerificationAgent running Progressive Source Fallback verification...")

    # Map resolved conflict values into facts
    resolved_conflict_map = {}
    for c in conflicts:
        if c.get("resolved") and c.get("resolved_value"):
            resolved_conflict_map[c["field"]] = c["resolved_value"]

    # Filter/update facts
    verified_facts: List[Dict[str, Any]] = []

    for f in facts:
        field = f.get("field")
        val = str(f.get("value", ""))
        val_low = val.lower()

        # Reject conversational LLM chatter
        if any(marker in val_low for marker in BAD_CONVERSATIONAL_MARKERS):
            continue

        # Classify authority level if not present
        if "authority_level" not in f:
            src_url = f.get("source_url") or f.get("source") or ""
            classification = classify_source_authority(url=src_url, title="", snippet="")
            f["authority_level"] = classification["authority_level"]
            f["official"] = classification["official"]
            f["source_type"] = classification["source_type"]

        if field in resolved_conflict_map:
            f["value"] = resolved_conflict_map[field]
            f["confidence"] = max(f.get("confidence", 0.5), 0.95)

        verified_facts.append(f)

    # Check max confidence per field
    field_max_confidence: Dict[str, float] = {}
    field_has_official: Dict[str, bool] = {}
    for f in verified_facts:
        field = f.get("field")
        if field:
            conf = f.get("confidence", 0.5)
            field_max_confidence[field] = max(field_max_confidence.get(field, 0.0), conf)
            if f.get("official", False) and conf >= 0.6:
                field_has_official[field] = True

    official_searcher = OfficialSourceSearch()
    general_searcher = GeneralWebSearch()
    fetcher = FetcherService()
    llm = get_llm_service()

    # Progressive Fallback verification loop for low confidence or missing high-risk fields
    for field in HIGH_RISK_FIELDS:
        max_conf = field_max_confidence.get(field, 0.0)
        current_retries = retry_counts.get(field, 0)

        # Level 1-4 Retry: Official Source Search
        if max_conf < 0.6 and current_retries < 2:
            logger.info(f"Field '{field}' confidence low ({max_conf:.2f}). Trying Priority 1-4 Official Search (attempt {current_retries + 1}/2)...")
            retry_counts[field] = current_retries + 1

            query = f"{rec.get('name', '')} {field.replace('_', ' ')} official notice"
            search_res = official_searcher.search(query, num_results=2)

            for s in search_res:
                text, hash_val = fetcher.fetch_url(s.url)
                body_text = text[:3000] if text else s.snippet
                if body_text and len(body_text) > 30:
                    prompt = (
                        f"Extract ONLY the concise factual value for '{field}' from text:\n{body_text}\n"
                        "Do not include conversational phrases, excuses, or headers."
                    )
                    try:
                        val = llm.invoke(prompt=prompt, model_tier="fast")
                        val_str = str(val).strip()
                        val_low = val_str.lower()

                        if val_str and not any(marker in val_low for marker in BAD_CONVERSATIONAL_MARKERS):
                            classification = classify_source_authority(url=s.url, title=s.title, snippet=s.snippet)
                            new_fact = Fact(
                                field=field,
                                value=val_str[:300],
                                source=s.title or s.url,
                                source_url=s.url,
                                source_type=classification["source_type"],
                                authority_level=classification["authority_level"],
                                official=classification["official"],
                                confidence=0.85 if classification["official"] else 0.70,
                            ).model_dump()
                            verified_facts.append(new_fact)
                            field_max_confidence[field] = new_fact["confidence"]
                            if classification["official"]:
                                field_has_official[field] = True
                            break
                    except Exception as e:
                        logger.warning(f"Official re-search failed for '{field}': {e}")

        # Level 5-7 Fallback: Reputed Secondary & Job Info Sources
        if field_max_confidence.get(field, 0.0) < 0.6 and current_retries < 3:
            logger.info(f"Field '{field}' official search unavailable/low-confidence. Fallback to Priority 5-7 Secondary Sources...")
            retry_counts[field] = current_retries + 1

            gen_query = f"{rec.get('name', '')} {field.replace('_', ' ')}"
            gen_res = general_searcher.search(gen_query, num_results=3)

            secondary_extracted_facts = []
            for s in gen_res:
                text, hash_val = fetcher.fetch_url(s.url)
                body_text = text[:3000] if text else s.snippet
                if body_text and len(body_text) > 30:
                    prompt = (
                        f"Extract ONLY the concise factual value for '{field}' from text:\n{body_text}\n"
                        "Do not include conversational phrases, excuses, or headers."
                    )
                    try:
                        val = llm.invoke(prompt=prompt, model_tier="fast")
                        val_str = str(val).strip()
                        val_low = val_str.lower()
                        if val_str and not any(marker in val_low for marker in BAD_CONVERSATIONAL_MARKERS):
                            classification = classify_source_authority(url=s.url, title=s.title, snippet=s.snippet)
                            secondary_extracted_facts.append({
                                "value": val_str[:300],
                                "url": s.url,
                                "title": s.title or s.url,
                                "classification": classification,
                            })
                    except Exception as e:
                        logger.warning(f"Secondary re-search failed for '{field}': {e}")

            if secondary_extracted_facts:
                # Group secondary facts to check for multi-source agreement
                val_map: Dict[str, List[Dict[str, Any]]] = {}
                for sf in secondary_extracted_facts:
                    v_norm = sf["value"].strip().lower()
                    val_map.setdefault(v_norm, []).append(sf)

                best_v_norm = max(val_map.keys(), key=lambda k: len(val_map[k]))
                agreed_items = val_map[best_v_norm]
                first_item = agreed_items[0]
                cls = first_item["classification"]
                corroborating_urls = [item["url"] for item in agreed_items]

                is_multi_agree = len(corroborating_urls) > 1
                conf_score = 0.85 if is_multi_agree else 0.70

                new_fact = Fact(
                    field=field,
                    value=first_item["value"],
                    source=first_item["title"],
                    source_url=first_item["url"],
                    source_type=cls["source_type"],
                    authority_level=cls["authority_level"],
                    official=False,  # Strictly false for secondary fallback
                    confidence=conf_score,
                    corroborating_sources=corroborating_urls if is_multi_agree else [],
                ).model_dump()
                verified_facts.append(new_fact)
                field_max_confidence[field] = conf_score

        # Final Fallback: Exhausted all priority levels
        if field_max_confidence.get(field, 0.0) < 0.6:
            logger.info(f"Field '{field}' remains unresolved across all source levels. Emitting explicit exhausted fallback.")
            verified_facts.append(
                Fact(
                    field=field,
                    value=EXHAUSTED_FALLBACK_STR,
                    source="verification_pipeline_exhausted",
                    source_url="",
                    source_type="blog_forum",
                    authority_level=7,
                    official=False,
                    confidence=1.0,
                ).model_dump()
            )

    status = dict(state.get("research_status", {}))
    status["verification_agent"] = "completed"

    return {
        **state,
        "verified_facts": verified_facts,
        "field_retry_counts": retry_counts,
        "research_status": status,
    }

