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
          --line: #26344f; --accent: #4a90d9; --ok: #23a55a; --warn: #e6a817; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh; }
  .app { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
  h1 { font-size: 1.5rem; margin-bottom: 4px; }
  .subtitle { color: var(--muted); font-size: 0.85rem; margin-bottom: 20px; }

  /* Search box */
  .search-box { background: var(--panel); border: 1px solid var(--line);
                 border-radius: 10px; padding: 20px; margin-bottom: 20px; }
  .query-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: end; margin-bottom: 16px; }
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

  /* Source checkboxes */
  .filter-groups { display: flex; gap: 24px; flex-wrap: wrap; }
  .filter-group { flex: 1; min-width: 200px; }
  .filter-group h3 { font-size: 0.82rem; color: var(--accent); margin-bottom: 8px;
                      text-transform: uppercase; letter-spacing: 0.5px; }
  .checkbox-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
  .checkbox-row input[type=checkbox] { accent-color: var(--accent); width: 16px; height: 16px; cursor: pointer; }
  .checkbox-row label { margin-bottom: 0; font-size: 0.88rem; color: var(--text); cursor: pointer; }
  .checkbox-row label.disabled { color: var(--muted); opacity: 0.5; }
  .checkbox-row .source-desc { font-size: 0.75rem; color: var(--muted); margin-left: 4px; }

  .status { color: var(--muted); font-size: 0.85rem; margin-top: 12px; }
  .error { color: #e74c3c; }

  /* Results */
  .results { display: flex; flex-direction: column; gap: 8px; }
  .result-row { background: var(--panel); border: 1px solid var(--line);
                border-radius: 8px; overflow: hidden; }
  .result-header { display: flex; align-items: center; gap: 10px; padding: 12px 16px;
                   cursor: pointer; user-select: none; }
  .result-header:hover { background: rgba(74, 144, 217, 0.06); }
  .expand-toggle { font-size: 0.75rem; color: var(--muted); flex-shrink: 0; width: 16px; }
  .result-score { background: var(--ok); color: #fff; padding: 2px 8px; border-radius: 4px;
                  font-size: 0.78rem; font-weight: 600; flex-shrink: 0; }
  .result-source { font-size: 0.82rem; color: var(--muted); flex-shrink: 0; max-width: 180px;
                   overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .result-collection { font-size: 0.72rem; padding: 2px 6px; border-radius: 3px;
                       background: var(--line); color: var(--text); flex-shrink: 0; }
  .result-snippet { font-size: 0.85rem; color: var(--text); flex: 1; overflow: hidden;
                    text-overflow: ellipsis; white-space: nowrap; }

  /* Expanded detail */
  .result-detail { display: none; padding: 0 16px 16px 16px; border-top: 1px solid var(--line); }
  .result-detail.open { display: block; }
  .detail-full-text { font-size: 0.88rem; line-height: 1.6; white-space: pre-wrap;
                      word-break: break-word; color: var(--text); margin: 12px 0;
                      max-height: 400px; overflow-y: auto; padding: 12px;
                      background: var(--bg); border-radius: 6px; border: 1px solid var(--line); }
  .detail-meta { font-size: 0.78rem; color: var(--muted); display: flex; flex-wrap: wrap; gap: 12px;
                 margin-bottom: 10px; }
  .detail-meta span { background: var(--bg); padding: 2px 8px; border-radius: 4px; }
  .copy-btn { padding: 6px 14px; border-radius: 5px; border: 1px solid var(--line);
              background: var(--panel); color: var(--text); font-size: 0.82rem;
              cursor: pointer; }
  .copy-btn:hover { border-color: var(--accent); }
</style>
</head>
<body>
<div class="app">
  <h1>Portfolio RAG Search</h1>
  <p class="subtitle">Semantic search across portfolio collections</p>

  <div class="search-box">
    <div class="query-row">
      <div style="flex:1;min-width:200px">
        <label for="q">Query</label>
        <input type="text" id="q" placeholder="Enter search query..." autofocus>
      </div>
      <div>
        <label for="n">Results</label>
        <select id="n">
          <option value="3">3</option>
          <option value="5" selected>5</option>
          <option value="10">10</option>
          <option value="20">20</option>
        </select>
      </div>
      <div>
        <label>&nbsp;</label>
        <button class="search-btn" id="searchBtn" onclick="doSearch()">Search</button>
      </div>
    </div>

    <div class="filter-groups">
      <div class="filter-group">
        <h3>Etymology</h3>
        <div class="checkbox-row">
          <input type="checkbox" id="src-beekes" checked>
          <label for="src-beekes">Beekes</label>
          <span class="source-desc">Greek Etymological Dictionary</span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="src-kroonen">
          <label for="src-kroonen">Kroonen</label>
          <span class="source-desc">Proto-Germanic Dictionary</span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="src-watkins">
          <label for="src-watkins">Watkins</label>
          <span class="source-desc">American Heritage Dict. of IE Roots (1985)</span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="src-devaan" disabled>
          <label for="src-devaan" class="disabled">de Vaan</label>
          <span class="source-desc" style="opacity:0.5">Latin Dictionary (coming soon)</span>
        </div>
      </div>
      <div class="filter-group">
        <h3>Other Collections</h3>
        <div class="checkbox-row">
          <input type="checkbox" id="src-dcc" checked>
          <label for="src-dcc">DCC</label>
          <span class="source-desc">Greek Core List</span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="src-portfolio">
          <label for="src-portfolio">Portfolio</label>
          <span class="source-desc">Project knowledge</span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="src-code">
          <label for="src-code">Code</label>
          <span class="source-desc">Source files</span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="src-jazz">
          <label for="src-jazz">Jazz Theory</label>
          <span class="source-desc">Riff library seeds</span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="src-metapm">
          <label for="src-metapm">MetaPM</label>
          <span class="source-desc">Requirements &amp; sprints</span>
        </div>
      </div>
    </div>

    <div class="status" id="status"></div>
  </div>

  <div class="results" id="results"></div>
</div>

<script>
const qEl = document.getElementById('q');
const nEl = document.getElementById('n');
const statusEl = document.getElementById('status');
const resultsEl = document.getElementById('results');
const searchBtn = document.getElementById('searchBtn');

const BEEKES_FILE = '698401131-Beekes-Etymological-Dictionary-Greek-1.pdf';
const KROONEN_FILE = 'Etymological Dictionary of Proto-Germanic.pdf';
const WATKINS_FILE = 'Watkins - American Heritage Dictionary of Indo-European Roots (1985).epub';

qEl.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

async function fetchSemantic(q, collection, n, sources) {
  const params = new URLSearchParams({ q, collection, n: String(n) });
  if (sources) params.set('sources', sources);
  const resp = await fetch('/semantic?' + params);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || 'HTTP ' + resp.status);
  }
  const data = await resp.json();
  return data.results || [];
}

