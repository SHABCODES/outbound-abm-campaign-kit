# Campaign playbook

The process this kit supports, in the order it runs for a client.

## 1. Offer and ICP (day 1)
Write the offer as one sentence a buyer can say yes to. For this kit, the low-risk ask is a free test on the prospect's own data. Then fill the ICP block in the offer YAML: industries, size band, countries, buyer titles, and the signals that suggest the problem is live right now. Signals matter more than firmographics. A 200-person SaaS hiring support agents is a better target than a 200-person SaaS that is not.

## 2. List building (day 1 to 2)
Pull from at least two databases so you can cross-check titles and fill gaps (Apollo, Clay's providers, LinkedIn Sales Navigator, job boards for hiring signals, a tech lookup for stack). Save each export as `apollo_*.csv`, `clay_*.csv` or `manual_*.csv`. The ingest step merges them by domain and dedupes contacts.

Target 40 to 60 accounts per offer for ABM. If the scored list has far more tier A accounts than that, tighten the ICP rather than sending to everyone.

## 3. Enrichment and verification
Waterfall order: email already provided, exported lookup (Clay, Hunter), then pattern guess. Anything guessed goes through a paid verifier before it is trusted. Remove role addresses (info@, sales@) and anything flagged invalid.

## 4. Copy
One angle per signal. Rules enforced by the linter:
- First email 40 to 110 words, no links, subject under 45 characters, lowercase.
- Follow ups under 70 words.
- No spam trigger words, no em dashes, no unresolved variables.
Read the first 10 rendered emails out loud before launch. If one sounds like a template, fix the signal line.

## 5. Infrastructure (start 3 weeks before launch)
- Separate sending domains, never the main one. 2 to 3 mailboxes per domain.
- SPF, DKIM, DMARC set up and checked with `abm.cli domain`.
- Warmup ramp from `abm.cli plan`: 5 sends a day rising to about 30 per mailbox over 21 days.
- Cap at about 30 cold sends per mailbox per day after warmup.
- Unsubscribe line and a real business address in every email.

## 6. Launch
Import `campaign_import.csv` into the sender. Check 5 rendered emails inside the tool before activating. Send Tuesday to Thursday, local morning. Stop the sequence on any reply. For the top 10 accounts, add a manual LinkedIn view or connection request on the day of touch 1 (HeyReach if available).

## 7. Optimise
Weekly, run `abm.cli report`. Rules:
- Bounce rate above 3%: pause, re-verify, check domain health before touching copy.
- Do not compare angles until each has 100+ delivered emails.
- Change one thing at a time: subject, first line, or offer.
- Read every reply. Negative replies often say which assumption in the ICP is wrong.

## 8. Reporting
The report is one table and a short list of next steps. Clients want to know what sent, what came back, and what changes this week.
