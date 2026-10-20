"""Typo-tolerant title lookup for plain-text messages sent to the bot.

A user types whatever they remember — "atack on titen", "aot", "jjk s2",
"demon slayr" — and we have to land on the right title. Postgres trigram
search alone misses acronyms and short forms, so the whole (small) catalogue is
scored in Python with several complementary strategies and the best one wins.

Scores are normalised to 0..1:
    1.00  exact match (after normalising)
    0.97  the query is an acronym of the title      ("aot"  -> Attack on Titan)
    0.95  title starts with the query               ("demon" -> Demon Slayer)
    0.90  query appears inside the title            ("titan" -> Attack on Titan)
    0.80+ every query word matches a title word     ("slayer demon")
    ....  character-level similarity for typos      ("atack on titen")
"""
import difflib
import logging
import re
import time

log = logging.getLogger("title_search")

_CACHE = {"at": 0.0, "rows": []}
CACHE_TTL = 60  # seconds

# Words people use when they're looking for adult content.
ADULT_WORDS = {
    "18", "18+", "adult", "adults", "adultnation", "porn", "porno", "pornhub",
    "xxx", "sex", "sexy", "nude", "nudes", "nsfw", "hentai", "ecchi", "erotic",
    "erotica", "bf", "bluefilm", "desi", "bhabhi", "mallu", "hot", "uncut",
    "unrated", "jav", "milf", "incest", "bold", "masala", "softcore", "hardcore",
    "onlyfans", "camgirl", "stripchat", "redlight", "randi", "chudai", "sexvideo",
}

_PUNCT = re.compile(r"[^a-z0-9\s]+")
_SPACE = re.compile(r"\s+")
# noise words that shouldn't drive a match
_STOP = {"the", "a", "an", "of", "and", "in", "season", "s", "part", "movie",
         "hindi", "dubbed", "dub", "sub", "episode", "ep", "full", "watch", "download"}


def normalise(text: str) -> str:
    t = (text or "").lower().strip()
    t = _PUNCT.sub(" ", t)
    return _SPACE.sub(" ", t).strip()


def tokens(text: str):
    return [w for w in normalise(text).split() if w]


def meaningful(text: str):
    ws = [w for w in tokens(text) if w not in _STOP]
    return ws or tokens(text)


def acronym(title: str) -> str:
    """'Attack on Titan' -> 'aot' (stop-words included, they're part of how
    people abbreviate)."""
    return "".join(w[0] for w in tokens(title) if w)


def acronym_strict(title: str) -> str:
    """'Attack on Titan' -> 'at' (skipping filler words)."""
    return "".join(w[0] for w in tokens(title) if w and w not in _STOP)


def looks_adult(query: str) -> bool:
    """True when the user is clearly asking for adult content."""
    qn = normalise(query)
    compact = qn.replace(" ", "")
    if compact in ADULT_WORDS:
        return True
    for w in tokens(query):
        if w in ADULT_WORDS:
            return True
    # "18+", "18 plus"
    if re.fullmatch(r"18\s*\+?(\s*plus)?", qn):
        return True
    return False


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _is_subseq(q: str, s: str) -> bool:
    it = iter(s)
    return all(ch in it for ch in q)


def shortform_score(q: str, title: str) -> float:
    """Score abbreviations people actually type: aot, jjk, csm, hxh, fmab.

    Matches the query against the title's word-initials first, then as a
    letter subsequence anchored on word starts, so "jjk" finds
    "Jujutsu Kaisen" (j-u-j-utsu k-aisen) without matching everything.
    """
    if not q or " " in q or not (2 <= len(q) <= 8):
        return 0.0
    words = tokens(title)
    if not words:
        return 0.0
    initials = "".join(w[0] for w in words)
    strict = "".join(w[0] for w in words if w not in _STOP) or initials
    if q in (initials, strict):
        return 0.97
    if len(q) >= 3 and (_is_subseq(q, initials) or _is_subseq(q, strict)):
        return 0.88

    compact = "".join(words)
    if not compact or compact[0] != q[0]:
        return 0.0
    # positions where a word begins — letters landing there are "real" initials
    starts, idx = set(), 0
    for w in words:
        starts.add(idx)
        idx += len(w)
    pos, on_start = 0, 0
    for ch in q:
        found = compact.find(ch, pos)
        if found == -1:
            return 0.0
        if found in starts:
            on_start += 1
        pos = found + 1
    if on_start < 2:            # needs to look like an abbreviation
        return 0.0
    span = max(pos, 1)
    density = len(q) / span                      # tightly packed = better
    start_ratio = on_start / len(q)
    return min(0.87, 0.60 + 0.22 * start_ratio + 0.18 * density)


