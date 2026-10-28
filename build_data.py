"""Convert data.csv (Airtable export) and embed it into index.html.

Run:  python3 build_data.py
"""
import csv, json, re
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "data.csv"
OUT = HERE / "index.html"  # data is embedded between the DATA_START/DATA_END markers

# Columns whose cells may hold several values (Airtable multiple choice)
MULTI = {
    "תחום עיסוק",
    "קהל יעד עיקרי",
    "(אטרקציות) - סוג האטרקציה",
    "(אטרקציות) -  מתקנים נלווים",
    "(קולינריה) - סוג מטבח",
    "(קולינריה) - נגיש לצרכים קולינרים מיוחדים",
    "(לינה) - סוג אירוח",
    "חסמים ואתגרים עסקיים",
    "התעניינות בתמיכה ושירותים שיכולים להינתן",
}
# Single-choice columns: shown as filter facets
SINGLE = {
    "מיקום", "רשות", "אזור גיאוגרפי", "מגזר", "מגזר עירוני", "פתוח בשבת",
    "(קולינריה) - תפריט כשר", "נגישות לנכים", "האם שייך לרשת או עסק עצמאי",
    "Civix מי אני", "עונתיות", "האם קיימים שיתופי פעולה עסקיים",
    "האם העסק משתתף בפסטיבלים \\ אירועים אזוריים או מקומיים",
    "(מצב כלכלי ותפעולי) - מגמה עסקית כללית", "האם חבר באיגוד עסקי או תיירות",
    "(מצב כלכלי ותפעולי) - קיימת תמיכה ממשתית \\ מענקים",
    "האם בעל העסק שירת במילואים אחרי ה-7.10",
    "אם הייתה לך הזדמנות לשתף פעולה עם עסקים מהחברה בדואים\\יהודים האם היית רוצה להשתתף?",
}
BOOL = {"מקום בעל עניין מיוחד לפרויקט", "עוגנים תיירותיים", "נסגר"}
NUM = {
    "(לינה) - מספר יחידות\\חדרים", "(לינה) - מספר מיטות", "מספר עובדים",
    "שנת הקמה של העסק", "(קולינריה) - מספר מקומות ישיבה",
    "קישור לרשת חברתית (Instagram) מספר עוקבים",
    "קישור לרשת חברתית (Facebook) מספר עוקבים",
}
URL = {
    "קישור לדף אינטרנט", "קישור לרשת חברתית (Facebook)",
    "קישור לרשת חברתית (Instagram)", "קישור לאתר BOOKING (לינה)", "Google maps",
}
PHONE = {"טלפון בעל העסק", "טלפון העסק (ללקוחות)"}
EMAIL = {"מייל בעל העסק"}
LONG = {"הערות", "כתובת", "(לינה) - שירותים נוספים",
        "האם קיימים שיתופי פעולה עסקיים - פירוט",
        "האם חבר באיגוד עסקי או תיירות - פירוט",
        "פירוט - האם העסק משתתף בפסטיבלים \\ אירועים אזוריים או מקומיים ",
        "(מצב כלכלי ותפעולי) - פירוט - תמיכה ממשתית \\ מענקים"}
# Redundant Airtable helper columns – kept out of the app
DROP = {"ערים במאגר", "ערים במאגר 2", "Name (from ערים במאגר 2)",
        # not relevant for the project right now
        "עוגנים תיירותיים", "Civix מי אני",
        "מקום בעל עניין מיוחד לפרויקט", "עונתיות", "חסמים ואתגרים עסקיים",
        "האם העסק משתתף בפסטיבלים \\ אירועים אזוריים או מקומיים",
        "פירוט - האם העסק משתתף בפסטיבלים \\ אירועים אזוריים או מקומיים ",
        "האם קיימים שיתופי פעולה עסקיים", "האם קיימים שיתופי פעולה עסקיים - פירוט"}

