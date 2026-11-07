"""Name cleaning and holding-text parsing. No source-specific logic beyond vocabulary."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Legal and deal-vehicle words. Stripped only from the END of a name, so "Point C" stays "point c".
SUFFIXES = frozenset(
    """inc incorporated llc llp ltd limited corp corporation co company lp plc gmbh sa sarl sas bv nv ag ab as oy
    holdings holding group intermediate buyer parent topco midco bidco holdco opco finco acquisition acquisitions
    acquireco aquireco purchaser borrower merger sub usa us enterprises international global""".split()
)

# Words that end a borrower name when reading right from a hit.
_STOP_RIGHT = frozenset(
    """investment investments instrument asset type commitment first second lien senior sr secured term revolver
    revolving delayed draw ddtl loan loans debt due reference ref sofr libor common preferred class units unit shares
    equity warrant warrants stock industry acq acquisition mat maturity date current coupon non affiliated affiliate
    one unitranche subordinated mezzanine notes note bond bonds interest portfolio initial funded unfunded
    undrawn drawn participation incremental tranche fka dba""".split()
)

# Sector and boilerplate words that end a name when reading left from a hit.
_STOP_LEFT = frozenset(
    """investment investments debt lien secured senior loan loans first second portfolio company companies issuer non
    affiliated controlled affiliate inv ptfl lns bnk bank ncna flss flsd equity industry united states technology
    technologies software services service health care healthcare hardware equipment supplies providers consumer
    commercial professional diversified financial finance insurance capital markets banking real estate retail
    specialty products product media entertainment hotels hotel restaurants leisure gaming education energy utilities
    utility water multi chemicals chemical materials packaging containers paper metals mining machinery industrial
    industrials aerospace defense automotive auto components distributors distribution logistics transportation
    freight air building construction engineering pharmaceuticals biotechnology life sciences tools beverage beverages
    food tobacco personal household durable goods textiles apparel wireless telecommunication telecommunications
    communication communications high tech internet it systems application management development ground trading and
    of the in type name corporate unitranche stop usd eur gbp""".split()
)

_LEGAL_WORDS = frozenset(
    "inc incorporated llc llp ltd limited corp corporation lp plc gmbh sarl bv nv ag ab as co company".split()
)


def norm(text: object) -> str:
    """Lower-case, spell out '&', and turn punctuation into spaces. 'L.L.C.' collapses to one token first."""
    s = str(text).replace("&", " and ").lower()
    s = re.sub(r"\bl\.\s?l\.\s?c\b\.?", "llc", s)
    s = re.sub(r"\bl\.\s?p\b\.?", "lp", s)
    s = re.sub(r"\bs\.\s?a\.?\s?r\.?\s?l\b\.?", "sarl", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def core(name: object) -> str:
    """Name without trailing legal words. 'Apex Group' -> 'apex'; 'Point C' -> 'point c'; 'The Foo, Inc.' -> 'foo'."""
    toks = norm(name).split()
    if len(toks) > 1 and toks[0] == "the":
        toks = toks[1:]
    original = list(toks)
    while toks and toks[-1] in SUFFIXES:
        toks.pop()
    return " ".join(toks) or " ".join(original)


def name_pattern(core_name: str) -> re.Pattern[str]:
    """Whole-word match that tolerates punctuation and spacing inside the name ("Women's" vs "Womens")."""
    body = r"[\W_]*".join(re.escape(t) for t in core_name.split())
    return re.compile(r"(?<![A-Za-z0-9])" + body + r"(?![A-Za-z0-9])", re.I)


@dataclass(frozen=True)
class Mention:
    """One place a listed company's name appears in a holding's text."""

    text: str  # borrower name as read around the hit, e.g. "Apex Service Partners, LLC"
    key: str  # cleaned form used to group identical mentions, e.g. "apex service partners"
    left: tuple[str, ...]  # name words before the hit ("wheel" in "Wheel Pros")
    right: tuple[str, ...]  # non-legal name words after the hit ("service", "partners")
    trade_name: bool  # hit sits inside brackets: "(dba X)", "(X)", "(fka X)"
    has_legal_form: bool  # an Inc/LLC/Corp follows the hit


def _words(s: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.\-&/]*", s)


def _clean_word(w: str) -> str:
    return norm(w).replace(" ", "")


def find_mention(raw: str, pattern: re.Pattern[str]) -> Mention | None:
    """Read outward from a name hit to the likely edges of the borrower name."""
    m = pattern.search(raw)
    if not m:
        return None
    before, hit, after = raw[: m.start()], raw[m.start() : m.end()], raw[m.end() :]

    # Rightwards: stop at '|', '(', ';' or ' - '. A comma ends the name unless a legal form follows it.
    seg = re.split(r"\||\(|\)|;|\s[-–]\s", after, maxsplit=1)[0]
    parts = [p.strip() for p in seg.split(",")]
    name_part = parts[0]
    if (
        len(parts) > 1
        and parts[1]
        and _clean_word(_words(parts[1])[0] if _words(parts[1]) else "") in _LEGAL_WORDS
    ):
        name_part = f"{parts[0]} {_words(parts[1])[0]}"
    right_words: list[str] = []
    legal = False
    for w in _words(name_part):
        c = _clean_word(w)
        if c in _LEGAL_WORDS:
            legal = True
            right_words.append(w)
            break
        if c in _STOP_RIGHT or re.fullmatch(r"\d[\d/.\-%]*", w):
            break
        right_words.append(w)
        if len(right_words) >= 6:
            break

    # Leftwards: stop at a delimiter, a number, or a sector or boilerplate word.
    trade = bool(re.search(r"\([^()]*$", before))
    left_seg = re.split(r"\||\(|,|;|\s[-–]\s|%", before)[-1]
    left_words: list[str] = []
    for w in reversed(_words(left_seg)):
        c = _clean_word(w)
        if (
            c in _STOP_LEFT
            or c in {"dba", "fka", "nka", "formerly"}
            or re.fullmatch(r"\d[\d/.\-%]*", w)
        ):
            break
        left_words.insert(0, w)
        if len(left_words) >= 3:
            break

    right_clean = tuple(
        c for c in map(_clean_word, right_words) if c not in _LEGAL_WORDS
    )
    left_clean = tuple(map(_clean_word, left_words))
    return Mention(
        text=" ".join([*left_words, hit, *right_words]),
        key=norm(" ".join([*left_clean, hit, *right_clean])),
        left=left_clean,
        right=right_clean,
        trade_name=trade,
        has_legal_form=legal,
    )


_BORROWER_RX = re.compile(
    r"((?:[A-Z0-9][\w'’.&\-/]*[ ,]+){1,6}?"
    r"(?:Inc|Incorporated|LLC|L\.L\.C|LLP|Ltd|Limited|Corp|Corporation|LP|L\.P|PLC|plc|GmbH|S\.?A\.?R\.?L|B\.?V|AB|AG)\b\.?)"
)


def borrowers_in(raw: str) -> list[str]:
    """Legal-entity names in a holding text, leading sector words trimmed. Used for search beyond exact name hits."""
    out = []
    for seg in re.split(r"\||\(|;|\s[-–]\s", raw):
        for m in _BORROWER_RX.finditer(seg):
            words = _words(m.group(1))
            while words and (
                _clean_word(words[0]) in _STOP_LEFT
                or _clean_word(words[0]) in _STOP_RIGHT
                or words[0][0].isdigit()
            ):
                words = words[1:]
            if len(words) >= 2:
                out.append(" ".join(words))
    return out


# Loan descriptors used for like-for-like comparison.
_LIEN = [
    ("second lien", r"second[\s-]*lien|2nd\s*lien"),
    ("subordinated", r"subordinated|mezzanine"),
    (
        "first lien",
        r"first[\s-]*lien|1st\s*lien|\bflss?d?\b|one\s*stop|unitranche|senior\s*secured",
    ),
]
_DATE = re.compile(
    r"(?:due|maturity(?:\s*date)?|mat)\s*:?\s*(\d{1,2})/(?:\d{1,2}/)?(\d{2,4})", re.I
)
_NOT_FUNDED_DEBT = re.compile(
    r"undrawn|unfunded|commitment|revolv|delayed\s*draw|ddtl|\bequity\b|\bunits?\b|\bstock\b|warrant|preferred|\bshares\b|lp interest",
    re.I,
)


def lien_of(raw: str) -> str | None:
    for label, rx in _LIEN:
        if re.search(rx, raw, re.I):
            return label
    return None


def maturity_of(raw: str, maturity_col: object = None) -> str | None:
    """Maturity as YYYY-MM, from the tagged field or the text."""
    if isinstance(maturity_col, str) and re.match(r"\d{4}-\d{2}", maturity_col):
        return maturity_col[:7]
    m = _DATE.search(raw)
    if not m:
        return None
    month, year = int(m.group(1)), m.group(2)
    year = int(year) + 2000 if len(year) == 2 else int(year)
    return f"{year:04d}-{month:02d}" if 1 <= month <= 12 else None


def is_funded_debt(raw: str) -> bool:
    """False for equity-like rows and credit lines that may be undrawn."""
    return not _NOT_FUNDED_DEBT.search(raw)
