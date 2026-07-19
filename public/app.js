const API_ROOT = window.location.origin;

async function executeCrawl() {
    const targetUrl = document.getElementById('crawlInput').value.trim();
    const status = document.getElementById('crawlStatus');
    if (!targetUrl) return;

    status.innerHTML = "⚡ Spider crawling target layers at the edge...";
    try {
        const response = await fetch(`${API_ROOT}/crawl?url=${encodeURIComponent(targetUrl)}`);
        const data = await response.json();
        if (data.error) {
            status.innerHTML = `❌ Pipeline Failure: ${data.error}`;
        } else {
            status.innerHTML = `✅ Complete! Parsed and built relational database matrices across <b>${data.pages_crawled}</b> vector pages.`;
        }
    } catch (err) {
        status.innerHTML = "❌ Failed to connect to worker execution threads.";
    }
}

async function executeSearch() {
    const query = document.getElementById('searchInput').value.trim();
    const status = document.getElementById('searchStatus');
    const view = document.getElementById('searchResults');
    if (!query) return;

    view.innerHTML = "";
    status.innerHTML = "⚡ Running Cosine Similarity and Overlap evaluations...";

    try {
        const response = await fetch(`${API_ROOT}/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        status.innerHTML = "Calculation finished.";

        if (data.error) {
            view.innerHTML = `<p style="color: #ef4444;">${data.error}</p>`;
            return;
        }

        if (!data.results || data.results.length === 0) {
            view.innerHTML = "<p style='color: var(--text-muted)'>No internal documents match your exact search criteria.</p>";
            return;
        }

        data.results.forEach((res, idx) => {
            const card = document.createElement('div');
            card.className = 'result-card';
            card.innerHTML = `
                <div class="result-title">
                    <span>Rank ${idx + 1}:</span> <a href="${res.name}" target="_blank">${res.name}</a>
                </div>
                <div class="meta-container">
                    <span class="metric-badge cosine">Cosine Sim: ${res.cosine.toFixed(4)}</span>
                    <span class="metric-badge">Simpson Overlap: ${res.simpson.toFixed(3)}</span>
                </div>
            `;
            view.appendChild(card);
        });
    } catch (err) {
        status.innerHTML = "❌ Target query calculation failed.";
    }
}
