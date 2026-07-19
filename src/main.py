from js import Response, Headers, fetch
from workers import WorkerEntrypoint
import json
import math
import re
from collections import Counter

TOKEN_RE = re.compile(r"\W+")

def tokenize(text):
    return [t.lower().strip() for t in TOKEN_RE.split(text) if t and len(t) > 0]

# Helper function to extract text and links from raw HTML using standard regexes
def parse_html(html, base_url):
    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.IGNORECASE | re.DOTALL)
    body_content = body_match.group(1) if body_match else html
    
    clean_text = re.sub(r"<script[^>]*>.*?</script>", " ", body_content, flags=re.IGNORECASE | re.DOTALL)
    clean_text = re.sub(r"<style[^>]*>.*?</style>", " ", clean_text, flags=re.IGNORECASE | re.DOTALL)
    clean_text = re.sub(r"<[^>]+>", " ", clean_text)
    
    links = set()
    for match in re.finditer(r'href=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE):
        url = match.group(1)
        if url.startswith(base_url) or "example.com" in url:
            links.add(url)
            
    return clean_text, list(links)

async def handle_crawl(url_to_crawl, env):
    if not url_to_crawl:
        return {"error": "No URL provided to crawl"}

    await env.DB.prepare("DROP TABLE IF EXISTS DocumentDictionary").run()
    await env.DB.prepare("DROP TABLE IF EXISTS TermDictionary").run()
    await env.DB.prepare("DROP TABLE IF EXISTS Posting").run()
    
    await env.DB.prepare("CREATE TABLE DocumentDictionary (DocId INTEGER PRIMARY KEY, DocumentName TEXT)").run()
    await env.DB.prepare("CREATE TABLE TermDictionary (termid INTEGER PRIMARY KEY, term TEXT)").run()
    await env.DB.prepare("CREATE TABLE Posting (termid INTEGER, docid INTEGER, tfidf REAL)").run()

    pages_to_crawl = [url_to_crawl]
    visited_docs = {}
    doc_tokens = {}
    global_term_df = Counter()
    doc_id_counter = 1
    max_pages = 3

    while pages_to_crawl and len(visited_docs) < max_pages:
        current_url = pages_to_crawl.pop(0)
        if current_url in visited_docs:
            continue
            
        try:
            res = await fetch(current_url, headers={"User-Agent": "CloudflareEdgeSpider"})
            if res.status != 200:
                continue
            html = await res.text()
            
            text_content, discovered_links = parse_html(html, url_to_crawl)
            visited_docs[current_url] = doc_id_counter
            
            await env.DB.prepare("INSERT INTO DocumentDictionary (DocId, DocumentName) VALUES (?, ?)")\
                .bind(doc_id_counter, current_url).run()
            
            tokens = tokenize(text_content)
            doc_tokens[doc_id_counter] = tokens
            
            for unique_term in set(tokens):
                global_term_df[unique_term] += 1
                
            for link in discovered_links:
                if link not in visited_docs:
                    pages_to_crawl.append(link)
                    
            doc_id_counter += 1
        except Exception:
            continue

    N = len(visited_docs)
    if N == 0:
        return {"error": "Could not access or parse target root URL."}

    term_ids = {}
    term_id_counter = 1
    for term in global_term_df.keys():
        term_ids[term] = term_id_counter
        await env.DB.prepare("INSERT INTO TermDictionary (termid, term) VALUES (?, ?)")\
            .bind(term_id_counter, term).run()
        term_id_counter += 1

    for docid, tokens in doc_tokens.items():
        tf_counts = Counter(tokens)
        for term, tf_count in tf_counts.items():
            df = global_term_df[term]
            idf = math.log((N / df), 10) if df > 0 else 0.0
            tfidf_score = tf_count * idf
            termid = term_ids[term]
            
            await env.DB.prepare("INSERT INTO Posting (termid, docid, tfidf) VALUES (?, ?, ?)")\
                .bind(termid, docid, tfidf_score).run()

    return {"status": "success", "pages_crawled": N}

async def handle_search(query_param, env):
    query_tokens = tokenize(query_param)
    if not query_tokens:
        return {"results": []}

    count_res = await env.DB.prepare("SELECT count(*) as total FROM DocumentDictionary").first()
    N = count_res.total if count_res else 0
    if N == 0:
        return {"error": "Index is blank. Run crawler pipeline step first."}

    term_infos, term_postings, missing_terms = {}, {}, []

    for term in query_tokens:
        row = await env.DB.prepare("SELECT termid FROM TermDictionary WHERE term = ?").bind(term).first()
        if not row:
            missing_terms.append(term)
        else:
            termid = row.termid
            df_res = await env.DB.prepare("SELECT COUNT(DISTINCT docid) as df FROM Posting WHERE termid = ?").bind(termid).first()
            df = df_res.df
            term_infos[term] = (termid, df)
            
            postings_rows = await env.DB.prepare("SELECT docid, tfidf FROM Posting WHERE termid = ?").bind(termid).all()
            term_postings[term] = [(p.docid, p.tfidf) for p in postings_rows.results]

    if missing_terms:
        return {"results": [], "error": f"Search terms not found in index layout: {missing_terms}"}

    doc_sets = [set(docid for docid, _ in postings) for postings in term_postings.values()]
    candidate_docs = set.intersection(*doc_sets) if doc_sets else set()

    if not candidate_docs:
        return {"results": []}

    len_rows = await env.DB.prepare("SELECT docid, SUM(tfidf*tfidf) as ssum FROM Posting GROUP BY docid").all()
    doc_lengths = {l.docid: math.sqrt(l.ssum if l.ssum is not None else 0.0) for l in len_rows.results}
    term_doc_tfidf = {term: {docid: float(tfidf) for docid, tfidf in postings} for term, postings in term_postings.items()}

    q_counts = Counter(query_tokens)
    q_weights = {}
    for term, cnt in q_counts.items():
        termid, df = term_infos[term]
        idf = math.log((N / df), 10) if df > 0 else 0.0
        q_weights[term] = cnt * idf

    q_len = math.sqrt(sum((w*w) for w in q_weights.values())) or 1.0
    results = []

    for docid in candidate_docs:
        dot = sum(q_weights[t] * term_doc_tfidf[t].get(docid, 0.0) for t in q_weights)
        d_len = doc_lengths.get(docid, 0.0)
        cosine = dot / (q_len * d_len) if d_len > 0 else 0.0
        
        term_count_res = await env.DB.prepare("SELECT COUNT(DISTINCT termid) as tcnt FROM Posting WHERE docid = ?").bind(docid).first()
        doc_term_count = term_count_res.tcnt or 0
        intersection_size = len([t for t in q_weights.keys() if docid in term_doc_tfidf[t]])
        simpson = intersection_size / min(len(q_weights), doc_term_count) if doc_term_count > 0 else 0.0
        
        name_res = await env.DB.prepare("SELECT DocumentName FROM DocumentDictionary WHERE DocId = ?").bind(docid).first()
        docname = name_res.DocumentName if name_res else "(unknown)"
        
        results.append({"name": docname, "cosine": round(cosine, 4), "simpson": round(simpson, 3)})

    results.sort(key=lambda x: x["cosine"], reverse=True)
    return {"results": results[:20]}

# --- NATIVE ENTRYPOINT CLASS REQUIRED BY CLOUDFLARE ---
from js import URL

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        headers = Headers.new()
        headers.set("Access-Control-Allow-Origin", "*")
        headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        headers.set("Access-Control-Allow-Headers", "*")
        headers.set("Content-Type", "application/json")
        
        if request.method == "OPTIONS":
            return Response.new("", headers=headers)

        # Use standard robust URL object parsing instead of raw string splitting
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

        return Response.new(json.dumps({"error": "Invalid endpoint parameters specified."}), headers=headers)
