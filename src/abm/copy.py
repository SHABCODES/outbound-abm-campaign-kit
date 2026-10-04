"""Render the email sequence for each contact and lint the copy before it can be exported."""
import re

VAR = re.compile(r"\{\{(\w+)\}\}")
SPAM_WORDS = ["free money", "guarantee", "act now", "limited time", "click here", "100%", "risk-free", "winner", "$$$"]
EM_DASH = "\u2014"


def fill(text, ctx, strict=True):
    def sub(m):
        k = m.group(1)
        if k in ctx and ctx[k] not in (None, ""):
            return str(ctx[k])
        if strict:
            raise KeyError(k)
        return m.group(0)
    # Two passes so values that themselves contain {{vars}} (signal_line, pilot) resolve.
    return VAR.sub(sub, VAR.sub(sub, text))


def pick_angle(offer, tags):
    tags = set(filter(None, tags.split(";"))) if isinstance(tags, str) else set(tags)
    for name, a in offer["angles"].items():
        if a["trigger_signal"] in tags:
            return name
    return offer["default_angle"]


def lint_touch(subject, body, touch_index):
    issues = []
    words = len(body.split())
    if touch_index == 0:
        if not 40 <= words <= 110:
            issues.append(f"touch 1 is {words} words, aim for 40 to 110")
        if "http" in body.lower():
            issues.append("touch 1 contains a link")
        if len(subject) > 45:
            issues.append(f"subject is {len(subject)} chars, keep under 45")
    elif words > 70:
        issues.append(f"follow up is {words} words, keep under 70")
    low = (subject + " " + body).lower()
    for w in SPAM_WORDS:
        if w in low:
            issues.append(f"spam trigger: '{w}'")
    if EM_DASH in body or EM_DASH in subject:
        issues.append("contains an em dash")
    if "{{" in body or "{{" in subject:
        issues.append("unresolved variable")
    return issues


SUFFIX = re.compile(r"[,\s]+(inc\.?|llc|ltd\.?|corp\.?|gmbh|plc|co\.?)$", re.I)


def short_company(name):
    return SUFFIX.sub("", (name or "").strip())


def render_contact(offer, row, sender_name, subject_variant=0):
    angle_name = pick_angle(offer, row.get("signal_tags", ""))
    angle = offer["angles"][angle_name]
    ctx = dict(row)
    ctx["company"] = short_company(row["company"])
    ctx["sender_name"] = sender_name
    ctx["pilot"] = offer["pilot"]
    ctx["signal_line"] = fill(angle["signal_line"], ctx)
    subject = fill(angle["subjects"][subject_variant % len(angle["subjects"])], ctx).lower()
    touches, issues = [], []
    for i, t in enumerate(angle["touches"]):
        body = fill(t["body"], ctx).strip()
        touches.append({"day": t["day"], "subject": subject if i == 0 else "re: " + subject, "body": body})
        issues += [f"touch {i + 1}: {x}" for x in lint_touch(subject, body, i)]
    return {"angle": angle_name, "touches": touches, "lint": issues}
