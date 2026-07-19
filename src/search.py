import math
import re
from collections import Counter

TOKEN_RE = re.compile(r"\W+")

def tokenize(text):
    return [t.lower().strip() for t in TOKEN_RE.split(text) if t and len(t) > 0]

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
        return {"results": [], "error": f"Terms not found in index: {missing_terms}"}

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
