"""Cheap pre-send checks. Not a replacement for a real verifier (ZeroBounce, NeverBounce),
but it catches obvious problems and flags guessed addresses for verification."""
import re

EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")
ROLE_LOCALS = {"info", "sales", "support", "admin", "contact", "hello", "office", "team", "noreply", "no-reply"}
DISPOSABLE = {"mailinator.com", "10minutemail.com", "guerrillamail.com", "tempmail.com", "yopmail.com"}


def has_mx(domain):
    try:
        import dns.resolver
        dns.resolver.resolve(domain, "MX", lifetime=4)
        return True
    except ImportError:
        return None
    except Exception:
        return False


def check_email(email, email_source="", check_dns=False):
    e = (email or "").strip().lower()
    if not e or not EMAIL_RE.match(e):
        return "invalid", "bad syntax or empty"
    local, domain = e.split("@", 1)
    if domain in DISPOSABLE:
        return "invalid", "disposable domain"
    if local in ROLE_LOCALS:
        return "risky", "role address"
    if check_dns:
        mx = has_mx(domain)
        if mx is False:
            return "invalid", "no MX record"
    if email_source == "pattern_guess":
        return "risky", "guessed pattern, verify with a paid checker before sending"
    return "valid", ""


def verify_rows(rows, check_dns=False):
    for r in rows:
        r["email_status"], r["email_note"] = check_email(r["email"], r.get("email_source", ""), check_dns)
    return rows
