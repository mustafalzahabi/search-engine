from js import Response, Headers, URL
from workers import WorkerEntrypoint
import json

from crawler import handle_crawl
from search import handle_search

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        headers = Headers.new()
        headers.set("Access-Control-Allow-Origin", "*")
        headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        headers.set("Access-Control-Allow-Headers", "*")
        headers.set("Content-Type", "application/json")
        
        if request.method == "OPTIONS":
            return Response.new("", headers=headers)

        url_obj = URL.new(request.url)
        path = url_obj.pathname.rstrip("/")

        # Route operational endpoints
        if path == "/crawl":
            target_url = url_obj.searchParams.get("url")
            res_data = await handle_crawl(target_url, self.env)
            return Response.new(json.dumps(res_data), headers=headers)
            
        elif path == "/search":
            query_str = url_obj.searchParams.get("q") or ""
            res_data = await handle_search(query_str, self.env)
            return Response.new(json.dumps(res_data), headers=headers)

        # Catch root / or unknown paths cleanly without crashing the Worker environment
        fallback_data = {
            "status": "online",
            "message": "Edge Vector API running successfully. Access endpoints via /crawl or /search."
        }
        return Response.new(json.dumps(fallback_data), headers=headers)
