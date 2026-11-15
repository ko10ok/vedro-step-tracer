import re


def in_order(*fragments: str) -> str:
    return "(?s)" + ".*".join(re.escape(fragment) for fragment in fragments)


def without(*fragments: str) -> str:
    alternatives = "|".join(re.escape(fragment) for fragment in fragments)
    return rf"(?s)^(?!.*(?:{alternatives})).*$"
