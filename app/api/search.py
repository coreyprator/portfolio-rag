"""Browser-based search interface for Portfolio RAG.

Serves a self-contained HTML page at /search/etymology (etymology-only).
/search redirects (301) to /search/etymology.
GET /search/etymology?q=... with a query param returns JSON semantic results.
"""

from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.vectorstore import vector_store

router = APIRouter()

SEARCH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Etymology Search — Portfolio RAG v3</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%230891B2'/><text x='16' y='22' font-size='18' text-anchor='middle' fill='white'>🔍</text></svg>">
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
  .source-count { font-size: 0.7rem; color: var(--ok); margin-left: auto; white-space: nowrap; }

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
  <h1>Etymology Search</h1>
  <p class="subtitle">PIE root dictionaries &middot; Beekes / Kroonen / de Vaan / Watkins / DCC / Wiktionary &middot; <a href="/api/coverage/report" style="color:var(--accent);text-decoration:none">Coverage Report</a></p>

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
          <span class="source-count" id="count-beekes"></span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="src-kroonen">
          <label for="src-kroonen">Kroonen</label>
          <span class="source-desc">Proto-Germanic Dictionary</span>
          <span class="source-count" id="count-kroonen"></span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="src-watkins">
          <label for="src-watkins">Watkins</label>
          <span class="source-desc">American Heritage Dict. of IE Roots (1985)</span>
          <span class="source-count" id="count-watkins"></span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="src-devaan">
          <label for="src-devaan">de Vaan</label>
          <span class="source-desc">Etymological Dictionary of Latin (2008)</span>
          <span class="source-count" id="count-de-vaan"></span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="src-wiktionary">
          <label for="src-wiktionary">Wiktionary</label>
          <span class="source-desc">Live etymology &mdash; FR, EL, ES, EN</span>
          <span class="source-count" id="count-wiktionary"></span>
        </div>
      </div>
      <div class="filter-group">
        <h3>Other Collections</h3>
        <div class="checkbox-row">
          <input type="checkbox" id="src-dcc" checked>
          <label for="src-dcc">DCC</label>
          <span class="source-desc">Greek Core List</span>
          <span class="source-count" id="count-dcc"></span>
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
const DEVAAN_FILE = 'de Vaan - Etymological Dictionary of Latin (2008).pdf';

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
  const devaanChecked = document.getElementById('src-devaan').checked;
  const wiktionaryChecked = document.getElementById('src-wiktionary').checked;
  const dccChecked = document.getElementById('src-dcc').checked;

  const anyChecked = beekesChecked || kroonenChecked || watkinsChecked || devaanChecked ||
                     wiktionaryChecked || dccChecked;
  if (!anyChecked) { statusEl.textContent = 'Select at least one source.'; return; }

  searchBtn.disabled = true;
  statusEl.textContent = 'Searching...';
  statusEl.classList.remove('error');
  resultsEl.innerHTML = '';

  try {
    const promises = [];

    // Etymology sources — same collection, filtered by source file
    if (beekesChecked || kroonenChecked || watkinsChecked || devaanChecked) {
      const sources = [];
      if (beekesChecked) sources.push(BEEKES_FILE);
      if (kroonenChecked) sources.push(KROONEN_FILE);
      if (watkinsChecked) sources.push(WATKINS_FILE);
      if (devaanChecked) sources.push(DEVAAN_FILE);
      promises.push(fetchSemantic(q, 'etymology', n, sources.join(',')));
    }

    // Wiktionary — own collection
    if (wiktionaryChecked) promises.push(fetchSemantic(q, 'wiktionary', n, null));

    // Other collections — no source filter needed
    if (dccChecked) promises.push(fetchSemantic(q, 'dcc', n, null));

    const arrays = await Promise.all(promises);
    const allResults = arrays.flat();

    // Sort merged results by score descending
    allResults.sort((a, b) => (b.score || 0) - (a.score || 0));
    const trimmed = allResults.slice(0, n);

    const checkedNames = [];
    if (beekesChecked) checkedNames.push('Beekes');
    if (kroonenChecked) checkedNames.push('Kroonen');
    if (watkinsChecked) checkedNames.push('Watkins');
    if (devaanChecked) checkedNames.push('de Vaan');
    if (wiktionaryChecked) checkedNames.push('Wiktionary');
    if (dccChecked) checkedNames.push('DCC');

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
  if (s.includes('de Vaan') || s.includes('devaan') || s.includes('de-vaan')) return 'de Vaan';
  if (s === 'wiktionary' || s.includes('wiktionary')) return 'Wiktionary';
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

// Fetch per-source counts on page load
fetch('/stats').then(r => r.json()).then(stats => {
  // Etymology sources
  const etymSources = stats.etymology?.sources || {};
  Object.entries(etymSources).forEach(([src, count]) => {
    const el = document.getElementById('count-' + src);
    if (el) el.textContent = count.toLocaleString();
  });
  // Wiktionary (own collection)
  const wkCount = stats.wiktionary?.total;
  const wkEl = document.getElementById('count-wiktionary');
  if (wkEl && wkCount > 0) wkEl.textContent = wkCount.toLocaleString();
  // Other collections
  ['dcc'].forEach(c => {
    const el = document.getElementById('count-' + c);
    const val = stats[c]?.total;
    if (el && val > 0) el.textContent = val.toLocaleString();
  });
}).catch(() => {});
</script>
</body>
</html>"""


@router.get("/search", include_in_schema=False)
async def search_redirect():
    """Deprecated. Redirects to /search/etymology."""
    return RedirectResponse(url="/search/etymology", status_code=301)


@router.get("/search/etymology")
async def search_etymology(q: Optional[str] = None, collection: Optional[str] = None, n: int = 5):
    """Etymology semantic search.
    With ?q=: returns JSON results from etymology/dcc/wiktionary collections.
    Without ?q=: returns the browser search UI (HTML).
    """
    if q:
        # JSON semantic search over etymology collections
        ETYMOLOGY_VALID = {"etymology", "dcc", "wiktionary"}
        effective_collection = collection if collection in ETYMOLOGY_VALID else "etymology"
        n = min(max(n, 1), 20)
        results = vector_store.query(q, collection=effective_collection, max_results=n)
        formatted = []
        for r in results:
            meta = r.get("metadata", {})
            full_text = r.get("text", "")
            formatted.append({
                "score": r.get("score"),
                "snippet": full_text[:500],
                "full_text": full_text,
                "source": meta.get("source_file") or meta.get("path", ""),
                "page": meta.get("page_number"),
                "section": meta.get("section") or meta.get("entry_headword", ""),
                "collection": r.get("collection"),
            })
        return {"query": q, "collection": effective_collection, "total": len(formatted), "results": formatted}
    # No query — serve browser UI
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=SEARCH_HTML)
