"""Command line entry point.

  python -m abm.cli build --offer offers/support_triage.yaml --inputs data/raw/*.csv --out out/support
  python -m abm.cli domain --domain yourdomain.com
  python -m abm.cli plan --contacts 150
  python -m abm.cli report --offer offers/support_triage.yaml --results data/results.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

from . import copy as cp
from . import deliverability, enrich, ingest, report, score, sequence, verify


def load_offer(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def cmd_build(a):
    offer = load_offer(a.offer)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = ingest.load_many(a.inputs)
    providers = [enrich.LookupProvider(a.lookup)] if a.lookup else []
    providers.append(enrich.PatternProvider())
    rows = enrich.enrich_emails(rows, providers)
    rows = enrich.tag_signals(rows, offer["signal_rules"])
    rows = verify.verify_rows(rows, check_dns=a.check_dns)
    abm = score.build_abm_list(rows, offer["icp"], size=a.size, contacts_per_account=a.contacts_per_account,
                               allow_risky=a.allow_risky)

    rendered, problems = [], []
    for r in abm:
        res = cp.render_contact(offer, r, a.sender)
        rendered.append((r, res))
        problems += [f"{r['email']}: {x}" for x in res["lint"]]

    cols = ["company", "domain", "industry", "employees", "country", "contact_name", "title", "email",
            "email_source", "email_status", "email_note", "signal_tags", "score", "tier", "why_this_account", "sources"]
    write_csv(out / "all_contacts_scored.csv", sorted(rows, key=lambda r: -r.get("score", 0)), cols)
    write_csv(out / "abm_list.csv", abm, cols)
    sequence.export_campaign(out / "campaign_import.csv", out / "sequence.json", offer, rendered)
    (out / "copy_lint.txt").write_text("\n".join(problems) or "no lint issues\n", encoding="utf-8")

    tiers = {t: sum(1 for r in rows if r["tier"] == t) for t in "ABC"}
    print(f"contacts loaded: {len(rows)}  tiers: {tiers}")
    print(f"ABM list: {len(abm)} contacts across {len({r['domain'] for r in abm})} accounts")
    print(f"copy lint issues: {len(problems)}")
    print(f"written to {out}/")
    return 1 if problems else 0


def cmd_domain(a):
    print(json.dumps(deliverability.check_domain(a.domain), indent=2))


def cmd_plan(a):
    print(json.dumps(deliverability.capacity_plan(a.contacts), indent=2))
    print("warmup per mailbox (daily sends):", deliverability.warmup_schedule())


def cmd_report(a):
    offer = load_offer(a.offer)
    rows = report.summarise(report.load_results(a.results))
    md = report.render_markdown(offer["label"], rows, report.recommendations(rows))
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
    print(md)


def main(argv=None):
    p = argparse.ArgumentParser(prog="abm")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--offer", required=True)
    b.add_argument("--inputs", nargs="+", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--lookup", help="CSV of emails exported from Clay/Apollo/Hunter")
    b.add_argument("--sender", default="Shabda")
    b.add_argument("--size", type=int, default=50)
    b.add_argument("--contacts-per-account", type=int, default=1)
    b.add_argument("--allow-risky", action="store_true")
    b.add_argument("--check-dns", action="store_true")
    b.set_defaults(fn=cmd_build)
    d = sub.add_parser("domain")
    d.add_argument("--domain", required=True)
    d.set_defaults(fn=cmd_domain)
    pl = sub.add_parser("plan")
    pl.add_argument("--contacts", type=int, required=True)
    pl.set_defaults(fn=cmd_plan)
    r = sub.add_parser("report")
    r.add_argument("--offer", required=True)
    r.add_argument("--results", required=True)
    r.add_argument("--out")
    r.set_defaults(fn=cmd_report)
    args = p.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
