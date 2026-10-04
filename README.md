# outbound-abm-campaign-kit

A working toolkit for running account-based cold email campaigns for more than one offer. It covers the parts of the job that sit between "I have a market" and "the campaign is sending": list building from several databases, enrichment, ICP scoring, copy that changes by signal, sending infrastructure checks, and reporting that does not overstate small numbers.

It does not send email. Output files import into a sender (EmailBison, Instantly, Smartlead) and the enrichment step is shaped to take exports from Clay, Apollo and Hunter.

## What is real and what is not

- The code, copy, ICPs and tests are real. 22 tests pass.
- The company and contact rows in `data/raw/` are **synthetic** (`.test` domains). They exist so the pipeline runs end to end with no API keys.
- There are **no campaign results in this repo**. `data/results_template.csv` is empty on purpose. See `docs/CAMPAIGN_LOG.md` for where real numbers get recorded once a send happens.

## Two offers, two ICPs

| Offer | Buyer | Angles (chosen by signal) |
|---|---|---|
| `support_triage`: AI ticket triage for B2B SaaS | Head of Support, VP Customer Success | hiring_first, tool_pain, growth_scaling |
| `predictive_maintenance`: failure early warning pilot for manufacturers | Plant Manager, Maintenance Manager | data_unused, hiring_gap, downtime_cost |

Each offer is one YAML file in `offers/`: ICP weights, signal keywords, and a 4-touch sequence per angle. Add a third offer by copying a file.

## How it works

```
apollo_*.csv  clay_*.csv  manual_*.csv
        |
   ingest.py     normalise columns, merge by domain, dedupe contacts across sources
        |
   enrich.py     email waterfall (provided > exported lookup > pattern guess), signal tagging
        |
   verify.py     syntax, role addresses, disposable domains, optional MX check
        |
   score.py      ICP score 0-100, tier A/B/C, "why this account" note, one contact per account
        |
   copy.py       pick angle from signal, render 4 touches, lint (length, links, spam words, unresolved vars)
        |
   sequence.py   campaign_import.csv + sequence.json
```

Other modules: `deliverability.py` (SPF, DKIM, DMARC checks, warmup ramp, mailbox and domain math) and `report.py` (reply rates with Wilson intervals, refuses to rank angles under 100 delivered emails, flags bounce rate above 3%).

## Run it

```bash
pip install -r requirements.txt
export PYTHONPATH=src
pytest -q

# build a campaign from real exports (name files apollo_*.csv, clay_*.csv or manual_*.csv)
python -m abm.cli build --offer offers/support_triage.yaml \
  --inputs data/raw/apollo_mylist.csv data/raw/clay_mylist.csv \
  --lookup data/my_clay_emails.csv --sender "Your Name" --size 50 --out out/support

python -m abm.cli domain --domain yoursendingdomain.com      # SPF / DKIM / DMARC
python -m abm.cli plan --contacts 150                        # mailboxes, domains, warmup ramp
python -m abm.cli report --offer offers/support_triage.yaml --results data/results.csv --out out/report.md
```

`build` exits non-zero if any email fails the copy lint, so a bad variable never reaches a sender.

Sample output for both offers is in `examples/`.

## Design choices

- **One contact per account by default.** ABM on a tight list means depth on the account, not volume. Raise `--contacts-per-account` to multi-thread.
- **Guessed emails never go out unverified.** Pattern guesses are marked risky and excluded unless `--allow-risky` is passed.
- **Copy follows the signal.** Hiring, tooling and funding each get a different first line and different reasoning. Every angle has a `why` field explaining the logic.
- **No fabricated proof.** The copy offers a free test on the prospect's own data instead of citing customer results that do not exist.
- **Small samples are not ranked.** With 40 emails per angle, the report says so instead of declaring a winner.

## Known gaps

- No live Clay, EmailBison or HeyReach API calls. Outputs are import files; Clay-style enrichment is modelled as a provider waterfall.
- No LinkedIn automation. HeyReach touches are a manual step in the playbook.
- Reply classification is not included. See `ai-outreach-engine` for an IMAP reply classifier.
- MX checking needs network access to DNS and is off unless `--check-dns` is passed.