def score(query: str, title: str, alt: str = "") -> float:
    """How well `query` matches `title` (0..1)."""
    q = normalise(query)
    if not q:
        return 0.0
    best = 0.0
    for cand in (title, alt):
        if not cand:
            continue
        t = normalise(cand)
        if not t:
            continue
        if q == t:
            return 1.0

        s = 0.0
        # --- acronym / short form ---
        s = max(s, shortform_score(q, cand))

        # --- prefix / substring ---
        if t.startswith(q):
            s = max(s, 0.95)
        elif q in t:
            # earlier and longer matches count for more
            frac = len(q) / len(t)
            s = max(s, 0.86 + 0.08 * frac)
        elif len(q) >= 4 and any(w.startswith(q) for w in t.split()):
            s = max(s, 0.88)

        # --- word-level matching (handles reordering + partial typing) ---
        qw, tw = meaningful(query), meaningful(cand)
        if qw and tw:
            hits = 0.0
            for w in qw:
                bw = max((_ratio(w, x) for x in tw), default=0.0)
                if bw >= 0.84 or any(x.startswith(w) and len(w) >= 3 for x in tw):
                    hits += 1
                elif bw >= 0.7:
                    hits += 0.6
            cover = hits / len(qw)
            if cover >= 0.999:
                s = max(s, 0.80 + 0.12 * min(1.0, len(qw) / max(1, len(tw))))
            else:
                s = max(s, 0.62 * cover)

        # --- whole-string fuzzy (pure typos) ---
        s = max(s, _ratio(q, t) * 0.92)
        # prefix-limited fuzzy: typing only the beginning of a long title
        if len(q) >= 4 and len(t) > len(q):
            s = max(s, _ratio(q, t[: len(q)]) * 0.9)

        best = max(best, s)
    return min(best, 1.0)


async def _load(titles_q):
    """All searchable titles, cached briefly (the catalogue is small)."""
    now = time.time()
    if now - _CACHE["at"] < CACHE_TTL and _CACHE["rows"]:
        return _CACHE["rows"]
    rows = await titles_q.search_index()
    _CACHE["rows"] = rows
    _CACHE["at"] = now
    return rows


def invalidate():
    _CACHE["at"] = 0.0


async def find(titles_q, query: str, show_nsfw: bool, limit: int = 5):
    """Return (results, adult_intent).

    results: list of (row, score) sorted best-first.
    adult_intent: the query was an adult search, so the caller should steer the
    user to the Adults Nation category when nothing good matched.
    """
    adult = looks_adult(query)
    rows = await _load(titles_q)

    pool = []
    for r in rows:
        if r["is_nsfw"] and not show_nsfw:
            continue
        pool.append(r)

    # An adult query should rank adult titles first; a normal query should not
    # surface adult titles unless they genuinely match.
    scored = []
    for r in pool:
        s = score(query, r["title"], r["title_alt"] or "")
        if adult and r["is_nsfw"]:
            s = min(1.0, s + 0.25)          # strong nudge toward the 18+ shelf
        elif adult and not r["is_nsfw"]:
            s *= 0.75
        if s > 0:
            scored.append((r, s))

    scored.sort(key=lambda x: (-x[1], len(x[0]["title"])))
    return scored[:limit], adult