async function doSearch() {
  const q = qEl.value.trim();
  if (!q) { statusEl.textContent = 'Enter a query.'; return; }

  const n = parseInt(nEl.value);
  const beekesChecked = document.getElementById('src-beekes').checked;
  const kroonenChecked = document.getElementById('src-kroonen').checked;
  const watkinsChecked = document.getElementById('src-watkins').checked;
  const dccChecked = document.getElementById('src-dcc').checked;
  const portfolioChecked = document.getElementById('src-portfolio').checked;
  const codeChecked = document.getElementById('src-code').checked;
  const jazzChecked = document.getElementById('src-jazz').checked;
  const metapmChecked = document.getElementById('src-metapm').checked;

  const anyChecked = beekesChecked || kroonenChecked || watkinsChecked || dccChecked ||
                     portfolioChecked || codeChecked || jazzChecked || metapmChecked;
  if (!anyChecked) { statusEl.textContent = 'Select at least one source.'; return; }

  searchBtn.disabled = true;
  statusEl.textContent = 'Searching...';
  statusEl.classList.remove('error');
  resultsEl.innerHTML = '';

  try {
    const promises = [];

    // Etymology sources — same collection, filtered by source file
    if (beekesChecked || kroonenChecked || watkinsChecked) {
      const sources = [];
      if (beekesChecked) sources.push(BEEKES_FILE);
      if (kroonenChecked) sources.push(KROONEN_FILE);
      if (watkinsChecked) sources.push(WATKINS_FILE);
      promises.push(fetchSemantic(q, 'etymology', n, sources.join(',')));
    }

    // Other collections — no source filter needed
    if (dccChecked) promises.push(fetchSemantic(q, 'dcc', n, null));
    if (portfolioChecked) promises.push(fetchSemantic(q, 'portfolio', n, null));
    if (codeChecked) promises.push(fetchSemantic(q, 'code', n, null));
    if (jazzChecked) promises.push(fetchSemantic(q, 'jazz_theory', n, null));
    if (metapmChecked) promises.push(fetchSemantic(q, 'metapm', n, null));

    const arrays = await Promise.all(promises);
    const allResults = arrays.flat();

    // Sort merged results by score descending
    allResults.sort((a, b) => (b.score || 0) - (a.score || 0));
    const trimmed = allResults.slice(0, n);

    const checkedNames = [];
    if (beekesChecked) checkedNames.push('Beekes');
    if (kroonenChecked) checkedNames.push('Kroonen');
    if (watkinsChecked) checkedNames.push('Watkins');
    if (dccChecked) checkedNames.push('DCC');
    if (portfolioChecked) checkedNames.push('Portfolio');
    if (codeChecked) checkedNames.push('Code');
    if (jazzChecked) checkedNames.push('Jazz');
    if (metapmChecked) checkedNames.push('MetaPM');

    statusEl.textContent = trimmed.length + ' result' + (trimmed.length !== 1 ? 's' : '') +
      ' for "' + q + '" across ' + checkedNames.join(', ');

    if (trimmed.length === 0) {
      resultsEl.innerHTML = '<div class="result-row" style="padding:16px"><p style="color:var(--muted)">No results found.</p></div>';
      return;
    }

    trimmed.forEach((r, i) => {
      const row = document.createElement('div');
      row.className = 'result-row';

      const scoreVal = r.score != null ? r.score.toFixed(3) : 'n/a';
      const sourceShort = shortSource(r.source || '');
      const snippetPreview = (r.snippet || '').replace(/\\n/g, ' ').substring(0, 120);
      const fullText = r.full_text || r.snippet || '';

      const metaParts = [];
      if (r.source) metaParts.push('<span>Source: ' + esc(r.source) + '</span>');
      if (r.collection) metaParts.push('<span>Collection: ' + esc(r.collection) + '</span>');
      if (r.page != null) metaParts.push('<span>Page: ' + r.page + '</span>');
      if (r.section) metaParts.push('<span>Section: ' + esc(r.section) + '</span>');
      if (r.repo) metaParts.push('<span>Repo: ' + esc(r.repo) + '</span>');
      if (r.filepath) metaParts.push('<span>File: ' + esc(r.filepath) + '</span>');

      row.innerHTML =
        '<div class="result-header" onclick="toggleExpand(this)">' +
          '<span class="expand-toggle">&#9654;</span>' +
          '<span class="result-score">' + scoreVal + '</span>' +
          '<span class="result-collection">' + esc(r.collection || '') + '</span>' +
          '<span class="result-source">' + esc(sourceShort) + '</span>' +
          '<span class="result-snippet">' + esc(snippetPreview) + '</span>' +
        '</div>' +
        '<div class="result-detail">' +
          '<div class="detail-meta">' + metaParts.join('') + '</div>' +
          '<div class="detail-full-text">' + esc(fullText) + '</div>' +
          '<button onclick="copyToClipboard(this)" class="copy-btn">&#128203; Copy chunk</button>' +
        '</div>';

      resultsEl.appendChild(row);
    });
  } catch (e) {
    statusEl.textContent = 'Error: ' + e.message;
    statusEl.classList.add('error');
    resultsEl.innerHTML = '<div class="result-row" style="padding:16px"><p class="error">Could not reach the RAG service.</p></div>';
  } finally {
    searchBtn.disabled = false;
  }
}

function shortSource(s) {
  if (s.includes('Beekes')) return 'Beekes';
  if (s.includes('Proto-Germanic') || s.includes('Kroonen')) return 'Kroonen';
  if (s.includes('Watkins')) return 'Watkins';
  if (s.includes('dcc.')) return 'DCC';
  const parts = s.split('/');
  return parts[parts.length - 1] || s;
}

function toggleExpand(header) {
  const detail = header.nextElementSibling;
  const toggle = header.querySelector('.expand-toggle');
  const expanded = detail.classList.contains('open');
  detail.classList.toggle('open');
  toggle.innerHTML = expanded ? '&#9654;' : '&#9660;';
}

function copyToClipboard(btn) {
  const fullTextEl = btn.previousElementSibling;
  const text = fullTextEl.textContent;
  navigator.clipboard.writeText(text).then(() => {
    btn.innerHTML = '&#9989; Copied';
    setTimeout(() => { btn.innerHTML = '&#128203; Copy chunk'; }, 2000);
  });
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
