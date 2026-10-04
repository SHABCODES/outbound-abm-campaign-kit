"""Score accounts against an offer's ICP and pick the contacts for a tight ABM list.

Points: industry 30, size 20, country 5, title up to 25, signals up to 25 (capped at 100).
Tier A >= 70, B >= 45, else C."""

TIER_A, TIER_B = 70, 45


def title_points(title, rules):
    t = (title or "").lower()
    return max((r["weight"] for r in rules if r["match"] in t), default=0)


def score_row(row, icp):
    pts, why = 0, []
    industry = (row["industry"] or "").lower()
    if any(i in industry for i in icp["industries"]):
        pts += 30
        why.append(f"industry fit ({row['industry']})")
    emp = row["employees"]
    if emp and icp["employees"]["min"] <= emp <= icp["employees"]["max"]:
        pts += 20
        why.append(f"~{emp} employees")
    if (row["country"] or "").lower() in icp["countries"]:
        pts += 5
    tp = title_points(row["title"], icp["titles"])
    if tp:
        pts += tp
        why.append(f"buyer title ({row['title']})")
    sig = 0
    for tag in filter(None, (row.get("signal_tags") or "").split(";")):
        w = icp["signals"].get(tag, 0)
        if w:
            sig += w
            why.append(f"signal: {tag}")
    pts += min(sig, 25)
    row["score"] = min(pts, 100)
    row["tier"] = "A" if row["score"] >= TIER_A else "B" if row["score"] >= TIER_B else "C"
    row["why_this_account"] = "; ".join(why)
    return row


def build_abm_list(rows, icp, size=50, contacts_per_account=1, allow_risky=False):
    ok = {"valid", "risky"} if allow_risky else {"valid"}
    for r in rows:
        score_row(r, icp)
    eligible = [r for r in rows if r["tier"] in ("A", "B") and r.get("email_status") in ok]
    eligible.sort(key=lambda r: (-r["score"], r["domain"]))
    per_account, picked = {}, []
    for r in eligible:
        if per_account.get(r["domain"], 0) >= contacts_per_account:
            continue
        per_account[r["domain"]] = per_account.get(r["domain"], 0) + 1
        picked.append(r)
    accounts = []
    seen = set()
    out = []
    for r in picked:
        if r["domain"] not in seen:
            if len(seen) >= size:
                continue
            seen.add(r["domain"])
        out.append(r)
    return out
