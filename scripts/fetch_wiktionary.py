"""Fetch Wiktionary etymology entries and output RAG chunks for /ingest/custom.

Queries the English Wiktionary MediaWiki API for a curated word list spanning
French, Ancient Greek, Spanish, and English. Extracts etymology sections with
PIE root data, cognate lists, and definition context.

Usage:
    python scripts/fetch_wiktionary.py > wiktionary_chunks.json

Output: JSON array of {id, content, metadata} chunks for wiktionary collection.
"""

import json
import re
import sys
import time
import urllib.request
import urllib.parse

WIKIAPI = "https://en.wiktionary.org/w/api.php"
SLEEP = 0.3   # seconds between API calls (polite rate limiting)
SOURCE_FILE = "wiktionary"

# Curated word list: (word, language_section, language_display, notes)
# language_section must match the ==Section Name== in Wiktionary wikitext
WORD_LIST = [
    # ── ENGLISH ──────────────────────────────────────────────────────
    # Family
    ("father",   "English", "en", "family"),
    ("mother",   "English", "en", "family"),
    ("brother",  "English", "en", "family"),
    ("sister",   "English", "en", "family"),
    ("son",      "English", "en", "family"),
    ("daughter", "English", "en", "family"),
    ("husband",  "English", "en", "family"),
    ("wife",     "English", "en", "family"),
    ("widow",    "English", "en", "family"),
    ("nephew",   "English", "en", "family"),
    ("niece",    "English", "en", "family"),
    # Body
    ("eye",      "English", "en", "body"),
    ("ear",      "English", "en", "body"),
    ("nose",     "English", "en", "body"),
    ("tooth",    "English", "en", "body"),
    ("tongue",   "English", "en", "body"),
    ("knee",     "English", "en", "body"),
    ("heart",    "English", "en", "body"),
    ("head",     "English", "en", "body"),
    ("foot",     "English", "en", "body"),
    ("hand",     "English", "en", "body"),
    # Nature
    ("fire",     "English", "en", "nature"),
    ("water",    "English", "en", "nature"),
    ("earth",    "English", "en", "nature"),
    ("sun",      "English", "en", "nature"),
    ("moon",     "English", "en", "nature"),
    ("star",     "English", "en", "nature"),
    ("wind",     "English", "en", "nature"),
    ("snow",     "English", "en", "nature"),
    ("river",    "English", "en", "nature"),
    ("sea",      "English", "en", "nature"),
    ("tree",     "English", "en", "nature"),
    ("wood",     "English", "en", "nature"),
    ("night",    "English", "en", "nature"),
    ("day",      "English", "en", "nature"),
    # Animals
    ("cow",      "English", "en", "animal"),
    ("horse",    "English", "en", "animal"),
    ("pig",      "English", "en", "animal"),
    ("fish",     "English", "en", "animal"),
    ("mouse",    "English", "en", "animal"),
    ("bear",     "English", "en", "animal"),
    ("wolf",     "English", "en", "animal"),
    ("dog",      "English", "en", "animal"),
    ("bird",     "English", "en", "animal"),
    ("ox",       "English", "en", "animal"),
    ("sheep",    "English", "en", "animal"),
    ("bee",      "English", "en", "animal"),
    # Basic nouns / numerals
    ("name",     "English", "en", "noun"),
    ("three",    "English", "en", "numeral"),
    ("four",     "English", "en", "numeral"),
    ("five",     "English", "en", "numeral"),
    ("six",      "English", "en", "numeral"),
    ("seven",    "English", "en", "numeral"),
    ("eight",    "English", "en", "numeral"),
    ("nine",     "English", "en", "numeral"),
    ("ten",      "English", "en", "numeral"),
    ("hundred",  "English", "en", "numeral"),
    # Verbs
    ("stand",    "English", "en", "verb"),
    ("sit",      "English", "en", "verb"),
    ("know",     "English", "en", "verb"),
    ("hear",     "English", "en", "verb"),
    ("eat",      "English", "en", "verb"),
    ("drink",    "English", "en", "verb"),
    ("live",     "English", "en", "verb"),
    ("die",      "English", "en", "verb"),
    ("come",     "English", "en", "verb"),
    ("carry",    "English", "en", "verb"),
    # Common nouns with PIE roots
    ("god",      "English", "en", "noun"),
    ("man",      "English", "en", "noun"),
    ("woman",    "English", "en", "noun"),
    ("house",    "English", "en", "noun"),
    ("path",     "English", "en", "noun"),
    ("king",     "English", "en", "noun"),
    ("light",    "English", "en", "noun"),
    ("new",      "English", "en", "adjective"),
    ("full",     "English", "en", "adjective"),
    ("long",     "English", "en", "adjective"),
    ("deep",     "English", "en", "adjective"),

    # ── FRENCH ────────────────────────────────────────────────────────
    ("père",     "French",  "fr", "family"),
    ("mère",     "French",  "fr", "family"),
    ("frère",    "French",  "fr", "family"),
    ("sœur",     "French",  "fr", "family"),
    ("fils",     "French",  "fr", "family"),
    ("fille",    "French",  "fr", "family"),
    ("mari",     "French",  "fr", "family"),
    ("femme",    "French",  "fr", "family"),
    ("eau",      "French",  "fr", "nature"),
    ("feu",      "French",  "fr", "nature"),
    ("terre",    "French",  "fr", "nature"),
    ("soleil",   "French",  "fr", "nature"),
    ("lune",     "French",  "fr", "nature"),
    ("nuit",     "French",  "fr", "nature"),
    ("jour",     "French",  "fr", "nature"),
    ("nez",      "French",  "fr", "body"),
    ("œil",      "French",  "fr", "body"),
    ("dent",     "French",  "fr", "body"),
    ("pied",     "French",  "fr", "body"),
    ("main",     "French",  "fr", "body"),
    ("cœur",     "French",  "fr", "body"),
    ("nom",      "French",  "fr", "noun"),
    ("trois",    "French",  "fr", "numeral"),
    ("cent",     "French",  "fr", "numeral"),
    ("dieu",     "French",  "fr", "noun"),
    ("homme",    "French",  "fr", "noun"),
    ("maison",   "French",  "fr", "noun"),
    ("chien",    "French",  "fr", "animal"),
    ("loup",     "French",  "fr", "animal"),
    ("bœuf",     "French",  "fr", "animal"),
    ("cheval",   "French",  "fr", "animal"),
    ("nouveau",  "French",  "fr", "adjective"),
    ("long",     "French",  "fr", "adjective"),
    ("plein",    "French",  "fr", "adjective"),
    ("vieux",    "French",  "fr", "adjective"),
    ("venir",    "French",  "fr", "verb"),
    ("savoir",   "French",  "fr", "verb"),
    ("voir",     "French",  "fr", "verb"),
    ("porter",   "French",  "fr", "verb"),
    ("manger",   "French",  "fr", "verb"),

    # ── SPANISH ───────────────────────────────────────────────────────
    ("padre",    "Spanish", "es", "family"),
    ("madre",    "Spanish", "es", "family"),
    ("hermano",  "Spanish", "es", "family"),
    ("hermana",  "Spanish", "es", "family"),
    ("hijo",     "Spanish", "es", "family"),
    ("hija",     "Spanish", "es", "family"),
    ("marido",   "Spanish", "es", "family"),
    ("mujer",    "Spanish", "es", "family"),
    ("agua",     "Spanish", "es", "nature"),
    ("fuego",    "Spanish", "es", "nature"),
    ("tierra",   "Spanish", "es", "nature"),
    ("sol",      "Spanish", "es", "nature"),
    ("luna",     "Spanish", "es", "nature"),
    ("noche",    "Spanish", "es", "nature"),
    ("día",      "Spanish", "es", "nature"),
    ("nariz",    "Spanish", "es", "body"),
    ("ojo",      "Spanish", "es", "body"),
    ("diente",   "Spanish", "es", "body"),
    ("pie",      "Spanish", "es", "body"),
    ("mano",     "Spanish", "es", "body"),
    ("corazón",  "Spanish", "es", "body"),
    ("nombre",   "Spanish", "es", "noun"),
    ("tres",     "Spanish", "es", "numeral"),
    ("cien",     "Spanish", "es", "numeral"),
    ("dios",     "Spanish", "es", "noun"),
    ("hombre",   "Spanish", "es", "noun"),
    ("casa",     "Spanish", "es", "noun"),
    ("perro",    "Spanish", "es", "animal"),
    ("lobo",     "Spanish", "es", "animal"),
    ("buey",     "Spanish", "es", "animal"),
    ("caballo",  "Spanish", "es", "animal"),
    ("nuevo",    "Spanish", "es", "adjective"),
    ("largo",    "Spanish", "es", "adjective"),
    ("lleno",    "Spanish", "es", "adjective"),
    ("saber",    "Spanish", "es", "verb"),
    ("ver",      "Spanish", "es", "verb"),
    ("llevar",   "Spanish", "es", "verb"),
    ("comer",    "Spanish", "es", "verb"),
    ("venir",    "Spanish", "es", "verb"),

    # ── ANCIENT GREEK ─────────────────────────────────────────────────
    ("πατήρ",   "Ancient Greek", "grc", "family"),
    ("μήτηρ",   "Ancient Greek", "grc", "family"),
    ("ἀδελφός", "Ancient Greek", "grc", "family"),
    ("υἱός",    "Ancient Greek", "grc", "family"),
    ("θυγάτηρ", "Ancient Greek", "grc", "family"),
    ("λόγος",   "Ancient Greek", "grc", "noun"),
    ("θεός",    "Ancient Greek", "grc", "noun"),
    ("ἀνήρ",    "Ancient Greek", "grc", "noun"),
    ("γυνή",    "Ancient Greek", "grc", "noun"),
    ("βίος",    "Ancient Greek", "grc", "noun"),
    ("ὁδός",    "Ancient Greek", "grc", "noun"),
    ("οὐρανός", "Ancient Greek", "grc", "noun"),
    ("γῆ",      "Ancient Greek", "grc", "nature"),
    ("πῦρ",     "Ancient Greek", "grc", "nature"),
    ("ὕδωρ",    "Ancient Greek", "grc", "nature"),
    ("νύξ",     "Ancient Greek", "grc", "nature"),
    ("ἥλιος",   "Ancient Greek", "grc", "nature"),
    ("ὀφθαλμός","Ancient Greek", "grc", "body"),
    ("καρδία",  "Ancient Greek", "grc", "body"),
    ("ὄνομα",   "Ancient Greek", "grc", "noun"),
    ("τρεῖς",   "Ancient Greek", "grc", "numeral"),
    ("δέκα",    "Ancient Greek", "grc", "numeral"),
    ("ἑκατόν",  "Ancient Greek", "grc", "numeral"),
    ("ἵππος",   "Ancient Greek", "grc", "animal"),
    ("κύων",    "Ancient Greek", "grc", "animal"),
    ("ἄγω",     "Ancient Greek", "grc", "verb"),
    ("φέρω",    "Ancient Greek", "grc", "verb"),
    ("γιγνώσκω","Ancient Greek", "grc", "verb"),
    ("ὁράω",    "Ancient Greek", "grc", "verb"),
    ("ἀκούω",   "Ancient Greek", "grc", "verb"),
    ("νέος",    "Ancient Greek", "grc", "adjective"),
    ("μέγας",   "Ancient Greek", "grc", "adjective"),
]


