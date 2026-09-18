import pytest
from app.services.search.duckduckgo_provider import DuckDuckGoSearchProvider
from app.services.fetcher import FetcherService


def test_duckduckgo_live_search():
    """Verify DuckDuckGo search returns valid non-empty results for a standard query."""
    provider = DuckDuckGoSearchProvider()
    query = "BPSC TRE 4.0 Computer Science official notification"
    
    results = provider.search(query, num_results=5)
    
    print(f"\n[DuckDuckGo Live Test] Query: '{query}' returned {len(results)} results:")
    for idx, item in enumerate(results, 1):
        print(f"  {idx}. [{item.source_type}] {item.title}")
        print(f"     URL: {item.url}")
        print(f"     Snippet snippet len: {len(item.snippet)} chars\n")
    
    assert isinstance(results, list)
    assert len(results) > 0, "DuckDuckGo search returned 0 results. Check internet connection or rate limits."
    assert results[0].url.startswith("http"), "Search result URL is missing or invalid."
    assert len(results[0].title) > 0, "Search result title is empty."


def test_duckduckgo_various_job_queries():
    """Verify DuckDuckGo search across different categories of government job queries."""
    provider = DuckDuckGoSearchProvider()
    queries = [
        "SSC CGL official notification application date",
        "UPSC Civil Services eligibility age limit",
        "IBPS PO recruitment notification salary",
        "RRB NTPC notification official website",
    ]

    print("\n[DuckDuckGo Multi-Query Test]")
    for query in queries:
        results = provider.search(query, num_results=3)
        print(f"  Query: '{query}' -> {len(results)} results")
        assert len(results) > 0, f"DuckDuckGo returned 0 results for query: '{query}'"


def test_duckduckgo_fetcher_integration():
    """Verify that URLs returned by DuckDuckGo can be successfully fetched for content extraction."""
    provider = DuckDuckGoSearchProvider()
    fetcher = FetcherService(timeout=10.0)
    query = "SSC CGL official notification"
    
    results = provider.search(query, num_results=3)
    assert len(results) > 0, "DuckDuckGo search returned 0 results."

    fetched_count = 0
    print(f"\n[DuckDuckGo Fetcher Integration Test] Query: '{query}'")
    for idx, item in enumerate(results, 1):
        text, content_hash = fetcher.fetch_url(item.url)
        content_len = len(text)
        print(f"  Result {idx}: {item.url}")
        print(f"    Fetched text length: {content_len} chars | Hash: {content_hash[:8] if content_hash else 'None'}")
        if content_len > 100:
            fetched_count += 1

    print(f"  Successfully fetched text from {fetched_count}/{len(results)} search result URLs.")
    assert fetched_count > 0, "Failed to fetch readable body text from any DuckDuckGo search result URL."


def test_duckduckgo_fallback_query():
    """Verify that long queries fall back gracefully to a 3-word query if no results returned."""
    provider = DuckDuckGoSearchProvider()
    # Extremely long query string
    long_query = "Detailed examination advertisement criteria for Bihar Public Service Commission Computer Science Teacher Recruitment 2026 Notification PDF"
    results = provider.search(long_query, num_results=3)
    
    print(f"\n[DuckDuckGo Fallback Test] Long Query ({len(long_query.split())} words) returned {len(results)} results")
    assert len(results) > 0, "Fallback query search failed to return results."


if __name__ == "__main__":
    print("=== Running Standalone DuckDuckGo Diagnostic Test ===")
    test_duckduckgo_live_search()
    test_duckduckgo_various_job_queries()
    test_duckduckgo_fetcher_integration()
    test_duckduckgo_fallback_query()
    print("=== ALL DUCKDUCKGO TESTS PASSED SUCCESSFULLY ===")

