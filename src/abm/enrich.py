"""Email waterfall and signal tagging.

Providers are tried in order; the first answer wins and its name is stored in
`email_source`. Plug a real provider in by subclassing Provider."""
import csv
import re


class Provider:
    name = "base"

    def find(self, first, last, domain):
        raise NotImplementedError


class LookupProvider(Provider):
    """Emails you already exported from Clay, Apollo, Hunter etc."""
    name = "lookup"

    def __init__(self, path):
        self.table = {}
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                k = (r["first"].lower(), r["last"].lower(), r["domain"].lower())
                self.table[k] = r["email"].lower()

    def find(self, first, last, domain):
        return self.table.get((first.lower(), last.lower(), domain.lower()))


class PatternProvider(Provider):
    """Last resort: guess first.last@domain. Always re-verified before sending."""
    name = "pattern_guess"

    def find(self, first, last, domain):
        if first and last:
            return f"{re.sub('[^a-z]', '', first.lower())}.{re.sub('[^a-z]', '', last.lower())}@{domain}"
        return None


def split_name(full):
    parts = (full or "").replace(",", " ").split()
    if not parts:
        return "", ""
    return parts[0], parts[-1] if len(parts) > 1 else ""


def enrich_emails(rows, providers):
    for r in rows:
        first, last = split_name(r["contact_name"])
        r["first_name"], r["last_name"] = first, last
        if r["email"]:
            r["email_source"] = "provided"
            continue
        r["email_source"] = ""
        for p in providers:
            found = p.find(first, last, r["domain"])
            if found:
                r["email"], r["email_source"] = found, p.name
                break
    return rows


def tag_signals(rows, signal_rules):
    """Match each rule's keywords against tech_stack + signals text.
    Also stores the matched keyword, used in copy as e.g. {{helpdesk_tool_name}}."""
    for r in rows:
        haystack = f"{r['tech_stack']};{r['signals']}".lower()
        tags = []
        for tag, words in signal_rules.items():
            hit = next((w for w in words if re.search(r"\b" + re.escape(w) + r"\b", haystack)), None)
            if hit:
                tags.append(tag)
                r[f"{tag}_name"] = hit.title()
        r["signal_tags"] = ";".join(tags)
    return rows
