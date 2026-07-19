# Search Engine

A lightweight, high-performance web crawler and dynamic vector search engine built natively for the edge using **Cloudflare Workers (Python)** and **Cloudflare D1**. 

This application uses a modular architecture that splits serverless API operations from static frontend presentation files, keeping the codebase clean, organized, and production-ready.

---

## 🛠 Project Architecture

The workspace utilizes an isolated directory mapping pattern separating data processing structures from static client assets:

```text
search-engine/
│
├── wrangler.toml         # Cloudflare deployment configuration
│
├── public/               # Decoupled frontend presentation layer
│   ├── index.html        # Structural markup web UI
│   ├── style.css         # Sleek dark-mode system styles
│   └── app.js            # Client network event controllers
│
└── src/                  # Edge computing API microservices
    ├── main.py           # HTTP routing gateway hub
    ├── crawler.py        # Web scraping and database pipeline
    └── search.py         # Cosine metric vector calculations
```

---

## 🚀 Deployment Configuration

The application maps the static client assets directory using the native `[assets]` binding while routing script parameters directly into a serverless SQLite pipeline via D1.

### wrangler.toml

```toml
name = "search-engine"
main = "src/main.py"
compatibility_date = "2026-07-19"
compatibility_flags = [ "python_workers", "disable_python_external_sdk" ]

[assets]
directory = "./public"

[[d1_databases]]
binding = "DB"
database_name = "search-index-db"
database_id = "YOUR_CLOUDFLARE_D1_DATABASE_ID"
```

---

## 💻 Code Specifications

### Gateway Controller (src/main.py)

Intercepts incoming requests, processes routing rules dynamically using native URL APIs, and proxies unresolved asset routes to the edge file-server framework:

```python
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

        return await self.env.ASSETS.fetch(request)
```

### Client Application Event Router (public/app.js)

Communicates seamlessly with the shared domain, feeding target payloads directly into your backend loops:

```javascript
const API_ROOT = window.location.origin;

async function executeCrawl() {
    const targetUrl = document.getElementById('crawlInput').value.trim();
    const status = document.getElementById('crawlStatus');
    if (!targetUrl) return;

    status.innerHTML = "⚡ Spider crawling target layers...";
    try {
        const response = await fetch(`${API_ROOT}/crawl?url=${encodeURIComponent(targetUrl)}`);
        const data = await response.json();
        if (data.error) {
            status.innerHTML = `❌ Failure: ${data.error}`;
        } else {
            status.innerHTML = `✅ Complete! Indexed ${data.pages_crawled} pages.`;
        }
    } catch (err) {
        status.innerHTML = "❌ Connection failed.";
    }
}
```

---

## ⚡ Step-by-Step Execution

1. **Deploy Engine Infrastructure:**
   Ensure your D1 relational database instance is active, copy the `database_id` into `wrangler.toml`, and initialize deployment:
   ```bash
   npx wrangler deploy
   ```

2. **Ingest Target Web Layers:**
   Open the production site domain, paste a seed target link (e.g., a Wikipedia topic page) into the crawl terminal input, and click **Crawl & Index**. The system will scan links, map token occurrences, and populate the D1 index arrays.

3. **Execute High-Dimensional Searches:**
   Enter multi-token keyword configurations into the search input. The engine evaluates spatial matrix intersections using combined Cosine Similarity and Simpson Overlap parameters, sorting the matched results in descending ranking configurations.
