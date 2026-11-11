import re

_DIACRITICS = re.compile("[ً-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_ALEF_VARIANTS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_TOKEN = re.compile(r"\w+", re.UNICODE)
_AR_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")

_STOPWORDS = frozenset(
    "a an and are as at be by for from has in is it of on or that the to was what when "
    "which with will how do does can i my me you your this these those if any "
    "في من على الى عن او ان هو هي هذا هذه ما هل كيف متى اذا الذي التي مع هناك كل لا".split()
)


def normalize(text: str) -> str:
    """Lowercase and unify Arabic spelling variants: no diacritics or tatweel, one alef,
    yaa for alef maqsura, haa for taa marbuta, Latin digits."""
    text = _DIACRITICS.sub("", text).replace(_TATWEEL, "")
    text = text.translate(_ALEF_VARIANTS).translate(_ARABIC_DIGITS)
    text = text.replace("ى", "ي").replace("ة", "ه")
    return text.lower()


def _stem(token: str) -> str:
    if token.isascii():
        if len(token) > 4 and token.endswith("ies"):
            return token[:-3] + "y"
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            return token[:-1]
        return token
    for prefix in _AR_PREFIXES:
        if token.startswith(prefix) and len(token) - len(prefix) >= 3:
            return token[len(prefix) :]
    return token


def tokenize(text: str) -> list[str]:
    tokens = (_stem(t) for t in _TOKEN.findall(normalize(text)))
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1 or t.isdigit()]
