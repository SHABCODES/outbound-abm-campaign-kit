"""Load account/contact CSVs from several sources and merge them into one table."""
import csv
import re
from pathlib import Path

CANON = ["company", "domain", "industry", "employees", "country", "tech_stack",
         "signals", "contact_name", "title", "email", "linkedin_url", "sources"]

# Column names each source tool uses, mapped to the canonical names.
COLUMN_MAPS = {
    "apollo": {"Company": "company", "Website": "domain", "Industry": "industry",
               "# Employees": "employees", "Country": "country", "Technologies": "tech_stack",
               "Full Name": "contact_name", "Title": "title", "Email": "email",
               "Person Linkedin Url": "linkedin_url", "Keywords": "signals"},
    "clay": {"company_name": "company", "domain": "domain", "industry": "industry",
             "employee_count": "employees", "country": "country", "tech": "tech_stack",
             "full_name": "contact_name", "job_title": "title", "work_email": "email",
             "linkedin": "linkedin_url", "signals": "signals"},
    "manual": {k: k for k in CANON},
}


def norm_domain(value):
    v = (value or "").strip().lower()
    v = re.sub(r"^https?://", "", v)
    v = re.sub(r"^www\.", "", v)
    return v.split("/")[0]


def parse_employees(value):
    """'51-200' -> 125, '1,200' -> 1200, '' -> None."""
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", str(value or ""))]
    if not nums:
        return None
    return sum(nums[:2]) // len(nums[:2])


def source_name(path):
    stem = Path(path).stem.lower()
    for name in COLUMN_MAPS:
        if stem.startswith(name):
            return name
    return "manual"


def load_file(path):
    name = source_name(path)
    cmap = COLUMN_MAPS[name]
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            row = {c: "" for c in CANON}
            for src_col, canon in cmap.items():
                if src_col in raw and raw[src_col]:
                    row[canon] = raw[src_col].strip()
            row["domain"] = norm_domain(row["domain"])
            row["email"] = row["email"].lower()
            row["employees"] = parse_employees(row["employees"])
            row["sources"] = name
            if row["domain"]:
                rows.append(row)
    return rows


def _union(a, b):
    items = [x.strip() for x in (a + ";" + b).split(";") if x.strip()]
    return ";".join(dict.fromkeys(items))


def merge(rows):
    """Merge contact rows. Company fields are filled across rows sharing a domain;
    contacts are deduped by email, or by (domain, name) when there is no email."""
    company = {}
    for r in rows:
        c = company.setdefault(r["domain"], {"company": "", "industry": "", "employees": None,
                                             "country": "", "tech_stack": "", "signals": ""})
        for f in ("company", "industry", "country"):
            c[f] = c[f] or r[f]
        c["employees"] = c["employees"] or r["employees"]
        c["tech_stack"] = _union(c["tech_stack"], r["tech_stack"])
        c["signals"] = _union(c["signals"], r["signals"])

    contacts = {}
    for r in rows:
        key = r["email"] or (r["domain"], r["contact_name"].lower())
        if key in contacts:
            cur = contacts[key]
            for f in ("title", "linkedin_url", "email", "contact_name"):
                cur[f] = cur[f] or r[f]
            cur["sources"] = _union(cur["sources"], r["sources"])
        else:
            contacts[key] = dict(r)

    out = []
    for r in contacts.values():
        r.update(company[r["domain"]])
        out.append(r)
    return out


def load_many(paths):
    rows = []
    for p in paths:
        rows.extend(load_file(p))
    return merge(rows)
