from concurrent.futures import ThreadPoolExecutor, as_completed
from tavily import TavilyClient
from models import EventGroup, SearchResults
from config import TAVILY_API_KEY, MAX_URLS_PER_GROUP, SEARCH_RESULTS_PER_KEYWORD

def deduplicate_urls(results: list) -> tuple:
    seen = set()
    urls = []
    snippets = {}
    for r in results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
            snippets[url] = r.get("content", "")
    return urls, snippets

def _search_keyword(client: TavilyClient, keyword: str) -> list:
    try:
        resp = client.search(
            query=keyword,
            search_depth="advanced",
            max_results=SEARCH_RESULTS_PER_KEYWORD,
        )
        return resp.get("results", [])
    except Exception:
        return []

def search_group(group: EventGroup) -> SearchResults:
    client = TavilyClient(api_key=TAVILY_API_KEY)
    all_results = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_search_keyword, client, kw): kw
            for kw in group.search_keywords
        }
        for future in as_completed(futures):
            all_results.extend(future.result())

    urls, snippets = deduplicate_urls(all_results)
    return SearchResults(
        group_name=group.group_name,
        urls=urls[:MAX_URLS_PER_GROUP],
        url_snippets={u: snippets[u] for u in urls[:MAX_URLS_PER_GROUP]},
    )
