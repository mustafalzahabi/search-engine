from js import Response, Headers, json
import math
import re
from collections import Counter

TOKEN_RE = re.compile(r"\W+")

def tokenize(text):
    return [t.lower().strip() for t in TOKEN_RE.split(text) if t and len(t) > 0]

async def search_handler(request, env):
    # Setup CORS headers so your GitHub Pages frontend can talk to the API
    headers = Headers.new()
    headers.set("Access-Control-Allow-Origin", "*")
    headers.set("Access-Control-Allow-Methods", "GET, OPTIONS")
    headers.set("Access-Control-Allow-Headers", "*")
    headers.set("Content-Type", "application/json")
    
    if request.method == "OPTIONS":
        return Response.new("", headers=headers)

    # Extract the query from URL parameters (?q=your+search+terms)
    url = request.url
    query_param = ""
    if "?" in url:
        params = url.split("?")[1].split("&")
        for param in params:
            if param.startswith("q="):
                query_param = param.split("=")[1]
                query_param = query_param.replace("%20", " ").replace("+", " ")
                
    query_tokens = tokenize(query_param)
    if not query_tokens:
        return Response.new(json.stringify({"results": []}), headers=headers)

    # 1. Fetch total document count using the D1 database binding 'env.DB'
    count_res = await env.DB.prepare("SELECT count(*) as total FROM DocumentDictionary").first()
    N = count_res.total if count_res else 0

    term_infos = {}
    term_postings = {}
    missing_terms = []

    # 2. Match search terms against D1 database
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
        return Response.new(json.stringify({"results": [], "error": f"Missing terms from dictionary: {missing_terms}"}), headers=headers)

    # 3. Find candidate documents containing all query terms
    doc_sets = [set(docid for docid, _ in postings) for postings in term_postings.values()]
    candidate_docs = set.intersection(*doc_sets) if doc_sets else set()

    if not candidate_docs:
        return Response.new(json.stringify({"results": []}), headers=headers)

    # 4. Compute document vector lengths
    len_rows = await env.DB.prepare("SELECT docid, SUM(tfidf*tfidf) as ssum FROM Posting GROUP BY docid").all()
    doc_lengths = {l.docid: math.sqrt(l.ssum if l.ssum is not None else 0.0) for l in len_rows.results}

    term_doc_tfidf = {term: {docid: float(tfidf) for docid, tfidf in postings} for term, postings in term_postings.items()}

    # 5. Compute query term weights using your exact base-10 log calculations
    q_counts = Counter(query_tokens)
    q_weights = {}
    for term, cnt in q_counts.items():
        termid, df = term_infos[term]
        idf = math.log((N / df), 10) if df > 0 else 0.0
        q_weights[term] = cnt * idf

    q_len = math.sqrt(sum((w*w) for w in q_weights.values())) or 1.0

    # 6. Score candidate matches with Cosine Similarity & Simpson Overlap
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

    # Sort results by Cosine Similarity descending
    results.sort(key=lambda x: x["cosine"], reverse=True)
    return Response.new(json.stringify({"results": results[:20]}), headers=headers)

async def on_fetch(request, env, ctx):
    return await search_handler(request, env)