GROUPS = [
    ("כללי", ["שם העסק", "תחום עיסוק", "מגזר", "מגזר עירוני", "אזור גיאוגרפי", "מיקום", "רשות",
              "כתובת", "מקום בעל עניין מיוחד לפרויקט", "עוגנים תיירותיים", "נסגר", "Civix מי אני", "הערות"]),
    ("קשר", ["שם בעל העסק", "טלפון בעל העסק", "טלפון העסק (ללקוחות)", "מייל בעל העסק",
             "קישור לדף אינטרנט", "קישור לרשת חברתית (Facebook)", "קישור לרשת חברתית (Facebook) מספר עוקבים",
             "קישור לרשת חברתית (Instagram)", "קישור לרשת חברתית (Instagram) מספר עוקבים",
             "קישור לאתר BOOKING (לינה)", "Google maps"]),
]


def split_multi(v):
    v = v.strip()
    if not v:
        return []
    return [t.strip() for t in next(csv.reader([v], skipinitialspace=True)) if t.strip()]


def to_num(v):
    v = v.strip().replace(",", "")
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except ValueError:
        return v or None


def ftype(c):
    if c in MULTI: return "multi"
    if c in SINGLE: return "single"
    if c in BOOL: return "bool"
    if c in NUM: return "num"
    if c in URL: return "url"
    if c in PHONE: return "phone"
    if c in EMAIL: return "email"
    if c in LONG: return "long"
    return "text"


def group_of(c):
    if c.startswith("(אטרקציות)"): return "אטרקציות"
    if c.startswith("(קולינריה)"): return "קולינריה"
    if c.startswith("(לינה)"): return "לינה"
    if c.startswith("(מצב כלכלי") or c in {"חסמים ואתגרים עסקיים", "התעניינות בתמיכה ושירותים שיכולים להינתן"}:
        return "מצב עסקי"
    for g, cols in GROUPS:
        if c in cols: return g
    return "פרטים נוספים"


def main():
    with SRC.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = [c for c in reader.fieldnames if c not in DROP]
        rows = list(reader)

    # Columns that are empty in every row are left out of the app
    empty = [c for c in cols if not any((r.get(c) or "").strip() not in ("", "-") for r in rows)]
    cols = [c for c in cols if c not in empty]
    if empty:
        print("Skipped empty columns:", *empty, sep="\n  ")

    fields = [{"key": c, "label": re.sub(r"^\((אטרקציות|קולינריה|לינה|מצב כלכלי ותפעולי)\) -\s+", "", c).strip(),
               "type": ftype(c), "group": group_of(c)} for c in cols]

    records = []
    for i, r in enumerate(rows, 1):
        rec = {"_id": f"b{i}"}
        for c in cols:
            raw = (r.get(c) or "").strip()
            t = ftype(c)
            if t == "multi":
                val = split_multi(raw)
            elif t == "bool":
                val = raw.lower() in ("checked", "true", "1", "כן")
            elif t == "num":
                val = to_num(raw)
            else:
                val = raw if raw not in ("", "-") else ""
                if c == "שם העסק":
                    val = re.sub(r"\s*\n\s*", " ", val)
            if val not in ("", None, [], False):
                rec[c] = val
        records.append(rec)

    js = (f"window.BASE_FIELDS = {json.dumps(fields, ensure_ascii=False)};\n"
          f"window.BASE_RECORDS = {json.dumps(records, ensure_ascii=False)};\n").replace("</", "<\\/")
    html = OUT.read_text(encoding="utf-8")
    html = re.sub(r"/\*DATA_START\*/.*?/\*DATA_END\*/", lambda m: "/*DATA_START*/\n" + js + "/*DATA_END*/", html, flags=re.S)
    OUT.write_text(html, encoding="utf-8")
    print(f"{len(records)} records, {len(fields)} fields -> embedded in {OUT.name}")


if __name__ == "__main__":
    main()