def fetch_wikitext(word: str) -> str | None:
    """Fetch wikitext for a Wiktionary page."""
    params = urllib.parse.urlencode({
        "action": "parse",
        "page": word,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
    })
    url = f"{WIKIAPI}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PortfolioRAG/1.0 Etymology Ingest"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data.get("parse", {}).get("wikitext", "")
    except Exception as e:
        print(f"  ERROR fetching {word!r}: {e}", file=sys.stderr)
        return None


def extract_language_section(wikitext: str, lang_section: str) -> str:
    """Extract the ==Language== section from wikitext."""
    # Find ==Language== ... ==NextLanguage== boundary
    pattern = re.compile(
        r"^==" + re.escape(lang_section) + r"==\s*\n(.*?)(?:^==(?!=)|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(wikitext)
    if m:
        return m.group(1)
    return ""


def extract_pie_root(section: str) -> str:
    """Extract PIE root from {{root|...|ine-pro|*root}} or {{PIE root|...}} templates."""
    # Standard: {{root|lang|ine-pro|*root-}} or {{root|lang|ine-pro|*root|id=...}}
    m = re.search(r"\{\{root\|[^}]*?\|ine-pro\|(\*[^|}\s]+)", section)
    if m:
        return m.group(1)
    # Alternative: {{PIE root|lang|root}}
    m = re.search(r"\{\{PIE root\|[^|]+\|([^|}]+)", section)
    if m:
        return "*" + m.group(1)
    # Direct mention: "Proto-Indo-European *root"
    m = re.search(r"Proto-Indo-European\s+\*([a-zāēīōūₑ₂₃ʰʷ\-]+)", section)
    if m:
        return "*" + m.group(1)
    # ine-pro template
    m = re.search(r"\{\{(?:m|inh|der|cog)\|ine-pro\|(\*[^|}\s]+)", section)
    if m:
        return m.group(1)
    return ""


def extract_etymology_section(lang_section: str) -> str:
    """Extract ===Etymology=== subsection text."""
    # May be ===Etymology=== or ====Etymology====
    m = re.search(
        r"===+Etymology(?:\s+\d+)?===+\s*\n(.*?)(?:===|==|\Z)",
        lang_section,
        re.DOTALL,
    )
    if m:
        return m.group(1).strip()
    return ""


def clean_wikitext(text: str) -> str:
    """Remove wikitext markup, keep meaningful text."""
    # Remove {{template|...}} — keep the display text where present
    # First: handle link-style templates like {{m|grc|λόγος|t=word}} → keep lang+word
    text = re.sub(r"\{\{(?:m|l|cog|inh|der|bor)\|[a-z-]+\|([^|{}\n]+?)(?:\|[^{}]*?)?\}\}", r"\1", text)
    # Remove all remaining templates
    text = re.sub(r"\{\{[^{}]*?\}\}", "", text)
    # Remove wiki links [[target|display]] → display, or [[target]] → target
    text = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove ref tags
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def extract_definition(lang_section: str) -> str:
    """Extract first definition from ===Noun=== / ===Verb=== etc. sections."""
    # Find any POS section
    m = re.search(
        r"===+(?:Noun|Verb|Adjective|Adverb|Preposition|Pronoun|Determiner)===+\s*\n.*?\n(#[^\n]+)",
        lang_section,
        re.DOTALL,
    )
    if m:
        defn = m.group(1)
        defn = re.sub(r"#\s*", "", defn)
        return clean_wikitext(defn)[:200]
    return ""


def build_chunk(word: str, lang_section: str, lang_code: str, lang_display: str,
                category: str, wikitext: str) -> dict | None:
    """Build a RAG chunk from fetched wikitext."""
    section = extract_language_section(wikitext, lang_section)
    if not section:
        return None

    etym_text = extract_etymology_section(section)
    if not etym_text:
        return None  # skip entries with no etymology

    pie_root = extract_pie_root(section)
    definition = extract_definition(section)
    cleaned_etym = clean_wikitext(etym_text)

    if len(cleaned_etym) < 20:
        return None

    # Build content
    parts = [f"Wiktionary — {lang_display}: {word}"]
    if definition:
        parts.append(f"Definition: {definition}")
    parts.append(f"Etymology: {cleaned_etym}")
    if pie_root:
        parts.append(f"PIE root: {pie_root}")

    content = "\n".join(parts)
    if len(content) > 1800:
        content = content[:1797] + "..."

    slug = re.sub(r"[^a-z0-9]", "_", word.lower()).strip("_") or "word"
    chunk_id = f"wiktionary::{lang_code}::{slug}"

    return {
        "id": chunk_id,
        "content": content,
        "metadata": {
            "source": "wiktionary",
            "source_file": "wiktionary",
            "collection": "wiktionary",
            "word": word,
            "language": lang_display,
            "language_code": lang_code,
            "category": category,
            "pie_root": pie_root,
        },
    }


def main():
    chunks = []
    seen_ids: set[str] = set()
    errors = 0

    print(f"Fetching {len(WORD_LIST)} words from Wiktionary...", file=sys.stderr)

    for i, (word, lang_section, lang_code, category) in enumerate(WORD_LIST):
        print(f"  [{i+1}/{len(WORD_LIST)}] {word} ({lang_section})", file=sys.stderr)

        wikitext = fetch_wikitext(word)
        if wikitext is None:
            errors += 1
            time.sleep(SLEEP)
            continue

        chunk = build_chunk(word, lang_section, lang_code, lang_section, category, wikitext)
        if chunk is None:
            print(f"    → no etymology section, skipping", file=sys.stderr)
            time.sleep(SLEEP)
            continue

        if chunk["id"] in seen_ids:
            print(f"    → duplicate id {chunk['id']}, skipping", file=sys.stderr)
            time.sleep(SLEEP)
            continue

        seen_ids.add(chunk["id"])
        chunks.append(chunk)
        print(f"    → OK pie={chunk['metadata']['pie_root'] or 'none'}", file=sys.stderr)
        time.sleep(SLEEP)

    print(f"\nGenerated {len(chunks)} chunks ({errors} errors)", file=sys.stderr)
    if chunks:
        print(f"First: {chunks[0]['id']}", file=sys.stderr)
        print(f"Last:  {chunks[-1]['id']}", file=sys.stderr)

    json.dump(chunks, sys.stdout, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
