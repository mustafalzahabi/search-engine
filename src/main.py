from workers import WorkerEntrypoint, Response
from js import Headers, URL
import json

# Modular component routing imports
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
        path = url_obj.pathname
        params = url_obj.searchParams

        if path.rstrip("/") == "/crawl":
            target_url = params.get("url")
            res_data = await handle_crawl(target_url, self.env)
            return Response.new(json.dumps(res_data), headers=headers)
            
        elif path.rstrip("/") == "/search":
            query_str = params.get("q") or ""
            res_data = await handle_search(query_str, self.env)
            return Response.new(json.dumps(res_data), headers=headers)

        return Response.new(json.dumps({"error": "Endpoint route not found"}), headers=headers, status=404)
