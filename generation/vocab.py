"""Name vocabularies for companies and foreign suppliers.

The built-in lists are enough on their own. `python -m generation.vocab_llm` asks the
local Qwen model for more stems and writes them to generation/vocab/llm_vocab.json; when
that file exists it is merged here. The pipeline never calls the LLM itself, so runs stay
deterministic for a given seed and vocabulary file.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

VOCAB_FILE = Path(__file__).parent / "vocab" / "llm_vocab.json"

# Words reserved for the hero cases (never generated for other companies).
RESERVED = {"alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "omega", "kappa"}

TN_STEMS = [
    "El Amen", "Ennour", "Carthage", "Yasmine", "Sahel", "El Majd", "El Wafa", "Ennajah", "El Baraka", "Essalama",
    "Essalem", "El Fajr", "Atlas", "Horizon", "Oasis", "Medina", "Cap Bon", "Djerba", "Kairouan", "Tabarka",
    "El Kheir", "Errahma", "El Hana", "Nour El Houda", "Ettakaddom", "El Ittihad", "Dar El Amen", "Rym", "Salsabil", "Zitouna",
    "El Firdaws", "Assil", "Chams", "Kamar", "Nesrine", "Amal", "El Bahja", "Tunisia", "Mediterranée", "Hannibal",
    "Elissa", "Didon", "Jugurtha", "Ifriqiya", "Byrsa", "Utique", "Thapsus", "Hadrumète", "Sufetula", "Tacapes",
    "El Mizane", "Ettaoufik", "El Fath", "Errayane", "Nakhla", "Zahra", "Warda", "Yosr", "Ines", "Selma",
    "Jasmin", "Olivier", "Sidi Bou", "Belvédère", "Lac", "Marina", "Corniche", "Kasbah", "Souk", "Riadh",
    "Ennasr", "El Menzah", "Manar", "Mutuelleville", "Mégrine", "Ezzahra", "Radès", "Hammamet", "Kélibia", "Monastir",
]
TN_FAMILIES = [
    "Ben Salah", "Jaziri", "Mejri", "Gharbi", "Chaabane", "Hammami", "Karoui", "Bouzid", "Dridi", "Ayari",
    "Mansouri", "Triki", "Masmoudi", "Ellouze", "Fourati", "Kallel", "Sellami", "Abid", "Zouari", "Belhaj",
    "Ben Amor", "Bouaziz", "Chaouachi", "Ferchichi", "Gargouri", "Hadj Ali", "Jemli", "Khemiri", "Ksibi", "Lahmar",
    "Mabrouk", "Nasri", "Ouali", "Rekik", "Saidi", "Tlili", "Zghal", "Baccar", "Chakroun", "Frikha",
    "Jarraya", "Koubaa", "Loukil", "Mhiri", "Sfar", "Turki", "Ben Youssef", "Hamdi", "Jebali", "Mahjoub",
]

SUPPLIER_PARTS = {
    "CN": {"words": ["Shenzhen", "Ningbo", "Yiwu", "Guangzhou", "Foshan", "Hangzhou", "Xiamen", "Qingdao", "Tianjin", "Dongguan", "Suzhou", "Wenzhou", "Jiangsu", "Zhejiang", "Shandong", "Hebei", "Changzhou", "Taizhou"],
           "suffix": ["Co., Ltd.", "Industrial Co., Ltd.", "Trading Co., Ltd.", "Manufacturing Co., Ltd."], "lang": "en"},
    "IT": {"words": ["Rossi", "Bianchi", "Ferrari", "Colombo", "Ricci", "Marino", "Greco", "Bruno", "Gallo", "Conti", "Esposito", "Romano", "Fontana", "Moretti", "Barbieri", "Lombardi"],
           "suffix": ["S.r.l.", "S.p.A."], "lang": "it"},
    "FR": {"words": ["Durand", "Lefebvre", "Moreau", "Laurent", "Girard", "Mercier", "Bonnet", "Dupont", "Lambert", "Fontaine", "Chevalier", "Rousseau", "Garnier", "Faure"],
           "suffix": ["SAS", "SA", "SARL"], "lang": "fr"},
    "DE": {"words": ["Keller", "Schmidt", "Wagner", "Becker", "Hoffmann", "Schulz", "Koch", "Richter", "Klein", "Wolf", "Neumann", "Braun", "Zimmermann", "Hartmann"],
           "suffix": ["GmbH", "AG", "GmbH & Co. KG"], "lang": "de"},
    "TR": {"words": ["Anadolu", "Ege", "Marmara", "Kuzey", "Yildiz", "Ozkan", "Aksoy", "Demir", "Karadeniz", "Toros", "Bursa", "Konya", "Kayseri", "Gaziantep"],
           "suffix": ["A.S.", "Ltd. Sti."], "lang": "tr"},
    "ES": {"words": ["Garcia", "Martinez", "Lopez", "Sanchez", "Fernandez", "Gomez", "Ruiz", "Navarro", "Iberica", "Levante", "Catalana", "Valenciana"],
           "suffix": ["S.L.", "S.A."], "lang": "es"},
    "DZ": {"words": ["El Djazair", "Setif", "Oran", "Annaba", "Constantine", "Tlemcen", "Bejaia", "El Hidhab", "Sahara", "Tassili"],
           "suffix": ["SARL", "EURL", "SPA"], "lang": "fr"},
}
GENERIC_PARTS = {"words": ["Global", "United", "Pacific", "Atlantic", "Continental", "Premier", "Delta Nord", "Eastern", "Western", "Royal", "Star", "Prime", "Orient", "Nordic", "Alpine", "Summit"],
                 "suffix": ["Ltd.", "Inc.", "Co.", "Group"], "lang": "en"}

PRODUCT_WORDS = {
    "en": {"30": ["Pharma", "Healthcare", "Life Sciences"], "39": ["Plastics", "Polymers", "Packaging"], "52": ["Textile", "Cotton", "Fabrics"],
           "72": ["Steel", "Metals", "Iron & Steel"], "73": ["Metal Products", "Hardware", "Steel Products"], "84": ["Machinery", "Tools", "Equipment"],
           "85": ["Electric", "Electronics", "Electrical Appliances"], "87": ["Auto Parts", "Motors", "Vehicles"]},
    "it": {"30": ["Farmaceutici"], "39": ["Plastica", "Materie Plastiche"], "52": ["Tessile", "Cotonificio"], "72": ["Acciai", "Siderurgica"],
           "73": ["Metalli", "Minuterie"], "84": ["Macchine", "Meccanica"], "85": ["Elettrica", "Elettronica"], "87": ["Ricambi Auto", "Automotive"]},
    "fr": {"30": ["Pharma", "Laboratoires"], "39": ["Plastiques", "Emballages"], "52": ["Textiles", "Tissages"], "72": ["Aciers", "Métaux"],
           "73": ["Métallerie", "Visserie"], "84": ["Equipements", "Machines"], "85": ["Electrique", "Electronique"], "87": ["Automobile", "Pièces Auto"]},
    "de": {"30": ["Pharma"], "39": ["Kunststoff", "Kunststofftechnik"], "52": ["Textil", "Weberei"], "72": ["Stahl", "Stahlhandel"],
           "73": ["Metallbau", "Schrauben"], "84": ["Maschinenbau", "Anlagenbau"], "85": ["Elektrotechnik", "Elektronik"], "87": ["Fahrzeugteile", "Automotive"]},
    "tr": {"30": ["Ilac"], "39": ["Plastik", "Ambalaj"], "52": ["Tekstil", "Iplik"], "72": ["Celik", "Demir Celik"], "73": ["Metal", "Hirdavat"],
           "84": ["Makina", "Makine Sanayi"], "85": ["Elektrik", "Elektronik"], "87": ["Otomotiv", "Yedek Parca"]},
    "es": {"30": ["Farma"], "39": ["Plasticos"], "52": ["Textil", "Tejidos"], "72": ["Aceros"], "73": ["Metalicas"], "84": ["Maquinaria"],
           "85": ["Electrica", "Electronica"], "87": ["Recambios"]},
}


@lru_cache(maxsize=1)
def _llm_vocab() -> dict:
    if VOCAB_FILE.exists():
        try:
            return json.loads(VOCAB_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


# Surnames of public figures and families associated with political cases are excluded.
BLOCKLIST = {"trabelsi", "bourguiba", "mzali", "ben ali", "bouhired", "essebsi", "caid essebsi", "ghannouchi",
             "saied", "marzouki", "materi", "chiboub", "mabrouk"}


def _acceptable(w: str) -> bool:
    low = w.lower()
    if low in BLOCKLIST or set(low.split()) & RESERVED:
        return False
    # LLM output sometimes truncates Arabic stems ("El Qa"): require a real word after the article.
    parts = low.split()
    if parts[0] in ("el", "ech", "er", "es", "et", "en") and (len(parts) < 2 or len(parts[-1]) < 4):
        return False
    return len(w) >= 3


def _merge(base: list[str], extra: list[str]) -> list[str]:
    seen = {w.lower() for w in base}
    out = [w for w in base if w.lower() not in BLOCKLIST]
    for w in extra:
        if w.lower() not in seen and _acceptable(w):
            seen.add(w.lower())
            out.append(w)
    return out


def tn_stems() -> list[str]:
    return _merge(TN_STEMS, _llm_vocab().get("tn_stems", []))


def tn_families() -> list[str]:
    return _merge(TN_FAMILIES, _llm_vocab().get("tn_families", []))


def supplier_parts(country: str) -> dict:
    base = SUPPLIER_PARTS.get(country, GENERIC_PARTS)
    extra = _llm_vocab().get("supplier_words", {}).get(country, [])
    return {**base, "words": _merge(base["words"], extra)}


class CompanyNamer:
    """Generates unique Tunisian-style company names."""

    def __init__(self, rng: np.random.Generator, taken: set[str]):
        self.rng = rng
        self.taken = {t.lower() for t in taken}
        self.stems = tn_stems()
        self.families = tn_families()

    def name(self, words: tuple[str, ...], forme: str) -> str:
        rng = self.rng
        for attempt in range(200):
            w = words[rng.integers(len(words))] if words else "Services"
            pattern = rng.integers(5)
            if pattern == 0:
                base = f"{self.stems[rng.integers(len(self.stems))]} {w}"
            elif pattern == 1:
                base = f"Société {self.families[rng.integers(len(self.families))]} {w}"
            elif pattern == 2:
                base = f"{w} {self.stems[rng.integers(len(self.stems))]}"
            elif pattern == 3:
                base = f"Société Tunisienne {w} {self.stems[rng.integers(len(self.stems))]}"
            else:
                base = f"{self.families[rng.integers(len(self.families))]} {w}"
            if attempt > 50:
                base = f"{base} {rng.integers(2, 99)}"
            full = f"{base} {forme}"
            if full.lower() not in self.taken:
                self.taken.add(full.lower())
                return full
        raise RuntimeError("could not generate a unique company name")


def supplier_name(rng: np.random.Generator, country: str, chapter: str, taken: set[str]) -> str:
    parts = supplier_parts(country)
    lang = parts["lang"]
    prods = PRODUCT_WORDS.get(lang, PRODUCT_WORDS["en"]).get(chapter) or PRODUCT_WORDS["en"].get(chapter, ["Trading"])
    for attempt in range(200):
        w = parts["words"][rng.integers(len(parts["words"]))]
        p = prods[rng.integers(len(prods))]
        s = parts["suffix"][rng.integers(len(parts["suffix"]))]
        name = f"{w} {p} {s}" if lang != "fr" or country == "DZ" else f"{p} {w} {s}"
        if country == "DZ":
            name = f"{s} {w} {p}"
        if attempt > 50:
            name = f"{w} {p} {rng.integers(2, 9)} {s}"
        if name not in taken:
            taken.add(name)
            return name
    raise RuntimeError("could not generate a unique supplier name")
