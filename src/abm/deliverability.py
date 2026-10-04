"""Sending infrastructure: DNS checks (SPF, DKIM, DMARC), warmup ramp, mailbox math."""
import math
import re


def parse_spf(txt_records):
    spf = [t.strip('"') for t in txt_records if t.strip('"').lower().startswith("v=spf1")]
    issues = []
    if not spf:
        return ["no SPF record"]
    if len(spf) > 1:
        issues.append("multiple SPF records (invalid, merge them)")
    rec = spf[0].lower()
    if rec.endswith("+all") or " +all" in rec:
        issues.append("SPF ends in +all, anyone can send as you")
    elif not (rec.endswith("-all") or rec.endswith("~all")):
        issues.append("SPF has no -all or ~all ending")
    lookups = len(re.findall(r"\b(include:|a\b|mx\b|ptr\b|exists:|redirect=)", rec))
    if lookups > 10:
        issues.append(f"SPF needs about {lookups} DNS lookups, limit is 10")
    return issues


def parse_dmarc(txt_records):
    d = [t.strip('"') for t in txt_records if t.strip('"').lower().startswith("v=dmarc1")]
    if not d:
        return ["no DMARC record"]
    tags = dict(p.strip().split("=", 1) for p in d[0].split(";") if "=" in p)
    issues = []
    policy = tags.get("p", "").lower()
    if policy not in ("none", "quarantine", "reject"):
        issues.append("DMARC has no valid p= policy")
    elif policy == "none":
        issues.append("DMARC p=none: fine while warming up, move to quarantine once stable")
    if "rua" not in tags:
        issues.append("DMARC has no rua= address for reports")
    return issues


def _txt(name):
    import dns.resolver
    try:
        return [b"".join(r.strings).decode() for r in dns.resolver.resolve(name, "TXT", lifetime=5)]
    except Exception:
        return []


def check_domain(domain, dkim_selectors=("google", "selector1", "selector2", "default")):
    result = {"domain": domain, "spf": parse_spf(_txt(domain)), "dmarc": parse_dmarc(_txt(f"_dmarc.{domain}"))}
    found = [s for s in dkim_selectors if any("v=dkim1" in t.lower() for t in _txt(f"{s}._domainkey.{domain}"))]
    result["dkim_selectors_found"] = found
    result["dkim"] = [] if found else [f"no DKIM key under selectors {list(dkim_selectors)}"]
    result["ok"] = not any(i for k in ("spf", "dkim") for i in result[k]) and not any("no DMARC" in i for i in result["dmarc"])
    return result


def warmup_schedule(days=21, start=5, target=30):
    """Daily send volume per mailbox: slow ramp, hold, reach target on the last day."""
    step = (target - start) / max(days - 1, 1)
    return [min(target, round(start + step * d)) for d in range(days)]


def capacity_plan(contacts, touches=4, window_days=14, per_mailbox_cap=30, mailboxes_per_domain=3):
    total_emails = contacts * touches
    per_day = math.ceil(total_emails / window_days)
    mailboxes = math.ceil(per_day / per_mailbox_cap)
    return {"contacts": contacts, "total_emails": total_emails, "emails_per_day": per_day,
            "mailboxes": mailboxes, "sending_domains": math.ceil(mailboxes / mailboxes_per_domain),
            "warmup_days_before_launch": 21}
