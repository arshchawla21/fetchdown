"""Markdown post-processing: strip boilerplate, citations, nav, and dupes."""
import re

# Wiki citation/edit markers
WIKI_NOISE_RE = re.compile(r'\[\d+\]|\[edit\]|\[\s*citation needed\s*\]', re.IGNORECASE)

# Orphan page-range refs left after stripping wiki citations: ": 111-148"
PAGE_REF_PREFIX_RE = re.compile(r'^:\s*\d+(?:[–\-]\d+)?\s*', re.MULTILINE)

# Bullets with leading whitespace from stripped citation prefixes
LIST_INDENT_RE = re.compile(r'^[ \t]+(?=- )', re.MULTILINE)

# Adjacent duplicate phrases (2-7 tokens, each 2+ chars). Catches doubled bylines:
# "Reviewed by Erika Rasure Reviewed by Erika Rasure" -> "Reviewed by Erika Rasure"
ADJACENT_DUP_RE = re.compile(r'\b((?:\S{2,}\s+){1,6}\S{2,})\s+\1\b')

# Investopedia-style TOC + author cards. Strip from "Table of Contents..." up to first prose lead.
TOC_DUMP_RE = re.compile(
    r'Table of Contents Expand Table of Contents.{30,2500}?'
    r'(?=\b(?:Definition|Key Takeaways|Important|Introduction|Overview|Abstract|Summary)\b)',
    re.DOTALL,
)

# Inline CTA / nav phrases
CTA_RE = re.compile(
    r'Get personalized, AI-powered answers[^.]*?ASK\s*'
    r'|Learn about our (?:editorial policies|Financial Review Board)\s*'
    r'|Subscribe to our newsletter[^.]*?\.\s*'
    r'|Sign up for[^.]*?newsletter[^.]*?\.\s*',
    re.IGNORECASE,
)

# Tail markers — truncate from the first match onward (refs, source lists, etc.)
TAIL_TRUNCATE_RE = re.compile(
    r'\n#{1,6}\s*(?:references?|external links?|see also|notes?|bibliography|further reading|sources|citations?|related articles?)\s*\n'
    r'|\bArticle Sources\b'
    r'|\nRead more\s+\w',
    re.IGNORECASE,
)

EXTRA_BLANKLINES_RE = re.compile(r'\n{3,}')


def clean_markdown(md: str) -> str:
    md = WIKI_NOISE_RE.sub('', md)
    md = PAGE_REF_PREFIX_RE.sub('', md)
    md = LIST_INDENT_RE.sub('', md)
    # Two passes: catches "A B A B C D C D" patterns
    md = ADJACENT_DUP_RE.sub(r'\1', md)
    md = ADJACENT_DUP_RE.sub(r'\1', md)
    md = TOC_DUMP_RE.sub('', md)
    md = CTA_RE.sub('', md)
    m = TAIL_TRUNCATE_RE.search(md)
    if m:
        md = md[:m.start()]
    md = EXTRA_BLANKLINES_RE.sub('\n\n', md)
    return md.strip()
