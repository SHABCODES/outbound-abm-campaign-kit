"""Turn a results CSV into the client-style weekly report. Refuses to call winners on tiny samples."""
import csv
import math
from collections import defaultdict

MIN_SENT = 100


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def load_results(path):
    agg = defaultdict(lambda: defaultdict(int))
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            for f in ("sent", "bounced", "replies", "positive", "meetings", "unsubscribed"):
                agg[r["angle"]][f] += int(r.get(f) or 0)
    return agg


def summarise(agg):
    rows = []
    for angle, v in agg.items():
        delivered = max(v["sent"] - v["bounced"], 0)
        lo, hi = wilson(v["replies"], delivered)
        rows.append({"angle": angle, "sent": v["sent"], "bounce_rate": v["bounced"] / v["sent"] if v["sent"] else 0,
                     "reply_rate": v["replies"] / delivered if delivered else 0, "reply_ci": (lo, hi),
                     "positive": v["positive"], "meetings": v["meetings"], "enough_data": delivered >= MIN_SENT})
    return sorted(rows, key=lambda r: -r["reply_rate"])


def recommendations(rows):
    notes = []
    for r in rows:
        if r["sent"] and r["bounce_rate"] > 0.03:
            notes.append(f"{r['angle']}: bounce rate {r['bounce_rate']:.1%} is above 3%. Pause, re-verify the list, check domain health.")
    ready = [r for r in rows if r["enough_data"]]
    if len(ready) < len(rows):
        notes.append(f"Angles with under {MIN_SENT} delivered emails are not ranked. Keep sending before changing copy.")
    if len(ready) >= 2:
        a, b = ready[0], ready[1]
        if a["reply_ci"][0] > b["reply_ci"][1]:
            notes.append(f"{a['angle']} is clearly ahead of {b['angle']}. Shift volume to it.")
        else:
            notes.append(f"{a['angle']} leads {b['angle']} but the ranges overlap. Keep both running.")
    return notes or ["No data yet. Fill data/results_template.csv after the first week of sending."]


def render_markdown(offer_label, rows, notes):
    out = [f"# Weekly report: {offer_label}", "", "| Angle | Sent | Bounce | Reply rate | 95% range | Positive | Meetings |",
           "|---|---|---|---|---|---|---|"]
    for r in rows:
        flag = "" if r["enough_data"] else " (low sample)"
        out.append(f"| {r['angle']}{flag} | {r['sent']} | {r['bounce_rate']:.1%} | {r['reply_rate']:.1%} | "
                   f"{r['reply_ci'][0]:.1%} to {r['reply_ci'][1]:.1%} | {r['positive']} | {r['meetings']} |")
    out += ["", "## Next steps", ""] + [f"- {n}" for n in notes]
    return "\n".join(out) + "\n"
