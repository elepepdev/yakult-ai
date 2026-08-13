import warnings
from typing import Dict, Optional

warnings.filterwarnings("ignore", message="This package.*has been renamed")
from ddgs import DDGS  # noqa: E402


class WebSearcher:
    def search(
        self,
        query: str,
        max_results: int = 15,
        region: Optional[str] = None,
        timelimit: Optional[str] = None,
    ) -> Dict:
        try:
            params = {}
            if region:
                params["region"] = region
            if timelimit:
                params["timelimit"] = timelimit
            with DDGS() as ddgs:
                results = list(ddgs.text(query, **params))[:max_results]
            formatted = []
            for r in results:
                formatted.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    }
                )
            return {
                "success": True,
                "query": query,
                "results": formatted,
                "total": len(formatted),
            }
        except Exception as e:
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "results": [],
                "total": 0,
            }

    def search_news(
        self,
        query: str,
        max_results: int = 15,
        timelimit: Optional[str] = None,
    ) -> Dict:
        try:
            params = {}
            if timelimit:
                params["timelimit"] = timelimit
            with DDGS() as ddgs:
                results = list(ddgs.news(query, **params))[:max_results]
            formatted = []
            for r in results:
                formatted.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("body", ""),
                        "date": r.get("date", ""),
                        "source": r.get("source", ""),
                    }
                )
            return {
                "success": True,
                "query": query,
                "results": formatted,
                "total": len(formatted),
            }
        except Exception as e:
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "results": [],
                "total": 0,
            }
