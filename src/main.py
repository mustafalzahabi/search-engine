from js import Response, Headers, URL
from workers import WorkerEntrypoint
import json
import os

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

        # 1. Operational API Endpoints
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

        # 2. Static Frontend Asset Routing - Flattened Paths
        try:
            # Route individual CSS stylesheet
            if path == "/style.css":
                headers.set("Content-Type", "text/css; charset=utf-8")
                with open("style.css", "r") as f:
                    return Response.new(f.read(), headers=headers)

            # Route client JS application modules
            elif path == "/app.js":
                headers.set("Content-Type", "application/javascript; charset=utf-8")
                with open("app.js", "r") as f:
                    return Response.new(f.read(), headers=headers)

            # Serve base HTML page on root (/) or direct requests
            elif path == "/" or path == "/index.html":
                headers.set("Content-Type", "text/html; charset=utf-8")
                with open("index.html", "r") as f:
                    return Response.new(f.read(), headers=headers)

        except Exception as err:
            headers.set("Content-Type", "application/json")
            return Response.new(json.dumps({"error": f"Asset routing read failure: {str(err)}"}), headers=headers)

        # Catch-all if an unmapped route is hit
        headers.set("Content-Type", "application/json")
        return Response.new(json.dumps({"error": "Resource asset path not found."}), headers=headers)
