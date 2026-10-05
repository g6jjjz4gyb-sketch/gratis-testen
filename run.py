#!/usr/bin/env python3
"""Scrape every source, merge duplicates, classify, cache images.

    .venv/bin/python run.py            -> data/latest.json + web/img/
    .venv/bin/python run.py --cached   -> re-merge the last raw scrape only

The same campaign usually appears in three or four sources under slightly
different names ("BiFi TASTY BITES gratis testen" / "Bifi Tasty Bites"), so
offers are merged first by campaign URL, then by product name.
"""
import datetime as dt, hashlib, io, json, os, re, sys, time, unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sources
from sources import SOURCES, TODAY, get, og_image, parse_date

DATA = os.path.join(HERE, "data")
IMGDIR = os.path.join(HERE, "web", "img")

# Which source wins when they disagree. The four curated lists only carry
# campaigns that are running; DailyDeal is an archive whose dates are read
# out of prose, so it is trusted last and only on its own.
PRIORITY = ["sheet", "sparwelt", "dealdoktor", "geldschnurrbart", "dailydeal"]
CURATED = {"sheet", "sparwelt", "dealdoktor", "geldschnurrbart"}
NAME_PRIORITY = ["dealdoktor", "sheet", "geldschnurrbart", "sparwelt", "dailydeal"]
IMAGE_PRIORITY = ["sparwelt", "dealdoktor", "dailydeal"]

KINDS = {
    "gratis":      "100 % zurück",
    "teil":        "Teil-Cashback",
    "garantie":    "Geld-zurück-Garantie",
    "probe":       "Gratisprobe",
    "produkttest": "Produkttest",
}

CATEGORIES = [
    ("Tierbedarf", r"hund|katze|futter|cesar|whiskas|felix|perfect ?fit|primum|sheba|pferd|pavo|purina|"
                   r"royal canin|tiernahrung"),
    ("Baby & Kind", r"windel|baby|lillydoo|rascals|pediakid"),
    ("Lebensmittel", r"käse|joghurt|skyr|pizza|bacon|pancetta|schoko|pralinen|konfitüre|\bjam\b|riegel|"
                     r"oat bar|salami|pasta|tofu|kimchi|\beis\b|croissant|kuchen|snack|bites"),
    ("Gesundheit", r"apothek|centrum|volta|doppelherz|orthomol|zirkulin|dexcom|wund|heilsalbe|sensicutan|"
                   r"pflaster|nahrungserg|vitamin|mikronähr|moossalbe|juckreiz"),
    ("Drogerie & Pflege", r"zahn|oral-?b|sensodyne|deo\b|antitranspirant|tampon|\bo\.b\.|always|binden|tena\b|"
                          r"slip|dove|shampoo|creme|kosmetik|pflege|sebamed|mundspül|gillette|odaban|schwei|"
                          r"borotalco|duschgel|rasier|massagepad|menstru|haar|magic finish"),
    ("Haushalt", r"spül|claro|zewa|air ?wick|febreze|waschmittel|lenor|calgon|vileda|\bhg\b|reinig|fairy|"
                 r"meister proper|ariel|frosch|vanish|weichspül|küchenspray|wisch"),
    ("Getränke", r"drink|\btee\b|kaffee|jacobs|lipton|rockstar|quelle|\bsaft|säfte|wasser|tanqueray|aperitivo|"
                 r"teekanne|energy|mocktail|\blimo|\bcola\b|\bbier\b"),
]

STOP = set("""gratis testen test tester cashback geld zuruck zurueck zurück aktion aktionen kaufen erhalten
sichern prozent und oder mit der die das den dem bei nur ab bis jetzt produkte produkt dein deine auf
ein eine einen fur für von im in the frische neu neue verschiedene sorten varianten probieren 100 1 2 3
x euro eur bekommen garantie geld-zuruck gzg kostenlos vegane veganer vegan""".split())

PLATFORM_HOSTS = {"aktionen.oca-services.com", "for-me-online.de", "erlebe-haleon.de", "kassenbon-aktion.de",
                  "kinder.com", "nutella.com", "dm.de", "produkttests.rewe.de", "purina.de", "marktguru.de",
                  "danishcrown.com", "rockstarenergy.de", "jacobskaffee.de", "trifftgenuss.de"}


# ------------------------------------------------------------------ helpers

