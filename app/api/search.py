"""Browser-based search interface for Portfolio RAG.

Serves a self-contained HTML page at /search that calls the /semantic
endpoint via client-side fetch(). No auth required.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

SEARCH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Portfolio RAG Search</title>
<style>
  :root { --bg: #0b1220; --panel: #111a2d; --text: #e6edf8; --muted: #9aa8c7;
          --line: #26344f; --accent: #4a90d9; --ok: #23a55a; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh; }
  .app { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
  h1 { font-size: 1.5rem; margin-bottom: 4px; }
  .subtitle { color: var(--muted); font-size: 0.85rem; margin-bottom: 20px; }
  .search-box { background: var(--panel); border: 1px solid var(--line);
                 border-radius: 10px; padding: 20px; margin-bottom: 20px; }
  .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: end; }
  label { display: block; font-size: 0.8rem; color: var(--muted); margin-bottom: 4px; }
  input[type=text] { flex: 1; min-width: 200px; padding: 10px 12px; border-radius: 6px;
                     border: 1px solid var(--line); background: var(--bg);
                     color: var(--text); font-size: 0.95rem; }
  input[type=text]:focus { outline: none; border-color: var(--accent); }
  select { padding: 10px 12px; border-radius: 6px; border: 1px solid var(--line);
           background: var(--bg); color: var(--text); font-size: 0.95rem; }
  button.search-btn { padding: 10px 24px; border-radius: 6px; border: none;
                      background: var(--accent); color: #fff; font-size: 0.95rem;
                      font-weight: 600; cursor: pointer; }
  button.search-btn:hover { opacity: 0.9; }
  button.search-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .status { color: var(--muted); font-size: 0.85rem; margin-top: 12px; }
  .error { color: #e74c3c; }
  .results { display: flex; flex-direction: column; gap: 12px; }
  .result-card { background: var(--panel); border: 1px solid var(--line);
                 border-radius: 8px; padding: 16px; }
  .result-header { display: flex; justify-content: space-between; align-items: center;
                   margin-bottom: 8px; }
  .score { background: var(--ok); color: #fff; padding: 2px 8px; border-radius: 4px;
           font-size: 0.8rem; font-weight: 600; }
  .snippet { font-size: 0.9rem; line-height: 1.5; white-space: pre-wrap;
             word-break: break-word; color: var(--text); margin-bottom: 8px; }
  .meta { font-size: 0.78rem; color: var(--muted); }
  .meta span { margin-right: 12px; }
  .result-num { font-size: 0.8rem; color: var(--muted); font-weight: 600; }
</style>
</head>
<body>
<div class="app">
  <h1>Portfolio RAG Search</h1>
  <p class="subtitle">Semantic search across portfolio collections</p>

  <div class="search-box">
    <div class="row">
      <div style="flex:1;min-width:200px">
        <label for="q">Query</label>
        <input type="text" id="q" placeholder="Enter search query..." autofocus>
      </div>
      <div>
        <label for="col">Collection</label>
        <select id="col">
          <option value="dcc">DCC</option>
          <option value="etymology">Beekes</option>
          <option value="portfolio">Portfolio</option>
          <option value="metapm">MetaPM</option>
        </select>
      </div>
      <div>
        <label for="n">Results</label>
        <select id="n">
          <option value="3">3</option>
          <option value="5" selected>5</option>
          <option value="10">10</option>
        </select>
      </div>
      <div>
        <label>&nbsp;</label>
        <button class="search-btn" id="searchBtn" onclick="doSearch()">Search</button>
      </div>
    </div>
    <div class="status" id="status"></div>
  </div>

  <div class="results" id="results"></div>
</div>

<script>
const qEl = document.getElementById('q');
const colEl = document.getElementById('col');
const nEl = document.getElementById('n');
const statusEl = document.getElementById('status');
const resultsEl = document.getElementById('results');
const searchBtn = document.getElementById('searchBtn');

qEl.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

async function doSearch() {
  const q = qEl.value.trim();
  if (!q) { statusEl.textContent = 'Enter a query.'; return; }

  searchBtn.disabled = true;
  statusEl.textContent = 'Searching...';
  statusEl.classList.remove('error');
  resultsEl.innerHTML = '';

  const params = new URLSearchParams({
    q: q,
    collection: colEl.value,
    n: nEl.value
  });

  try {
    const resp = await fetch('/semantic?' + params);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || 'HTTP ' + resp.status);
    }
    const data = await resp.json();
    statusEl.textContent = data.total + ' result' + (data.total !== 1 ? 's' : '') +
      ' for "' + data.query + '" in ' + data.collection;

    if (data.results.length === 0) {
      resultsEl.innerHTML = '<div class="result-card"><p style="color:var(--muted)">No results found.</p></div>';
      return;
    }

    data.results.forEach((r, i) => {
      const card = document.createElement('div');
      card.className = 'result-card';

      const scoreVal = r.score != null ? r.score.toFixed(4) : 'n/a';
      const metaParts = [];
      if (r.collection) metaParts.push('<span>Collection: ' + esc(r.collection) + '</span>');
      if (r.source) metaParts.push('<span>Source: ' + esc(r.source) + '</span>');
      if (r.section) metaParts.push('<span>Section: ' + esc(r.section) + '</span>');
      if (r.page != null) metaParts.push('<span>Page: ' + r.page + '</span>');
      if (r.repo) metaParts.push('<span>Repo: ' + esc(r.repo) + '</span>');
      if (r.filepath) metaParts.push('<span>File: ' + esc(r.filepath) + '</span>');

      card.innerHTML =
        '<div class="result-header">' +
          '<span class="result-num">#' + (i + 1) + '</span>' +
          '<span class="score">' + scoreVal + '</span>' +
        '</div>' +
        '<div class="snippet">' + esc(r.snippet || '') + '</div>' +
        '<div class="meta">' + metaParts.join('') + '</div>';

      resultsEl.appendChild(card);
    });
  } catch (e) {
    statusEl.textContent = 'Error: ' + e.message;
    statusEl.classList.add('error');
    resultsEl.innerHTML = '<div class="result-card"><p class="error">Could not reach the RAG service. ' +
      'Check that the service is running and try again.</p></div>';
  } finally {
    searchBtn.disabled = false;
  }
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
</script>
</body>
</html>"""


@router.get("/search", response_class=HTMLResponse)
async def search_page():
    """Browser-based search interface. No auth required."""
    return SEARCH_HTML
