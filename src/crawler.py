from js import fetch
import math
import re
from collections import Counter

TOKEN_RE = re.compile(r"\W+")

def tokenize(text):
    return [t.lower().strip() for t in TOKEN_RE.split(text) if t and len(t) > 0]

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