def fold(s):
    s = (s or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s


def tokens(title):
    t = re.sub(r"[^a-z0-9]+", " ", fold(title))
    return [w for w in t.split() if w not in {fold(x) for x in STOP} and len(w) > 1]


def host_path(url):
    if not url:
        return None, None
    p = urllib.parse.urlsplit(url)
    host = p.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    path = p.path.lower().rstrip("/")
    path = re.sub(r"/(tnb|terms|teilnahmebedingungen|aktion|de|de-de)$", "", path)
    return host, path


def display_name(o):
    t = o["title"]
    t = re.sub(r"(?i)^(gratis[- ]?(testen|aktion)|aktion)\s*:\s*", "", t)
    t = re.sub(r"(?i)[\s:–-]*(\(?\s*)?(100\s?%\s*)?(gratis|kostenlos)\s+(testen|probieren)!?\.?\)?\s*$", "", t)
    t = re.sub(r"(?i)\s*[:–-]\s*(100\s?%\s*(geld zurück|cashback)|gratis testen|geld zurück)\s*$", "", t)
    t = re.sub(r"(?i)\s*(kaufen,? (und )?geld zurück (bekommen|erhalten)!?)$", "", t)
    return t.strip(" -–:!")


def classify_kind(group):
    """Decide the offer type from every source's signals together."""
    blob = " ".join(filter(None, [o["title"] + " " + (o["text"] or "") + " " + (o["where"] or "")
                                  for o in group])).lower()
    urls = " ".join(o["url"] or "" for o in group).lower()
    explicit = {o["kind"] for o in group if o["kind"]}
    main_url = (pick(group, "url", PRIORITY) or "").lower()
    if "produkttest" in explicit or re.search(r"produkttests\.rewe|/produkttest|glueckskind", main_url):
        return "produkttest"
    if "probe" in explicit or re.search(r"gratisprobe|probe anfordern|probierpaket|propierpaket|testpaket|"
                                        r"futterprobe|proben-anford|\d+ tage testen", blob):
        return "probe"
    if re.search(r"unzufriedenheit|zufriedenheitsgarantie|nicht zufrieden|money-back|geschmacksgarantie|"
                 r"geld-zur(ü|u)ck-garantie", blob + " " + urls) and "gratis" not in explicit:
        return "garantie"
    if "teil" in explicit and "gratis" not in explicit:
        return "teil"
    head = " ".join(o["title"] + " " + (o["where"] or "") for o in group).lower()
    if re.search(r"\b[2-9]\s+[\wäöü-]+(\s+[\wäöü-]+){0,3}\s+kaufen", head) and not re.search(r"100\s*%", head):
        return "teil"                       # "3 kaufen, 1x Geld zurück"
    partial = re.search(r"(\d+[,.]?\d*\s*€|\b[1-9]\d?\s*%)\s*(cashback|geld|zurück)|(\d)\s*\w*\s*kaufen.{0,30}"
                        r"(1x|1 \w+ gratis|cashback für 1)|bis zu \d+\s*€ cashback", head)
    if partial and not re.search(r"100\s*%|gratis testen|kaufpreis", head) and "gratis" not in explicit:
        return "teil"
    return "gratis"


def classify_category(group):
    hint = next((o["category"] for o in group if o["category"]), None)
    blob = " ".join(o["title"] + " " + (o["text"] or "")[:200] for o in group).lower()
    title_blob = " ".join(o["title"] for o in group).lower()
    for name, pat in CATEGORIES:            # the name alone is the strongest signal
        if re.search(pat, title_blob):
            return name
    if hint:
        return hint
    for name, pat in CATEGORIES:
        if re.search(pat, blob):
            return name
    return "Lebensmittel"


# -------------------------------------------------------------------- merge

class Groups:
    def __init__(self, items):
        self.parent = list(range(len(items)))
        self.items = items

    def find(self, i):
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def members(self, root):
        return [i for i in range(len(self.items)) if self.find(i) == root]

    def union(self, a, b, force=False):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if force:
            self.parent[rb] = ra
            return
        # Two offers from the same source are never one campaign: Sparwelt lists
        # "JACOBS Ganze Bohne - 5€" and "- 3€" separately for a reason.
        sa = {self.items[i]["source"] for i in self.members(ra)}
        sb = {self.items[i]["source"] for i in self.members(rb)}
        if sa & sb:
            return
        self.parent[rb] = ra


def merge(raw):
    items = [o for o in raw if o["title"]]
    g = Groups(items)
    hp = [host_path(o["url"]) for o in items]
    # hosts that serve several campaigns need the path to match too
    per_source = {}
    for o, (h, p) in zip(items, hp):
        if h:
            per_source.setdefault((o["source"], h), set()).add(p)
    platform = PLATFORM_HOSTS | {h for (s, h), ps in per_source.items() if len(ps) > 1}
    platform = {h for h in platform} | {h2 for h2 in (h for h, _ in hp if h)
                                        if any(h2.endswith("." + x) for x in PLATFORM_HOSTS)}

    tok = [tokens(display_name(o)) for o in items]

    # pass 1: same campaign page
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (hi, pi), (hj, pj) = hp[i], hp[j]
            if not hi or hi != hj:
                continue
            if hi in platform:
                if pi and pi == pj:
                    # DailyDeal splits one campaign into several posts
                    # ("VoltaHeat …", "VoltaCool …") on the same page
                    same = items[i]["source"] == items[j]["source"] == "dailydeal" and pi.count("/") >= 2
                    g.union(i, j, force=same)
            else:
                g.union(i, j)
    # pass 2: same product name
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = set(tok[i]), set(tok[j])
            if not a or not b:
                continue
            # different campaign pages on independent hosts -> different campaigns
            (hi, pi), (hj, pj) = hp[i], hp[j]
            if hi and hj and hi != hj and hi not in platform and hj not in platform:
                continue
            if hi and hi == hj and hi in platform and pi != pj:
                continue
            jacc = len(a & b) / len(a | b)
            first = tok[i][0] == tok[j][0] and len(tok[i][0]) >= 3
            subset = (a <= b or b <= a) and max(len(w) for w in a & b or {""}) >= 4
            if (first and (jacc >= 0.3 or subset)) or jacc >= 0.6:
                g.union(i, j)

    groups = {}
    for i in range(len(items)):
        groups.setdefault(g.find(i), []).append(items[i])
    return list(groups.values())


def pick(group, field, order):
    for s in order:
        for o in group:
            if o["source"] == s and o.get(field):
                return o[field]
    return None


def build_offer(group):
    srcs = {o["source"] for o in group}
    curated = [o for o in group if o["source"] in CURATED]
    basis = curated or group
    # Curated lists sometimes lag (the sheet's partial-cashback tab was last
    # touched in August); if any of them still shows a later end, believe it.
    ends = [o["until"] for o in basis if o["until"]]
    until = max(ends) if ends else None
    start = pick(basis, "start", PRIORITY)
    added = sorted(o["added"] for o in group if o["added"])
    title = display_name(next(o for s in NAME_PRIORITY for o in group if o["source"] == s))
    kind = classify_kind(group)
    text = pick(group, "text", ["sparwelt", "sheet", "geldschnurrbart", "dealdoktor", "dailydeal"])
    if text:
        text = re.sub(r"\s*Kontakt\s*:.*$", "", text, flags=re.S).strip()
    wheres = []
    for o in group:
        for w in re.split(r",\s*", o["where"] or ""):
            if w and w.lower() not in {x.lower() for x in wheres}:
                wheres.append(w)
    links = []
    for s in PRIORITY:
        for o in group:
            if o["source"] == s and o["source_url"] and o["source_url"] not in [l["url"] for l in links]:
                links.append({"source": s, "name": SOURCES[s]["name"], "url": o["source_url"]})
    url = pick(group, "url", PRIORITY)
    ident = hashlib.sha1((fold(title) + "|" + (url or "")).encode()).hexdigest()[:10]
    return {
        "id": ident,
        "title": title,
        "kind": kind,
        "category": classify_category(group),
        "url": url,
        "until": until,
        "start": start,
        "added": added[0] if added else None,
        "image": pick(group, "image", IMAGE_PRIORITY),
        "text": text,
        "quota": pick(group, "quota", PRIORITY),
        "start_time": pick(group, "start_time", PRIORITY),
        "receipt": pick(group, "receipt", PRIORITY),
        "max_refund": pick(group, "max_refund", PRIORITY),
        "where": ", ".join(wheres) or None,
        "sources": links,
        "source_keys": sorted(srcs, key=PRIORITY.index),
    }


def keep(o, group):
    """Running (or about to start), and a free-to-try kind of offer."""
    title = o["title"].lower()
    if re.search(r"prämie|gewinnchance|gewinnen|handtuch|brotkorb|sitzsack|gutschein als", title) \
            and not re.search(r"gratis testen|cashback|geld zurück", title):
        return False
    if o["until"]:
        return o["until"] >= TODAY.isoformat()
    # undated: trust the curated lists; a DailyDeal-only post must be recent
    if any(x["source"] in CURATED for x in group):
        return True
    return bool(o["added"]) and o["added"] >= (TODAY - dt.timedelta(days=30)).isoformat()


# ------------------------------------------------------------------- images

def img_path(url):
    return os.path.join(IMGDIR, hashlib.sha1(url.encode()).hexdigest()[:16] + ".webp")


def fetch_image(url, max_px=480):
    from PIL import Image
    path = img_path(url)
    if os.path.exists(path):
        return path
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": sources.UA, "Accept": "image/*"})
        raw = urllib.request.urlopen(req, timeout=25).read()
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception:
        return None
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    if im.width < 80 or im.height < 60:          # tracking pixels, favicons
        return None
    im.thumbnail((max_px, max_px), Image.LANCZOS)
    os.makedirs(IMGDIR, exist_ok=True)
    im.save(path + ".tmp", "WEBP", quality=72, method=4)
    os.replace(path + ".tmp", path)
    return path


def campaign_image(url):
    """Fallback for offers no aggregator pictured: the campaign page's own
    og:image, which is the brand's promo shot."""
    try:
        _, page = get(url, tries=1, timeout=20)
    except Exception:
        return None
    img = og_image(page)
    return urllib.parse.urljoin(url, img) if img else None


def attach_images(offers):
    # an image shared by several unrelated offers is a site default or logo
    seen = {}
    for o in offers:
        if o["image"]:
            seen[o["image"]] = seen.get(o["image"], 0) + 1
    for o in offers:
        if o["image"] and seen[o["image"]] >= 3:
            o["image"] = None
    for o in offers:
        if not o["image"] and o["url"] and not o["url"].lower().endswith(".pdf"):
            o["image"] = campaign_image(o["url"])
    urls = sorted({o["image"] for o in offers if o["image"]})   # several offers can share one
    with ThreadPoolExecutor(8) as ex:
        paths = dict(zip(urls, ex.map(fetch_image, urls)))
    for o in offers:
        p = paths.get(o["image"])
        o["image_local"] = os.path.relpath(p, os.path.join(HERE, "web")) if p else None


# --------------------------------------------------------------------- main

def main():
    os.makedirs(DATA, exist_ok=True)
    raw_path = os.path.join(DATA, "raw.json")
    status = {}
    if "--cached" in sys.argv:
        raw = json.load(open(raw_path))
        status = json.load(open(os.path.join(DATA, "latest.json"))).get("sources", {})
    else:
        raw = []
        for key, reader in sources.READERS.items():
            t = time.time()
            try:
                got = reader()
                status[key] = {"name": SOURCES[key]["name"], "url": SOURCES[key]["url"],
                               "ok": True, "count": len(got)}
                raw += got
            except Exception as e:
                status[key] = {"name": SOURCES[key]["name"], "url": SOURCES[key]["url"],
                               "ok": False, "count": 0, "error": str(e)[:200]}
            print(f"{SOURCES[key]['name']:<16} {status[key]['count']:>4}  ({time.time()-t:.0f}s)"
                  + ("" if status[key]["ok"] else "  FEHLER " + status[key]["error"]), flush=True)
        json.dump(raw, open(raw_path, "w"), ensure_ascii=False, indent=1)

    offers = []
    for group in merge(raw):
        o = build_offer(group)
        if keep(o, group):
            offers.append(o)
    if not offers:
        print("!! keine Angebote – vorherige Daten bleiben stehen")
        sys.exit(2)
    attach_images(offers)
    for k in status:
        status[k]["kept"] = sum(1 for o in offers if k in o["source_keys"])
    iso = TODAY.isocalendar()
    out = {
        "generated": dt.datetime.now().isoformat(timespec="minutes"),
        "iso_week": f"{iso[0]}-W{iso[1]:02d}",
        "sources": status,
        "kinds": KINDS,
        "offers": sorted(offers, key=lambda o: (o["until"] or "9999", o["title"].lower())),
    }
    json.dump(out, open(os.path.join(DATA, "latest.json"), "w"), ensure_ascii=False, indent=1)
    by_kind = {}
    for o in offers:
        by_kind[o["kind"]] = by_kind.get(o["kind"], 0) + 1
    print(f"{len(offers)} Aktionen aus {len(raw)} Einträgen: "
          + ", ".join(f"{KINDS[k]} {n}" for k, n in sorted(by_kind.items(), key=lambda x: -x[1])))
    print(f"Bilder: {sum(1 for o in offers if o['image_local'])}/{len(offers)}")


if __name__ == "__main__":
    main()
