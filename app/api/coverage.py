"""Dictionary coverage audit endpoint.

GET /api/coverage — returns coverage matrix showing which dictionaries
cover words from each app (Super Flashcards, Etymython, EFG).

Data source: GCS JSON file (gs://portfolio-rag-backups-57478301787/coverage/latest.json)
uploaded by the audit script. Falls back to SQL if GCS unavailable.
"""

import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

GCS_BUCKET = "portfolio-rag-backups-57478301787"
GCS_COVERAGE_KEY = "coverage/latest.json"

# In-memory cache (refreshed on each cold start or explicit reload)
_coverage_cache: dict | None = None


def _load_from_gcs() -> dict | None:
    """Load coverage data from GCS."""
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(GCS_COVERAGE_KEY)
        if not blob.exists():
            logger.info("No coverage data in GCS yet")
            return None
        data = json.loads(blob.download_as_text())
        logger.info(f"Loaded coverage from GCS: {data.get('total_links', 0)} links")
        return data
    except Exception as e:
        logger.warning(f"GCS coverage load failed: {e}")
        return None


def _load_from_sql() -> dict | None:
    """Load coverage data from SQL Server (fallback)."""
    try:
        from app.core.database import get_db

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT app_source, COUNT(DISTINCT word) AS unique_words, COUNT(*) AS total_links
                FROM word_dictionary_links GROUP BY app_source ORDER BY app_source
            """)
            app_summary = [
                {"app": row[0], "unique_words": row[1], "total_links": row[2]}
                for row in cursor.fetchall()
            ]

            cursor.execute("""
                SELECT app_source, language, dictionary,
                       COUNT(DISTINCT word) AS matched_words, AVG(match_score) AS avg_score
                FROM word_dictionary_links
                GROUP BY app_source, language, dictionary
                ORDER BY app_source, language, dictionary
            """)
            matrix_rows = cursor.fetchall()

            cursor.execute("""
                SELECT app_source, language, COUNT(DISTINCT word) AS total_words
                FROM word_dictionary_links GROUP BY app_source, language
            """)
            totals = {(r[0], r[1]): r[2] for r in cursor.fetchall()}

            coverage = {}
            for row in matrix_rows:
                app, lang, dictionary, matched, avg_score = row
                coverage.setdefault(app, {})
                if lang not in coverage[app]:
                    coverage[app][lang] = {"total_words": totals.get((app, lang), 0), "dictionaries": {}}
                total = totals.get((app, lang), 1)
                pct = round(matched / total * 100, 1) if total > 0 else 0
                coverage[app][lang]["dictionaries"][dictionary] = {
                    "matched": matched, "total": total, "coverage_pct": pct,
                    "avg_score": round(avg_score, 3) if avg_score else None,
                }

            cursor.execute("SELECT COUNT(*) FROM word_dictionary_links")
            total_links = cursor.fetchone()[0]

            return {"total_links": total_links, "apps": app_summary, "coverage": coverage}
    except Exception as e:
        logger.warning(f"SQL coverage load failed: {e}")
        return None


def _get_coverage_data() -> dict:
    """Get coverage data from cache, GCS, or SQL."""
    global _coverage_cache
    if _coverage_cache is not None:
        return _coverage_cache

    # Try GCS first
    data = _load_from_gcs()
    if data:
        _coverage_cache = data
        return data

    # Fall back to SQL
    data = _load_from_sql()
    if data:
        _coverage_cache = data
        return data

    return {"total_links": 0, "apps": [], "coverage": {}}


@router.get("/api/coverage/reload")
async def reload_coverage():
    """Force reload coverage data from GCS."""
    global _coverage_cache
    _coverage_cache = None
    data = _get_coverage_data()
    return {"reloaded": True, "total_links": data.get("total_links", 0)}


@router.get("/api/coverage")
async def get_dictionary_coverage():
    """Coverage matrix: app x language x dictionary with match counts and %."""
    try:
        return _get_coverage_data()
    except Exception as e:
        logger.error(f"Coverage query failed: {e}")
        raise HTTPException(500, f"Coverage query failed: {e}")


# ── HTML coverage report ────────────────────────────────────────────

COVERAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dictionary Coverage Report</title>
<style>
  :root { --bg: #0b1220; --panel: #111a2d; --text: #e6edf8; --muted: #9aa8c7;
          --line: #26344f; --accent: #4a90d9; --ok: #23a55a; --warn: #e6a817; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh; }
  .app { max-width: 1000px; margin: 0 auto; padding: 24px 16px; }
  h1 { font-size: 1.5rem; margin-bottom: 4px; }
  .subtitle { color: var(--muted); font-size: 0.85rem; margin-bottom: 20px; }
  .nav { margin-bottom: 20px; }
  .nav a { color: var(--accent); text-decoration: none; font-size: 0.85rem; }
  .nav a:hover { text-decoration: underline; }
  .summary-cards { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }
  .summary-card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
                  padding: 16px 20px; flex: 1; min-width: 180px; }
  .summary-card h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase;
                     letter-spacing: 0.5px; margin-bottom: 6px; }
  .summary-card .val { font-size: 1.6rem; font-weight: 700; color: var(--accent); }
  .app-section { background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
                 padding: 20px; margin-bottom: 16px; }
  .app-section h2 { font-size: 1.1rem; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
  .app-badge { font-size: 0.72rem; padding: 2px 8px; border-radius: 4px;
               background: var(--accent); color: #fff; }
  .lang-group { margin-bottom: 16px; }
  .lang-group h3 { font-size: 0.9rem; color: var(--warn); margin-bottom: 8px;
                   border-bottom: 1px solid var(--line); padding-bottom: 4px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th { text-align: left; padding: 8px 10px; color: var(--muted); font-weight: 600;
       border-bottom: 1px solid var(--line); font-size: 0.78rem; text-transform: uppercase; }
  td { padding: 8px 10px; border-bottom: 1px solid rgba(38,52,79,0.5); }
  .pct-bar { display: inline-block; height: 6px; border-radius: 3px; margin-right: 8px;
             vertical-align: middle; }
  .pct-high { background: var(--ok); }
  .pct-mid { background: var(--warn); }
  .pct-low { background: #e74c3c; }
  .pct-zero { background: var(--line); }
  .loading { color: var(--muted); text-align: center; padding: 40px; font-size: 1rem; }
  .error { color: #e74c3c; text-align: center; padding: 40px; }
</style>
</head>
<body>
<div class="app">
  <div class="nav"><a href="/search">&larr; Back to Search</a></div>
  <h1>Dictionary Coverage Report</h1>
  <p class="subtitle">Word-to-dictionary traceability across portfolio apps</p>
  <div id="content"><p class="loading">Loading coverage data...</p></div>
</div>
<script>
const DICT_LABELS = {
  beekes: 'Beekes (Greek)',
  kroonen: 'Kroonen (Proto-Germanic)',
  de_vaan: 'de Vaan (Latin)',
  wiktionary: 'Wiktionary',
  dcc: 'DCC (Greek Core)',
  watkins: 'Watkins (IE Roots)',
};
const APP_LABELS = {
  'super-flashcards': 'Super Flashcards',
  'etymython': 'Etymython',
  'efg': 'Etymology Graph (EFG)',
};
const LANG_LABELS = {
  fr: 'French', el: 'Greek', en: 'English', es: 'Spanish',
  la: 'Latin', pie: 'PIE', de: 'German', pt: 'Portuguese',
  unknown: 'Unknown',
};

function pctClass(pct) {
  if (pct >= 60) return 'pct-high';
  if (pct >= 20) return 'pct-mid';
  if (pct > 0) return 'pct-low';
  return 'pct-zero';
}

async function loadCoverage() {
  const el = document.getElementById('content');
  try {
    const resp = await fetch('/api/coverage');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();

    let html = '';

    const totalWords = data.apps.reduce((s, a) => s + a.unique_words, 0);
    html += '<div class="summary-cards">';
    html += '<div class="summary-card"><h3>Total Links</h3><div class="val">' +
            data.total_links.toLocaleString() + '</div></div>';
    html += '<div class="summary-card"><h3>Unique Words</h3><div class="val">' +
            totalWords.toLocaleString() + '</div></div>';
    html += '<div class="summary-card"><h3>Apps Audited</h3><div class="val">' +
            data.apps.length + '</div></div>';
    html += '</div>';

    const coverage = data.coverage || {};
    for (const [app, langs] of Object.entries(coverage)) {
      const appLabel = APP_LABELS[app] || app;
      const appInfo = data.apps.find(a => a.app === app);
      const wordCount = appInfo ? appInfo.unique_words : '?';

      html += '<div class="app-section">';
      html += '<h2>' + esc(appLabel) + ' <span class="app-badge">' + wordCount + ' words</span></h2>';

      for (const [lang, info] of Object.entries(langs)) {
        const langLabel = LANG_LABELS[lang] || lang.toUpperCase();
        html += '<div class="lang-group">';
        html += '<h3>' + esc(langLabel) + ' (' + info.total_words + ' words)</h3>';
        html += '<table><tr><th>Dictionary</th><th>Matched</th><th>Coverage</th><th>Avg Score</th></tr>';

        for (const [dict, stats] of Object.entries(info.dictionaries)) {
          const dictLabel = DICT_LABELS[dict] || dict;
          const pct = stats.coverage_pct;
          const barWidth = Math.max(pct, 2);
          html += '<tr><td>' + esc(dictLabel) + '</td>';
          html += '<td>' + stats.matched + ' / ' + stats.total + '</td>';
          html += '<td><span class="pct-bar ' + pctClass(pct) + '" style="width:' + barWidth + 'px"></span> ' + pct + '%</td>';
          html += '<td>' + (stats.avg_score != null ? stats.avg_score : '\u2014') + '</td></tr>';
        }
        html += '</table></div>';
      }
      html += '</div>';
    }

    if (data.total_links === 0) {
      html += '<div class="app-section"><p style="color:var(--muted);text-align:center;padding:20px">' +
              'No coverage data yet. Run the audit script to populate.</p></div>';
    }

    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<p class="error">Failed to load coverage: ' + esc(e.message) + '</p>';
  }
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

loadCoverage();
</script>
</body>
</html>"""


@router.get("/api/coverage/report", response_class=HTMLResponse)
async def coverage_report_page():
    """Browser-based coverage report. No auth required."""
    return COVERAGE_HTML
