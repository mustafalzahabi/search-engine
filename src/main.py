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
        
        if request.method == "OPTIONS":
            return Response.new("", headers=headers)

        url_obj = URL.new(request.url)
        path = url_obj.pathname

        # 1. API Endpoints
        if path.rstrip("/") == "/crawl":
            headers.set("Content-Type", "application/json")
            target_url = url_obj.searchParams.get("url")
            res_data = await handle_crawl(target_url, self.env)
            return Response.new(json.dumps(res_data), headers=headers)
            
        elif path.rstrip("/") == "/search":
            headers.set("Content-Type", "application/json")
            query_str = url_obj.searchParams.get("q") or ""
            res_data = await handle_search(query_str, self.env)
            return Response.new(json.dumps(res_data), headers=headers)

        # 2. Native Static Asset Fallback
        # If the path isn't /crawl or /search, let the environment fetch from the front-end folder
        return await self.env.ASSETS.fetch(request)
