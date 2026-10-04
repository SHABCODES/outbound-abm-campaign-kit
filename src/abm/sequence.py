"""Export the rendered campaign in a flat CSV that cold email tools accept as custom variables."""
import csv
import json


def export_campaign(path_csv, path_json, offer, rendered_rows):
    fields = ["email", "first_name", "last_name", "company", "title", "domain", "angle", "score", "why_this_account"]
    n = len(offer["angles"][offer["default_angle"]]["touches"])
    for i in range(1, n + 1):
        fields += [f"subject_{i}", f"body_{i}"]
    with open(path_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for row, rendered in rendered_rows:
            rec = {k: row.get(k, "") for k in fields if not k.startswith(("subject_", "body_"))}
            rec["angle"] = rendered["angle"]
            for i, t in enumerate(rendered["touches"], 1):
                rec[f"subject_{i}"], rec[f"body_{i}"] = t["subject"], t["body"]
            w.writerow(rec)
    days = [t["day"] for t in offer["angles"][offer["default_angle"]]["touches"]]
    with open(path_json, "w", encoding="utf-8") as fh:
        json.dump({"offer": offer["name"], "send_on_days": days,
                   "rules": ["stop sequence on any reply", "send Tue to Thu, 8 to 11 am recipient time",
                             "no tracking links or images in touch 1", "include unsubscribe line and business address"]},
                  fh, indent=2)
