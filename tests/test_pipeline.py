import csv
from pathlib import Path

import yaml

from abm import copy as cp
from abm import deliverability as dl
from abm import enrich, ingest, report, score, verify

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


def offer(name):
    return yaml.safe_load(open(ROOT / "offers" / f"{name}.yaml", encoding="utf-8"))


# ingest
def test_domain_normalised():
    assert ingest.norm_domain("https://www.Example.com/path") == "example.com"


def test_employee_ranges():
    assert ingest.parse_employees("51-200") == 125
    assert ingest.parse_employees("1,200") == 1200
    assert ingest.parse_employees("") is None


def test_merge_across_sources_dedupes_and_fills():
    rows = ingest.load_many([RAW / "apollo_sample_saas.csv", RAW / "clay_sample_saas.csv"])
    dana = [r for r in rows if r["contact_name"] == "Dana Reyes"]
    assert len(dana) == 1
    assert dana[0]["sources"] == "apollo;clay"
    assert dana[0]["linkedin_url"].startswith("https://linkedin.example")
    assert "customer support agent opening" in dana[0]["signals"]


# enrich
def test_waterfall_uses_lookup_before_guess():
    rows = [{"contact_name": "Priya Nair", "domain": "lumen-example.test", "email": ""}]
    prov = [enrich.LookupProvider(ROOT / "data" / "lookup_sample.csv"), enrich.PatternProvider()]
    out = enrich.enrich_emails(rows, prov)[0]
    assert out["email_source"] == "lookup"


def test_waterfall_falls_back_to_guess():
    rows = [{"contact_name": "Jo Bloggs", "domain": "x.test", "email": ""}]
    out = enrich.enrich_emails(rows, [enrich.PatternProvider()])[0]
    assert out["email"] == "jo.bloggs@x.test" and out["email_source"] == "pattern_guess"


def test_signal_word_boundaries():
    rules = {"helpdesk_tool": ["front"]}
    r = enrich.tag_signals([{"tech_stack": "Frontend;React", "signals": ""}], rules)[0]
    assert r["signal_tags"] == ""


# verify
def test_verify_statuses():
    assert verify.check_email("a@b.com")[0] == "valid"
    assert verify.check_email("info@b.com")[0] == "risky"
    assert verify.check_email("a@mailinator.com")[0] == "invalid"
    assert verify.check_email("not-an-email")[0] == "invalid"
    assert verify.check_email("a.b@c.com", "pattern_guess")[0] == "risky"


# score
def build(offer_name, files, **kw):
    o = offer(offer_name)
    rows = ingest.load_many([RAW / f for f in files])
    rows = enrich.enrich_emails(rows, [enrich.PatternProvider()])
    rows = enrich.tag_signals(rows, o["signal_rules"])
    rows = verify.verify_rows(rows)
    return o, rows, score.build_abm_list(rows, o["icp"], **kw)


def test_abm_list_excludes_off_icp_and_unverified():
    o, rows, abm = build("support_triage", ["apollo_sample_saas.csv"])
    domains = {r["domain"] for r in abm}
    assert "oakline-example.test" not in domains          # retail, off ICP
    assert "pixelforge-example.test" not in domains       # info@ role address
    assert "lumen-example.test" not in domains            # only a guessed email
    assert "northwind-example.test" in domains


def test_one_contact_per_account_by_default():
    o, rows, abm = build("support_triage", ["apollo_sample_saas.csv", "clay_sample_saas.csv"])
    doms = [r["domain"] for r in abm]
    assert len(doms) == len(set(doms))


def test_manufacturing_offer_scores_plants_highly():
    o, rows, abm = build("predictive_maintenance", ["apollo_sample_mfg.csv"])
    domains = {r["domain"] for r in abm}
    assert {"steelbrook-example.test", "greenfield-example.test"} <= domains
    assert "cedar-example.test" not in domains            # bank


# copy
def test_angle_follows_signal():
    o = offer("support_triage")
    assert cp.pick_angle(o, "hiring_support;helpdesk_tool") == "hiring_first"
    assert cp.pick_angle(o, "") == "tool_pain"


def test_all_offers_render_clean_for_every_angle():
    for name in ("support_triage", "predictive_maintenance"):
        o = offer(name)
        for angle in o["angles"].values():
            tag = angle["trigger_signal"]
            row = {"company": "Acme Inc", "first_name": "Sam", "signal_tags": tag, f"{tag}_name": "Thing"}
            for t in o["signal_rules"]:
                row.setdefault(f"{t}_name", "Thing")
            res = cp.render_contact(o, row, "Shabda")
            assert res["lint"] == [], (name, res["lint"])
            assert len(res["touches"]) == 4
            assert "Acme Inc" not in res["touches"][0]["body"]


def test_missing_variable_fails_loudly():
    try:
        cp.fill("Hi {{first_name}}", {})
        assert False
    except KeyError:
        pass


def test_lint_catches_problems():
    body = "word " * 30 + "click here http://x.test \u2014 {{oops}}"
    issues = cp.lint_touch("x" * 60, body, 0)
    joined = " ".join(issues)
    assert "link" in joined and "spam" in joined and "em dash" in joined and "unresolved" in joined and "subject" in joined


# deliverability
def test_spf_checks():
    assert dl.parse_spf([]) == ["no SPF record"]
    assert dl.parse_spf(['"v=spf1 include:_spf.google.com ~all"']) == []
    assert any("+all" in i for i in dl.parse_spf(["v=spf1 +all"]))
    assert any("multiple" in i for i in dl.parse_spf(["v=spf1 -all", "v=spf1 ~all"]))


def test_dmarc_checks():
    assert dl.parse_dmarc([]) == ["no DMARC record"]
    ok = dl.parse_dmarc(["v=DMARC1; p=quarantine; rua=mailto:d@x.test"])
    assert ok == []
    assert any("p=none" in i for i in dl.parse_dmarc(["v=DMARC1; p=none; rua=mailto:d@x.test"]))


def test_warmup_ramps_and_caps():
    s = dl.warmup_schedule(21, 5, 30)
    assert s[0] == 5 and s[-1] == 30 and s == sorted(s)


def test_capacity_plan_math():
    p = dl.capacity_plan(150, touches=4, window_days=14, per_mailbox_cap=30)
    assert p["total_emails"] == 600 and p["emails_per_day"] == 43 and p["mailboxes"] == 2 and p["sending_domains"] == 1


# report
def test_wilson_bounds():
    lo, hi = report.wilson(10, 100)
    assert 0.05 < lo < 0.10 < hi < 0.18
    assert report.wilson(0, 0) == (0.0, 0.0)


def test_report_refuses_to_rank_small_samples(tmp_path):
    f = tmp_path / "r.csv"
    f.write_text("angle,sent,bounced,replies,positive,meetings,unsubscribed\na,40,0,6,3,1,0\nb,40,0,1,0,0,0\n")
    rows = report.summarise(report.load_results(f))
    notes = report.recommendations(rows)
    assert all(not r["enough_data"] for r in rows)
    assert not any("clearly ahead" in n for n in notes)


def test_report_flags_high_bounce(tmp_path):
    f = tmp_path / "r.csv"
    f.write_text("angle,sent,bounced,replies,positive,meetings,unsubscribed\na,200,12,5,2,1,0\n")
    notes = report.recommendations(report.summarise(report.load_results(f)))
    assert any("bounce" in n for n in notes)


def test_report_template_has_no_data_message():
    rows = report.summarise(report.load_results(ROOT / "data" / "results_template.csv"))
    assert isinstance(rows, list)
