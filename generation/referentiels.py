"""Reference tables (data/raw/ref_*.csv) and the sector behaviour parameters used by the simulation.

Published columns follow modele_donnees.md 2.13 exactly. Internal behaviour parameters
(seasonality, VAT mix, public-buyer propensity...) stay in Python and are not published.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# NAT 2009 classes
# ---------------------------------------------------------------------------
# family drives supplier affinity, seasonality and labour intensity.
#   GROS: wholesale, DETAIL: retail, INDUSTRIE, BTP, TRANSPORT, SERVICES, HORECA, AUTRE


@dataclass(frozen=True)
class Nat:
    code: str
    libelle: str
    section: str
    family: str
    weight: float                 # share of the population (%)
    marge: float                  # marge_brute_reference (benchmark, 3.4)
    part_imp: float               # probability of being an importer
    chapitres: tuple[str, ...]    # HS chapters imported
    ca_mult: float = 1.0          # turnover multiplier vs size-class median
    labour: float = 0.0           # share of cost of sales that is labour (not purchases)
    vat: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)  # shares 19/13/7/exempt of domestic sales
    export: float = 0.0           # export share of an onshore company
    offshore: float = 0.0         # probability of being TOTALEMENT_EXPORTATRICE
    b2b: float = 0.6              # share of sales made to other companies (annex V visibility)
    public: float = 0.03          # probability of receiving ADEB payments
    public_share: tuple[float, float] = (0.05, 0.25)
    season: str = "flat"
    salary: float = 16_000.0      # mean annual gross salary (TND)
    taux_is: float = 20.0
    words: tuple[str, ...] = field(default_factory=tuple)


NAT_CLASSES: list[Nat] = [
    # Wholesale (20 %)
    Nat("46.43", "Commerce de gros d'appareils électroménagers", "G", "GROS", 3.0, 0.31, 0.85, ("85", "84"), 1.6, vat=(1, 0, 0, 0), b2b=0.85, public=0.08, words=("Electroménager", "Home Appliances", "Distribution Electro")),
    Nat("46.46", "Commerce de gros de produits pharmaceutiques", "G", "GROS", 1.5, 0.25, 0.80, ("30",), 2.0, vat=(0.1, 0, 0.9, 0), b2b=0.9, public=0.30, salary=24_000, words=("Pharma", "Médical Distribution", "Santé Distribution")),
    Nat("46.49", "Commerce de gros d'autres biens domestiques", "G", "GROS", 2.0, 0.31, 0.65, ("39", "73", "85"), 1.4, b2b=0.85, public=0.05, words=("Distribution", "Home Center", "Articles Ménagers")),
    Nat("46.51", "Commerce de gros d'ordinateurs, d'équipements informatiques périphériques et de logiciels", "G", "GROS", 1.5, 0.28, 0.80, ("84", "85"), 1.5, b2b=0.9, public=0.25, salary=22_000, words=("Informatique", "Computer", "Systèmes")),
    Nat("46.69", "Commerce de gros d'autres machines et équipements", "G", "GROS", 3.0, 0.31, 0.80, ("84", "85"), 1.4, b2b=0.9, public=0.15, words=("Equipements", "Machines", "Industrial Supply")),
    Nat("46.73", "Commerce de gros de bois, de matériaux de construction et d'appareils sanitaires", "G", "GROS", 2.5, 0.22, 0.60, ("72", "73", "39"), 1.6, b2b=0.8, public=0.12, season="btp", words=("Matériaux", "Matériaux de Construction", "Sanitaires")),
    Nat("46.74", "Commerce de gros de quincaillerie et fournitures pour plomberie et chauffage", "G", "GROS", 1.5, 0.28, 0.60, ("73", "84"), 1.3, b2b=0.8, public=0.08, season="btp", words=("Quincaillerie", "Outillage", "Plomberie Distribution")),
    Nat("46.76", "Commerce de gros d'autres produits intermédiaires", "G", "GROS", 1.0, 0.24, 0.70, ("39", "52", "72"), 1.5, b2b=0.95, public=0.03, words=("Négoce Industriel", "Matières Premières", "Intermédiaires")),
    Nat("46.90", "Commerce de gros non spécialisé", "G", "GROS", 3.0, 0.27, 0.60, ("39", "73", "84", "85"), 1.3, b2b=0.8, public=0.06, words=("Négoce", "Import-Export", "Trading", "Commerce International")),
    Nat("45.31", "Commerce de gros d'équipements automobiles", "G", "GROS", 1.0, 0.30, 0.80, ("87", "85", "84"), 1.3, b2b=0.75, public=0.05, words=("Auto Pièces", "Pièces Auto", "Auto Parts")),
    # Retail (20 %)
    Nat("47.11", "Commerce de détail en magasin non spécialisé à prédominance alimentaire", "G", "DETAIL", 5.0, 0.22, 0.10, ("39", "85"), 1.2, vat=(0.45, 0, 0.2, 0.35), b2b=0.05, public=0.02, season="retail", salary=11_000, words=("Market", "Supérette", "Alimentation Générale")),
    Nat("47.41", "Commerce de détail d'ordinateurs, d'unités périphériques et de logiciels", "G", "DETAIL", 2.0, 0.30, 0.35, ("84", "85"), 0.9, b2b=0.25, public=0.05, season="retail", words=("Info Store", "Micro Informatique", "Digital Store")),
    Nat("47.52", "Commerce de détail de quincaillerie, peintures et verres", "G", "DETAIL", 4.0, 0.33, 0.25, ("73", "39"), 0.9, b2b=0.3, public=0.02, season="btp", words=("Bricolage", "Droguerie", "Quincaillerie")),
    Nat("47.71", "Commerce de détail d'habillement en magasin spécialisé", "G", "DETAIL", 4.0, 0.45, 0.15, ("52",), 0.8, b2b=0.02, public=0.0, season="retail", salary=10_000, words=("Mode", "Boutique", "Fashion")),
    Nat("47.73", "Commerce de détail de produits pharmaceutiques et parapharmaceutiques", "G", "DETAIL", 3.0, 0.30, 0.20, ("30",), 1.0, vat=(0.3, 0, 0.7, 0), b2b=0.05, public=0.03, words=("Parapharmacie", "Para Santé", "Bien-Etre")),
    Nat("45.11", "Commerce de voitures et de véhicules automobiles légers", "G", "DETAIL", 2.0, 0.15, 0.70, ("87",), 3.0, b2b=0.35, public=0.10, taux_is=35.0, salary=20_000, words=("Automobiles", "Motors", "Auto")),
    # Manufacturing (22 %)
    Nat("10.71", "Fabrication de pain et de pâtisserie fraîche", "C", "INDUSTRIE", 3.0, 0.23, 0.10, ("84", "39"), 0.6, labour=0.3, vat=(0.3, 0, 0.2, 0.5), b2b=0.25, public=0.05, salary=11_000, words=("Boulangerie", "Pâtisserie", "Viennoiserie")),
    Nat("10.39", "Autre transformation et conservation de fruits et légumes", "C", "INDUSTRIE", 2.0, 0.23, 0.40, ("39", "73", "84"), 1.1, labour=0.2, vat=(0.3, 0, 0.7, 0), export=0.3, b2b=0.8, public=0.02, season="agro", salary=11_000, words=("Conserves", "Agro", "Agro-Alimentaire")),
    Nat("13.20", "Tissage", "C", "INDUSTRIE", 1.5, 0.30, 0.70, ("52", "84"), 1.0, labour=0.1, export=0.35, offshore=0.35, b2b=0.85, public=0.0, salary=12_000, words=("Tissage", "Textile", "Tissus")),
    Nat("14.13", "Fabrication d'autres vêtements de dessus", "C", "INDUSTRIE", 3.0, 0.35, 0.70, ("52", "39"), 0.8, labour=0.1, export=0.3, offshore=0.35, b2b=0.85, public=0.0, salary=11_000, words=("Confection", "Textile", "Habillement")),
    Nat("14.14", "Fabrication de vêtements de dessous", "C", "INDUSTRIE", 1.5, 0.35, 0.70, ("52",), 0.8, labour=0.1, export=0.3, offshore=0.35, b2b=0.85, public=0.0, salary=11_000, words=("Lingerie", "Confection", "Bonneterie")),
    Nat("22.22", "Fabrication d'emballages en matières plastiques", "C", "INDUSTRIE", 2.0, 0.25, 0.65, ("39", "84"), 1.1, labour=0.2, export=0.1, b2b=0.9, public=0.03, words=("Emballages", "Plast", "Packaging")),
    Nat("22.29", "Fabrication d'autres articles en matières plastiques", "C", "INDUSTRIE", 1.5, 0.25, 0.60, ("39",), 1.0, labour=0.2, export=0.1, b2b=0.8, public=0.05, words=("Plastiques", "Plast Industrie", "Polymères")),
    Nat("25.11", "Fabrication de structures métalliques et de parties de structures", "C", "INDUSTRIE", 2.5, 0.18, 0.55, ("72", "73"), 1.0, labour=0.25, b2b=0.75, public=0.25, season="btp", salary=13_000, words=("Constructions Métalliques", "Charpente Métallique", "Métal")),
    Nat("25.62", "Usinage", "C", "INDUSTRIE", 1.5, 0.25, 0.45, ("72", "84"), 0.8, labour=0.35, export=0.15, b2b=0.9, public=0.03, salary=14_000, words=("Mécanique de Précision", "Usinage", "Mécanique Générale")),
    Nat("27.32", "Fabrication d'autres fils et câbles électroniques ou électriques", "C", "INDUSTRIE", 1.5, 0.22, 0.75, ("85", "39"), 1.2, labour=0.3, export=0.4, offshore=0.4, b2b=0.9, public=0.05, salary=13_000, words=("Câblage", "Câbles", "Wiring")),
    Nat("21.20", "Fabrication de préparations pharmaceutiques", "C", "INDUSTRIE", 1.0, 0.45, 0.80, ("30", "39"), 2.0, labour=0.2, vat=(0.1, 0, 0.9, 0), export=0.1, b2b=0.9, public=0.20, salary=26_000, words=("Laboratoires", "Pharmaceutique", "Pharma Industrie")),
    Nat("29.31", "Fabrication d'équipements électriques et électroniques automobiles", "C", "INDUSTRIE", 1.0, 0.20, 0.75, ("85", "87", "39"), 1.5, labour=0.3, export=0.5, offshore=0.45, b2b=0.95, public=0.0, salary=14_000, words=("Automotive", "Composants Auto", "Auto Systems")),
    # Construction (12 %)
    Nat("41.20", "Construction de bâtiments résidentiels et non résidentiels", "F", "BTP", 5.0, 0.15, 0.08, ("72", "73", "39"), 1.0, labour=0.3, vat=(0.8, 0.2, 0, 0), b2b=0.45, public=0.40, public_share=(0.1, 0.6), season="btp", salary=12_000, words=("Bâtiment", "Construction", "Immobilière de Construction")),
    Nat("42.11", "Construction de routes et autoroutes", "F", "BTP", 2.0, 0.15, 0.15, ("84", "87", "73"), 1.2, labour=0.3, b2b=0.3, public=0.85, public_share=(0.3, 0.65), season="btp", salary=13_000, words=("Travaux", "Travaux Publics", "Routes et Ouvrages")),
    Nat("43.21", "Installation électrique", "F", "BTP", 3.0, 0.20, 0.10, ("85",), 0.8, labour=0.35, b2b=0.6, public=0.35, public_share=(0.1, 0.5), season="btp", salary=13_000, words=("Electricité", "Electricité Générale", "Installations Electriques")),
    Nat("43.22", "Travaux de plomberie et installation de chauffage et de conditionnement d'air", "F", "BTP", 2.0, 0.20, 0.10, ("73", "84"), 0.8, labour=0.35, b2b=0.6, public=0.30, public_share=(0.1, 0.5), season="btp", salary=12_500, words=("Plomberie", "Sanitaire", "Climatisation")),
    # Transport (8 %)
    Nat("49.41", "Transports routiers de fret", "H", "TRANSPORT", 5.0, 0.25, 0.05, ("87",), 0.7, labour=0.45, b2b=0.9, public=0.10, salary=13_000, words=("Transport", "Logistique", "Transport International")),
    Nat("52.29", "Autres services auxiliaires des transports", "H", "TRANSPORT", 3.0, 0.30, 0.03, ("84",), 0.8, labour=0.5, b2b=0.95, public=0.05, salary=16_000, words=("Transit", "Logistique", "Shipping")),
    # Business services / ICT (10 %)
    Nat("62.01", "Programmation informatique", "J", "SERVICES", 2.5, 0.33, 0.05, ("84", "85"), 0.5, labour=0.75, export=0.25, b2b=0.9, public=0.30, salary=26_000, words=("Software", "Digital", "Tech")),
    Nat("62.02", "Conseil informatique", "J", "SERVICES", 1.5, 0.33, 0.05, ("84",), 0.5, labour=0.75, export=0.15, b2b=0.95, public=0.30, salary=28_000, words=("IT Consulting", "Systèmes d'Information", "Solutions")),
    Nat("69.20", "Activités comptables", "M", "SERVICES", 2.0, 0.33, 0.0, (), 0.4, labour=0.8, b2b=0.95, public=0.05, salary=20_000, words=("Audit et Conseil", "Expertise Comptable", "Fiduciaire")),
    Nat("70.22", "Conseil pour les affaires et autres conseils de gestion", "M", "SERVICES", 1.5, 0.33, 0.0, (), 0.4, labour=0.75, export=0.1, b2b=0.95, public=0.15, salary=24_000, words=("Consulting", "Conseil", "Management")),
    Nat("71.12", "Activités d'ingénierie", "M", "SERVICES", 1.5, 0.33, 0.03, ("84",), 0.5, labour=0.7, b2b=0.8, public=0.40, public_share=(0.1, 0.5), salary=24_000, words=("Ingénierie", "Etudes", "Engineering")),
    Nat("73.11", "Activités des agences de publicité", "M", "SERVICES", 1.0, 0.33, 0.02, ("85",), 0.5, labour=0.6, b2b=0.95, public=0.10, salary=18_000, words=("Communication", "Publicité", "Media")),
    # Hotels and restaurants (5 %)
    Nat("55.10", "Hôtels et hébergement similaire", "I", "HORECA", 2.0, 0.32, 0.05, ("84", "85"), 1.2, labour=0.4, vat=(0.1, 0, 0.9, 0), export=0.3, b2b=0.2, public=0.03, season="tourism", salary=11_000, taux_is=10.0, words=("Hôtel", "Résidence", "Palace")),
    Nat("56.10", "Restauration traditionnelle", "I", "HORECA", 3.0, 0.32, 0.03, ("84",), 0.5, labour=0.4, vat=(0.4, 0, 0.6, 0), b2b=0.1, public=0.02, season="tourism", salary=10_000, words=("Restaurant", "Grill", "Food")),
    # Other (3 %)
    Nat("85.59", "Enseignements divers", "P", "AUTRE", 1.5, 0.40, 0.02, ("84",), 0.3, labour=0.7, vat=(0.5, 0, 0.5, 0), b2b=0.1, public=0.05, salary=14_000, words=("Formation", "Académie", "Training Center")),
    Nat("81.21", "Nettoyage courant des bâtiments", "N", "AUTRE", 1.5, 0.30, 0.02, ("84", "39"), 0.4, labour=0.7, b2b=0.9, public=0.35, salary=9_500, words=("Services", "Nettoyage", "Clean Services")),
]
NAT_BY_CODE = {n.code: n for n in NAT_CLASSES}

SECTION_LIBELLES = {
    "C": "Industrie manufacturière", "F": "Construction", "G": "Commerce ; réparation d'automobiles et de motocycles",
    "H": "Transports et entreposage", "I": "Hébergement et restauration", "J": "Information et communication",
    "M": "Activités spécialisées, scientifiques et techniques", "N": "Activités de services administratifs et de soutien",
    "P": "Enseignement",
}

# Monthly seasonality profiles (index 0 = January), amplitude within +/-15 %.
SEASON_PROFILES = {
    "flat": np.array([0.97, 0.96, 1.00, 1.00, 1.01, 1.00, 0.98, 0.93, 1.02, 1.03, 1.03, 1.07]),
    "retail": np.array([0.92, 0.90, 1.08, 1.05, 0.98, 0.97, 1.02, 1.00, 1.06, 0.97, 0.97, 1.08]),
    "btp": np.array([0.88, 0.90, 0.98, 1.03, 1.08, 1.12, 1.10, 0.95, 1.03, 1.02, 0.98, 0.93]),
    "tourism": np.array([0.85, 0.86, 0.92, 0.98, 1.05, 1.13, 1.15, 1.15, 1.10, 1.00, 0.91, 0.90]),
    "agro": np.array([0.90, 0.88, 0.94, 1.00, 1.08, 1.14, 1.12, 1.05, 1.00, 0.98, 0.95, 0.96]),
}

# Local supplier affinity: which families a client family buys from (weights).
SUPPLIER_AFFINITY = {
    "GROS": {"GROS": 0.35, "INDUSTRIE": 0.30, "SERVICES": 0.15, "TRANSPORT": 0.15, "AUTRE": 0.05},
    "DETAIL": {"GROS": 0.60, "INDUSTRIE": 0.20, "SERVICES": 0.08, "TRANSPORT": 0.07, "AUTRE": 0.05},
    "INDUSTRIE": {"GROS": 0.35, "INDUSTRIE": 0.30, "SERVICES": 0.12, "TRANSPORT": 0.18, "AUTRE": 0.05},
    "BTP": {"GROS": 0.45, "INDUSTRIE": 0.20, "BTP": 0.15, "SERVICES": 0.08, "TRANSPORT": 0.12},
    "TRANSPORT": {"GROS": 0.50, "SERVICES": 0.20, "TRANSPORT": 0.20, "AUTRE": 0.10},
    "SERVICES": {"GROS": 0.35, "SERVICES": 0.40, "DETAIL": 0.10, "AUTRE": 0.15},
    "HORECA": {"GROS": 0.40, "INDUSTRIE": 0.25, "DETAIL": 0.15, "AUTRE": 0.15, "SERVICES": 0.05},
    "AUTRE": {"GROS": 0.40, "SERVICES": 0.30, "DETAIL": 0.20, "AUTRE": 0.10},
}


# ---------------------------------------------------------------------------
# Customs nomenclature (NDP 11 digits = NGP 10 digits + key digit)
# ---------------------------------------------------------------------------
# (sh6, designation, unit, reference unit price in TND, customs duty %, kg per unit)
_NDP_ROWS: list[tuple[str, str, str, float, float, float]] = [
    # Chapter 30: pharmaceutical products (DD 0, VAT 7, no FODEC)
    ("300210", "Antisérums et autres fractions du sang", "KG", 2500, 0, 1),
    ("300215", "Produits immunologiques présentés sous forme de doses", "KG", 9000, 0, 1),
    ("300241", "Vaccins pour la médecine humaine", "U", 35, 0, 0.05),
    ("300310", "Médicaments contenant des pénicillines, non dosés", "KG", 180, 0, 1),
    ("300420", "Médicaments contenant d'autres antibiotiques, dosés", "KG", 260, 0, 1),
    ("300431", "Médicaments contenant de l'insuline, dosés", "KG", 1400, 0, 1),
    ("300432", "Médicaments contenant des hormones corticostéroïdes, dosés", "KG", 420, 0, 1),
    ("300439", "Médicaments contenant d'autres hormones, dosés", "KG", 650, 0, 1),
    ("300449", "Médicaments contenant des alcaloïdes, dosés", "KG", 380, 0, 1),
    ("300450", "Médicaments contenant des vitamines, dosés", "KG", 120, 0, 1),
    ("300490", "Autres médicaments dosés pour usages thérapeutiques", "KG", 300, 0, 1),
    ("300510", "Pansements adhésifs et articles à couche adhésive", "KG", 45, 0, 1),
    ("300590", "Ouates, gazes, bandes et articles analogues", "KG", 22, 0, 1),
    ("300610", "Catguts stériles et ligatures pour sutures chirurgicales", "KG", 900, 0, 1),
    ("300630", "Préparations opacifiantes pour examens radiographiques", "KG", 350, 0, 1),
    ("300650", "Trousses et boîtes de pharmacie garnies pour premiers soins", "U", 25, 0, 0.4),
    ("300660", "Préparations chimiques contraceptives", "KG", 500, 0, 1),
    ("300692", "Déchets pharmaceutiques et médicaments périmés conditionnés", "KG", 15, 0, 1),
    # Chapter 39: plastics
    ("390110", "Polyéthylène d'une densité inférieure à 0,94", "KG", 5.2, 0, 1),
    ("390120", "Polyéthylène d'une densité égale ou supérieure à 0,94", "KG", 5.0, 0, 1),
    ("390210", "Polypropylène, sous formes primaires", "KG", 4.9, 0, 1),
    ("390311", "Polystyrène expansible", "KG", 6.0, 0, 1),
    ("390410", "Poly(chlorure de vinyle) non mélangé à d'autres substances", "KG", 3.8, 0, 1),
    ("390761", "Poly(éthylène téréphtalate) d'un indice de viscosité >= 78 ml/g", "KG", 4.3, 0, 1),
    ("390810", "Polyamides-6, -11, -12, -6,6, sous formes primaires", "KG", 9.5, 0, 1),
    ("390950", "Polyuréthanes, sous formes primaires", "KG", 11.0, 0, 1),
    ("391732", "Tubes et tuyaux flexibles en matières plastiques, non renforcés", "KG", 14.0, 20, 1),
    ("391740", "Accessoires de tuyauterie en matières plastiques", "KG", 22.0, 20, 1),
    ("391910", "Plaques et bandes autoadhésives en rouleaux, largeur <= 20 cm", "KG", 16.0, 20, 1),
    ("392010", "Plaques et feuilles en polymères de l'éthylène", "KG", 7.5, 20, 1),
    ("392020", "Plaques et feuilles en polymères du propylène", "KG", 8.0, 20, 1),
    ("392321", "Sacs, sachets et cornets en polymères de l'éthylène", "KG", 7.0, 20, 1),
    ("392330", "Bonbonnes, bouteilles, flacons en matières plastiques", "KG", 9.0, 20, 1),
    ("392350", "Bouchons, couvercles, capsules en matières plastiques", "KG", 12.0, 20, 1),
    ("392410", "Vaisselle et ustensiles de cuisine en matières plastiques", "KG", 10.0, 20, 1),
    ("392490", "Autres articles de ménage en matières plastiques", "KG", 9.0, 20, 1),
    ("392690", "Autres ouvrages en matières plastiques", "KG", 20.0, 20, 1),
    # Chapter 52: cotton
    ("520100", "Coton, non cardé ni peigné", "KG", 6.5, 0, 1),
    ("520411", "Fils à coudre de coton contenant >= 85 % de coton", "KG", 35.0, 20, 1),
    ("520512", "Fils de coton simples en fibres non peignées", "KG", 12.0, 20, 1),
    ("520523", "Fils de coton simples en fibres peignées", "KG", 15.0, 20, 1),
    ("520622", "Fils de coton simples en fibres peignées, < 85 % de coton", "KG", 11.0, 20, 1),
    ("520811", "Tissus de coton écrus, armure toile, <= 100 g/m2", "KG", 22.0, 20, 1),
    ("520812", "Tissus de coton écrus, armure toile, > 100 g/m2", "KG", 21.0, 20, 1),
    ("520822", "Tissus de coton blanchis, armure toile, > 100 g/m2", "KG", 24.0, 20, 1),
    ("520832", "Tissus de coton teints, armure toile, > 100 g/m2", "KG", 27.0, 20, 1),
    ("520842", "Tissus de coton en fils de diverses couleurs, armure toile", "KG", 30.0, 20, 1),
    ("520852", "Tissus de coton imprimés, armure toile, > 100 g/m2", "KG", 32.0, 20, 1),
    ("520912", "Tissus de coton écrus, armure sergé, >= 200 g/m2", "KG", 20.0, 20, 1),
    ("520942", "Tissus dits denim, >= 200 g/m2", "KG", 26.0, 20, 1),
    ("520952", "Tissus de coton imprimés, >= 200 g/m2", "KG", 30.0, 20, 1),
    ("521031", "Tissus de coton teints mélangés de fibres synthétiques", "KG", 28.0, 20, 1),
    ("521142", "Tissus dits denim mélangés de fibres synthétiques", "KG", 27.0, 20, 1),
    ("521211", "Autres tissus de coton écrus, <= 200 g/m2", "KG", 23.0, 20, 1),
    ("521213", "Autres tissus de coton teints, <= 200 g/m2", "KG", 28.0, 20, 1),
    # Chapter 72: iron and steel
    ("720711", "Demi-produits en fer ou en aciers non alliés, section carrée", "KG", 1.9, 15, 1),
    ("720827", "Produits laminés plats à chaud, en rouleaux, épaisseur < 3 mm", "KG", 2.6, 15, 1),
    ("720838", "Produits laminés plats à chaud, épaisseur 3 à 4,75 mm", "KG", 2.5, 15, 1),
    ("720916", "Produits laminés plats à froid, épaisseur 1 à 3 mm", "KG", 2.9, 15, 1),
    ("721012", "Produits laminés plats étamés, épaisseur < 0,5 mm", "KG", 4.2, 20, 1),
    ("721049", "Produits laminés plats zingués, autrement qu'électrolytiquement", "KG", 3.3, 20, 1),
    ("721070", "Produits laminés plats peints, vernis ou revêtus de matières plastiques", "KG", 3.8, 20, 1),
    ("721310", "Fil machine comportant des empreintes obtenues au laminage", "KG", 2.3, 15, 1),
    ("721420", "Barres comportant des empreintes (ronds à béton)", "KG", 2.4, 20, 1),
    ("721491", "Autres barres en fer ou aciers non alliés, section rectangulaire", "KG", 2.7, 20, 1),
    ("721631", "Profilés en U en fer ou aciers non alliés, hauteur >= 80 mm", "KG", 2.9, 20, 1),
    ("721633", "Profilés en H en fer ou aciers non alliés, hauteur >= 80 mm", "KG", 3.0, 20, 1),
    ("721710", "Fils en fer ou aciers non alliés, non revêtus", "KG", 3.1, 20, 1),
    ("721720", "Fils en fer ou aciers non alliés, zingués", "KG", 3.4, 20, 1),
    ("722011", "Produits laminés plats en aciers inoxydables, épaisseur >= 4,75 mm", "KG", 11.0, 15, 1),
    ("722219", "Barres en aciers inoxydables, simplement obtenues à chaud", "KG", 12.0, 15, 1),
    ("722830", "Barres en autres aciers alliés, simplement laminées à chaud", "KG", 5.5, 15, 1),
    ("722490", "Demi-produits en autres aciers alliés", "KG", 4.8, 15, 1),
    # Chapter 73: articles of iron or steel
    ("730431", "Tubes sans soudure étirés ou laminés à froid", "KG", 6.5, 20, 1),
    ("730630", "Tubes soudés de section circulaire en fer ou aciers non alliés", "KG", 4.2, 20, 1),
    ("730661", "Tubes soudés de section carrée ou rectangulaire", "KG", 4.5, 20, 1),
    ("730721", "Brides en aciers inoxydables", "KG", 22.0, 20, 1),
    ("730820", "Tours et pylônes en fonte, fer ou acier", "KG", 5.5, 20, 1),
    ("730890", "Autres constructions et parties de constructions en fer ou acier", "KG", 6.0, 20, 1),
    ("730900", "Réservoirs, foudres, cuves d'une contenance > 300 l", "KG", 8.0, 20, 1),
    ("731010", "Réservoirs, fûts, tambours d'une contenance de 50 à 300 l", "KG", 7.0, 20, 1),
    ("731210", "Torons et câbles en fer ou acier, non isolés", "KG", 5.8, 20, 1),
    ("731300", "Ronces artificielles en fer ou acier", "KG", 4.0, 20, 1),
    ("731414", "Toiles métalliques tissées en aciers inoxydables", "KG", 6.0, 20, 1),
    ("731815", "Autres vis et boulons, même avec écrous", "KG", 9.0, 20, 1),
    ("731816", "Ecrous en fonte, fer ou acier", "KG", 9.5, 20, 1),
    ("731822", "Autres rondelles en fonte, fer ou acier", "KG", 8.0, 20, 1),
    ("732111", "Appareils de cuisson et chauffe-plats à combustibles gazeux", "U", 450, 30, 25),
    ("732393", "Articles de ménage en aciers inoxydables", "KG", 25.0, 30, 1),
    ("732410", "Eviers et lavabos en aciers inoxydables", "U", 180, 30, 8),
    ("732690", "Autres ouvrages en fer ou en acier", "KG", 12.0, 20, 1),
    # Chapter 84: machinery
    ("841370", "Pompes centrifuges", "U", 2800, 0, 45),
    ("841381", "Autres pompes pour liquides", "U", 3500, 0, 60),
    ("841430", "Compresseurs des types utilisés dans les équipements frigorifiques", "U", 900, 0, 12),
    ("841480", "Compresseurs d'air et autres pompes à air", "U", 6500, 0, 120),
    ("841510", "Climatiseurs muraux ou pour fenêtres, formant un seul corps ou split-system", "U", 1400, 30, 40),
    ("841582", "Autres climatiseurs avec dispositif de réfrigération", "U", 5200, 30, 150),
    ("841821", "Réfrigérateurs ménagers à compression", "U", 1300, 30, 60),
    ("841850", "Meubles frigorifiques de conservation et d'exposition", "U", 4200, 30, 150),
    ("842211", "Machines à laver la vaisselle de type ménager", "U", 1600, 30, 45),
    ("842240", "Autres machines et appareils à emballer ou à empaqueter", "U", 38000, 0, 900),
    ("842710", "Chariots autopropulsés à moteur électrique", "U", 45000, 0, 2500),
    ("842951", "Chargeuses et chargeuses-pelleteuses à chargement frontal", "U", 210000, 0, 12000),
    ("842952", "Pelles mécaniques dont la superstructure peut effectuer une rotation de 360 degrés", "U", 280000, 0, 20000),
    ("845011", "Machines à laver le linge entièrement automatiques, capacité <= 10 kg", "U", 1250, 30, 65),
    ("845121", "Machines à sécher le linge, capacité <= 10 kg", "U", 1900, 30, 45),
    ("845210", "Machines à coudre de type ménager", "U", 600, 15, 9),
    ("845229", "Autres machines à coudre industrielles", "U", 4800, 0, 60),
    ("845811", "Tours horizontaux à commande numérique", "U", 145000, 0, 4000),
    ("847130", "Machines automatiques de traitement de l'information portatives", "U", 2100, 0, 2),
    ("847141", "Autres machines automatiques de traitement de l'information", "U", 2900, 0, 9),
    ("847160", "Unités d'entrée ou de sortie", "U", 450, 0, 5),
    ("847170", "Unités de mémoire", "U", 380, 0, 0.5),
    ("847330", "Parties et accessoires des machines du n° 8471", "KG", 85, 0, 1),
    ("847790", "Parties de machines pour le travail du caoutchouc ou des matières plastiques", "KG", 70, 0, 1),
    ("847989", "Autres machines et appareils mécaniques à fonction propre", "U", 22000, 0, 600),
    ("848180", "Autres articles de robinetterie", "KG", 40, 20, 1),
    ("848210", "Roulements à billes", "KG", 35, 15, 1),
    ("848340", "Engrenages et roues de friction, broches filetées", "KG", 45, 15, 1),
    # Chapter 85: electrical machinery
    ("850110", "Moteurs d'une puissance n'excédant pas 37,5 W", "U", 30, 15, 0.5),
    ("850152", "Moteurs polyphasés d'une puissance > 750 W et <= 75 kW", "U", 1200, 0, 40),
    ("850421", "Transformateurs à diélectrique liquide, puissance <= 650 kVA", "U", 28000, 0, 1500),
    ("850440", "Convertisseurs statiques", "U", 350, 15, 3),
    ("850650", "Piles et batteries de piles électriques, au lithium", "KG", 90, 20, 1),
    ("850710", "Accumulateurs au plomb pour le démarrage des moteurs à piston", "U", 260, 30, 18),
    ("850760", "Accumulateurs au lithium-ion", "KG", 120, 15, 1),
    ("850940", "Broyeurs et mélangeurs pour aliments, presse-fruits", "U", 140, 30, 3),
    ("851621", "Radiateurs à accumulation", "U", 250, 30, 12),
    ("851650", "Fours à micro-ondes", "U", 330, 30, 13),
    ("851660", "Autres fours, cuisinières, réchauds et grils", "U", 900, 30, 35),
    ("851713", "Smartphones", "U", 1100, 0, 0.2),
    ("851762", "Appareils pour la réception et la transmission de données (routeurs)", "U", 480, 0, 1),
    ("852872", "Autres appareils récepteurs de télévision, en couleurs", "U", 1200, 30, 12),
    ("853690", "Autres appareils pour la connexion de circuits électriques, <= 1000 V", "KG", 110, 15, 1),
    ("853710", "Tableaux et panneaux de commande, tension <= 1000 V", "U", 3200, 15, 60),
    ("853921", "Lampes et tubes halogènes au tungstène", "U", 6, 20, 0.05),
    ("854143", "Cellules photovoltaïques assemblées en modules ou panneaux", "U", 380, 0, 22),
    ("854442", "Autres conducteurs électriques munis de pièces de connexion, <= 1000 V", "KG", 45, 15, 1),
    ("854449", "Autres conducteurs électriques, tension <= 1000 V", "KG", 32, 15, 1),
    # Chapter 87: vehicles
    ("870120", "Tracteurs routiers pour semi-remorques", "U", 230000, 15, 8000),
    ("870322", "Voitures de tourisme, cylindrée 1000 à 1500 cm3", "U", 52000, 30, 1100),
    ("870323", "Voitures de tourisme, cylindrée 1500 à 3000 cm3", "U", 75000, 30, 1400),
    ("870332", "Voitures de tourisme diesel, cylindrée 1500 à 2500 cm3", "U", 85000, 30, 1500),
    ("870380", "Voitures de tourisme à moteur électrique", "U", 110000, 0, 1700),
    ("870421", "Véhicules pour le transport de marchandises, diesel, PTC <= 5 t", "U", 68000, 15, 1800),
    ("870422", "Véhicules pour le transport de marchandises, diesel, PTC 5 à 20 t", "U", 160000, 15, 6000),
    ("870829", "Parties et accessoires de carrosseries", "KG", 28, 20, 1),
    ("870830", "Freins et servofreins et leurs parties", "KG", 30, 20, 1),
    ("870840", "Boîtes de vitesses et leurs parties", "U", 3800, 20, 60),
    ("870850", "Ponts avec différentiel et essieux porteurs", "U", 5200, 20, 150),
    ("870870", "Roues, leurs parties et accessoires", "U", 320, 20, 12),
    ("870880", "Systèmes de suspension et leurs parties", "KG", 30, 20, 1),
    ("870891", "Radiateurs et leurs parties", "U", 420, 20, 8),
    ("870899", "Autres parties et accessoires de véhicules automobiles", "KG", 35, 20, 1),
    ("871120", "Motocycles à moteur à piston, cylindrée 50 à 250 cm3", "U", 4200, 30, 110),
    ("871200", "Bicyclettes et autres cycles, sans moteur", "U", 450, 30, 14),
    ("871639", "Autres remorques et semi-remorques pour le transport de marchandises", "U", 48000, 15, 5500),
]


def _ndp_key(ngp: str) -> str:
    """Synthetic key digit (the official algorithm is not public)."""
    s = sum((i % 3 + 1) * int(d) for i, d in enumerate(ngp))
    return str(s % 10)


def build_ref_ndp() -> pd.DataFrame:
    rows = []
    for sh6, lib, unit, price, dd, kg in _NDP_ROWS:
        ngp = sh6 + ("9997" if sh6 == "847989" else "0000")
        ndp = "84798997000" if sh6 == "847989" else ngp + _ndp_key(ngp)
        chap = sh6[:2]
        rows.append({
            "code_ndp": ndp, "code_sh6": sh6, "chapitre_sh": chap, "designation": lib, "unite": unit,
            "prix_reference_tnd": float(price), "taux_dd": float(dd),
            "taux_tva": 7.0 if chap == "30" else 19.0,
            "taux_fodec": 0.0 if chap == "30" else 1.0,
            "_kg_par_unite": float(kg),
        })
    return pd.DataFrame(rows)


# Duty-free origins for industrial products (EU association agreement, Turkey FTA).
EU_ORIGINS = {"IT", "FR", "DE", "ES", "BE", "NL", "PT", "AT", "PL", "CZ", "RO", "GR", "SE", "DK", "IE", "HU", "SI", "SK", "BG", "HR", "LT", "LV", "EE", "FI", "LU", "MT", "CY"}
DD_FREE_ORIGINS = EU_ORIGINS | {"TR"}

# ---------------------------------------------------------------------------
# Governorates (INS codes and share of companies, modele_donnees.md 3.2)
# ---------------------------------------------------------------------------
GOUVERNORATS = [
    (11, "Tunis", 18.0), (12, "Ariana", 7.3), (13, "Ben Arous", 7.0), (14, "Manouba", 3.4),
    (15, "Nabeul", 7.4), (16, "Zaghouan", 1.3), (17, "Bizerte", 4.4), (21, "Béja", 1.7),
    (22, "Jendouba", 1.8), (23, "Le Kef", 1.2), (24, "Siliana", 1.0), (31, "Sousse", 7.7),
    (32, "Monastir", 5.2), (33, "Mahdia", 2.9), (34, "Sfax", 10.0), (41, "Kairouan", 2.8),
    (42, "Kasserine", 1.7), (43, "Sidi Bouzid", 2.0), (51, "Gabès", 2.9), (52, "Médenine", 4.2),
    (53, "Tataouine", 1.0), (61, "Gafsa", 1.8), (62, "Tozeur", 0.9), (63, "Kébili", 1.0),
]
GOUV_LIBELLE = {c: l for c, l, _ in GOUVERNORATS}

# ---------------------------------------------------------------------------
# Customs offices (synthetic codes) and other code lists
# ---------------------------------------------------------------------------
BUREAUX = {
    "301": ("Radès port", "MARITIME"), "302": ("La Goulette port", "MARITIME"),
    "303": ("Tunis-Carthage aéroport", "AERIEN"), "401": ("Sfax port", "MARITIME"),
    "402": ("Sousse port", "MARITIME"), "501": ("Bizerte port", "MARITIME"),
    "601": ("Ras Jedir", "ROUTIER"), "602": ("Melloula", "ROUTIER"),
}
# Port used by importers of each governorate (maritime traffic).
PORT_BY_GOUV = {34: "401", 33: "402", 31: "402", 32: "402", 41: "402", 17: "501", 22: "501", 21: "501",
                51: "401", 52: "401", 53: "401", 61: "401", 62: "401", 63: "401", 43: "401", 42: "401"}

CODES = [
    ("CIRCUIT", "V", "Vert : bon à enlever automatique", False),
    ("CIRCUIT", "O", "Orange : contrôle documentaire", False),
    ("CIRCUIT", "R", "Rouge : visite physique", False),
    ("TYPE_DECLARATION", "IC100", "Mise à la consommation (code réel non trouvé, placeholder)", True),
    ("TYPE_DECLARATION", "SA530", "Admission temporaire pour perfectionnement actif", False),
    ("TYPE_DECLARATION", "SA531", "Entrepôt industriel", False),
    ("TYPE_DECLARATION", "SE737", "Entrepôt public", False),
    *[("BUREAU", k, v[0], True) for k, v in BUREAUX.items()],
    ("CODE_TAXE", "001", "DD - Droit de douane (base CAF)", False),
    ("CODE_TAXE", "014", "DC - Droit de consommation (non liquidé dans les données synthétiques)", False),
    ("CODE_TAXE", "093", "FODEC", False),
    ("CODE_TAXE", "105", "TVA (base CAF + DD + FODEC)", False),
    ("CODE_TAXE", "473", "RPD - Redevance pour prestations douanières (3 % des droits et taxes)", False),
    ("CODE_TAXE", "480", "AIR - Avance d'impôt sur le revenu (non liquidée dans les données synthétiques)", False),
    ("RESULTAT_CONTROLE", "CONFORME", "Bon à enlever", False),
    ("RESULTAT_CONTROLE", "COMPLEMENT_DEMANDE", "Demande de complément", False),
    ("RESULTAT_CONTROLE", "LITIGE", "Litige", False),
    ("RESULTAT_CONTROLE", "INFRACTION", "Infraction relevée", False),
    ("MODE_TRANSPORT", "MARITIME", "Maritime", False),
    ("MODE_TRANSPORT", "AERIEN", "Aérien", False),
    ("MODE_TRANSPORT", "ROUTIER", "Routier", False),
    ("TYPE_MONTANT", "1", "Honoraires", False), ("TYPE_MONTANT", "2", "Commissions", False),
    ("TYPE_MONTANT", "3", "Courtages", False), ("TYPE_MONTANT", "4", "Loyers", False),
    ("TYPE_MONTANT", "5", "Rémunérations des activités non commerciales", False),
    ("TYPE_MONTANT", "6", "Rémunérations de performance", False),
    ("CODE_ACTE", "0", "Spontané", False), ("CODE_ACTE", "1", "Régularisation", False), ("CODE_ACTE", "2", "Redressement", False),
    ("CODE_DECLARATION", "0", "Spontanée", False), ("CODE_DECLARATION", "1", "Régularisation", False),
    ("CODE_DECLARATION", "2", "Rectificative", False),
    ("STATUT_DEPOT", "DEPOSEE", "Déclaration déposée", False), ("STATUT_DEPOT", "NON_DEPOSEE", "Déclaration non déposée à la date d'extraction", False),
    ("TYPE_ID_BENEFICIAIRE", "1", "Matricule fiscal", False), ("TYPE_ID_BENEFICIAIRE", "2", "Carte d'identité nationale", False),
    ("TYPE_ID_BENEFICIAIRE", "3", "Carte de séjour", False), ("TYPE_ID_BENEFICIAIRE", "4", "Non-résident", False),
    ("CODE_TVA", "A", "Assujetti obligatoire", False), ("CODE_TVA", "B", "Assujetti par option", False),
    ("CODE_TVA", "P", "Assujetti partiel", False), ("CODE_TVA", "F", "Forfaitaire", False), ("CODE_TVA", "N", "Non assujetti", False),
    ("CODE_CATEGORIE", "M", "Personne morale", False), ("CODE_CATEGORIE", "C", "Commerçant ou industriel personne physique", False),
    ("CODE_CATEGORIE", "P", "Profession libérale", False), ("CODE_CATEGORIE", "N", "Employeur non soumis", False),
    ("NATURE_ACHAT", "MARCHE_TUNEPS", "Marché public passé via TUNEPS", False),
    ("NATURE_ACHAT", "CONSULTATION", "Consultation", False), ("NATURE_ACHAT", "BON_COMMANDE", "Bon de commande", False),
    ("TYPE_CONTROLE", "VERIF_PRELIMINAIRE", "Vérification préliminaire (contrôle sur pièces)", False),
    ("TYPE_CONTROLE", "VERIF_APPROFONDIE_PARTIELLE", "Vérification approfondie partielle", False),
    ("TYPE_CONTROLE", "VERIF_APPROFONDIE_TOTALE", "Vérification approfondie totale", False),
    ("ORIGINE_SELECTION", "PROGRAMME_RISQUE", "Programmation par règle statique pondérée (type SAR)", False),
    ("ORIGINE_SELECTION", "RECOUPEMENT", "Recoupement d'informations", False),
    ("ORIGINE_SELECTION", "DENONCIATION", "Dénonciation", False), ("ORIGINE_SELECTION", "ALEATOIRE", "Sélection aléatoire", False),
    ("ISSUE", "SANS_REDRESSEMENT", "Sans redressement", False), ("ISSUE", "ACCORD", "Accord", False),
    ("ISSUE", "TAXATION_OFFICE", "Taxation d'office", False), ("ISSUE", "CONTENTIEUX", "Contentieux", False),
    ("CATEGORIE_RESULTAT", "CONFORME", "Conforme", False), ("CATEGORIE_RESULTAT", "REDRESSEMENT_MINEUR", "Redressement mineur", False),
    ("CATEGORIE_RESULTAT", "FRAUDE_SIGNIFICATIVE", "Fraude significative", False),
    ("CENTRE_GESTION", "DGE", "Direction des grandes entreprises", True), ("CENTRE_GESTION", "DME", "Direction des moyennes entreprises", True),
    ("CENTRE_GESTION", "CRCI", "Centre régional de contrôle des impôts", True),
]

TAUX_RETENUE = [
    ("Honoraires versés aux sociétés et personnes au régime réel", 3.0),
    ("Honoraires, commissions, loyers (autres résidents)", 10.0),
    ("Achats >= 1 000 DT TTC, fournisseur soumis à l'IS au taux de 10 %", 0.5),
    ("Achats >= 1 000 DT TTC, fournisseur soumis à l'IS au taux de 20 %", 1.0),
    ("Achats >= 1 000 DT TTC, fournisseur soumis à l'IS au taux de 35 % ou 40 %", 1.5),
    ("TVA retenue par l'Etat, les collectivités et les entreprises publiques (paiements >= 1 000 DT)", 25.0),
    ("Livraisons e-commerce pour vendeurs sans matricule fiscal", 3.0),
]

# Public buyers (id, label, type, governorate, mission code, mission label)
_MISSIONS = {
    "EQUIPEMENT": ("07", "Equipement, habitat et infrastructure"),
    "SANTE": ("11", "Santé"),
    "EDUCATION": ("09", "Education"),
    "ENS_SUP": ("08", "Enseignement supérieur et recherche scientifique"),
    "INTERIEUR": ("05", "Intérieur et collectivités locales"),
    "TRANSPORT": ("14", "Transport"),
    "AGRICULTURE": ("12", "Agriculture, ressources hydrauliques et pêche"),
    "INDUSTRIE": ("10", "Industrie, mines et énergie"),
    "TECHNO": ("16", "Technologies de la communication"),
    "FINANCES": ("03", "Finances"),
}


def build_public_buyers() -> pd.DataFrame:
    rows = []
    ministries = [
        ("Ministère de l'Equipement et de l'Habitat", "EQUIPEMENT"), ("Ministère de la Santé", "SANTE"),
        ("Ministère de l'Education", "EDUCATION"), ("Ministère de l'Enseignement supérieur et de la Recherche scientifique", "ENS_SUP"),
        ("Ministère de l'Intérieur", "INTERIEUR"), ("Ministère du Transport", "TRANSPORT"),
        ("Ministère de l'Agriculture, des Ressources hydrauliques et de la Pêche", "AGRICULTURE"),
        ("Ministère de l'Industrie, des Mines et de l'Energie", "INDUSTRIE"),
        ("Ministère des Technologies de la communication", "TECHNO"), ("Ministère des Finances", "FINANCES"),
    ]
    for lib, m in ministries:
        rows.append((lib, "MINISTERE", 11, m))
    epa = [
        ("Hôpital Charles Nicolle de Tunis", 11, "SANTE"), ("CHU Habib Bourguiba de Sfax", 34, "SANTE"),
        ("CHU Sahloul de Sousse", 31, "SANTE"), ("CHU Fattouma Bourguiba de Monastir", 32, "SANTE"),
        ("Pharmacie centrale de Tunisie", 11, "SANTE"), ("Université de Tunis El Manar", 11, "ENS_SUP"),
        ("Université de Sfax", 34, "ENS_SUP"), ("Université de Sousse", 31, "ENS_SUP"),
        ("Direction régionale de l'Equipement de Sfax", 34, "EQUIPEMENT"), ("Direction régionale de l'Equipement de Nabeul", 15, "EQUIPEMENT"),
        ("Direction régionale de l'Equipement de Médenine", 52, "EQUIPEMENT"), ("Commissariat régional à l'Education de Tunis 1", 11, "EDUCATION"),
        ("Commissariat régional à l'Education de Sfax 1", 34, "EDUCATION"), ("Agence de réhabilitation et de rénovation urbaine", 11, "EQUIPEMENT"),
    ]
    for lib, g, m in epa:
        rows.append((lib, "EPA", g, m))
    ep = [
        ("Société tunisienne de l'électricité et du gaz", 11, "INDUSTRIE"), ("Société nationale d'exploitation et de distribution des eaux", 11, "AGRICULTURE"),
        ("Office national de l'assainissement", 11, "EQUIPEMENT"), ("Tunisie Autoroutes", 11, "EQUIPEMENT"),
        ("Société nationale des chemins de fer tunisiens", 11, "TRANSPORT"), ("Société des transports de Tunis", 11, "TRANSPORT"),
        ("Compagnie des phosphates de Gafsa", 61, "INDUSTRIE"), ("Office de la marine marchande et des ports", 11, "TRANSPORT"),
        ("Groupe chimique tunisien", 51, "INDUSTRIE"), ("Office des céréales", 11, "AGRICULTURE"),
    ]
    for lib, g, m in ep:
        rows.append((lib, "ENTREPRISE_PUBLIQUE", g, m))
    communes = [(11, "Tunis"), (12, "Ariana"), (13, "Ben Arous"), (14, "Manouba"), (15, "Nabeul"), (15, "Hammamet"),
                (17, "Bizerte"), (21, "Béja"), (22, "Jendouba"), (23, "Le Kef"), (31, "Sousse"), (32, "Monastir"),
                (33, "Mahdia"), (34, "Sfax"), (34, "Sakiet Ezzit"), (41, "Kairouan"), (42, "Kasserine"),
                (43, "Sidi Bouzid"), (51, "Gabès"), (52, "Médenine"), (52, "Djerba Houmt Souk"), (52, "Zarzis"),
                (53, "Tataouine"), (61, "Gafsa"), (62, "Tozeur"), (63, "Kébili")]
    for g, name in communes:
        rows.append((f"Commune de {name}", "COMMUNE", g, "INTERIEUR"))
    out = []
    for i, (lib, typ, g, m) in enumerate(rows, start=1):
        code, mlib = _MISSIONS[m]
        out.append({"id_acheteur_public": f"AP{i:03d}", "libelle": lib, "type": typ, "gouvernorat_code": g,
                    "_mission_code": code, "_mission_libelle": mlib})
    return pd.DataFrame(out)


def build_ref_tables() -> dict[str, pd.DataFrame]:
    ref_nat = pd.DataFrame([{
        "code_nat": n.code, "libelle": n.libelle, "section_nat": n.section, "division": n.code[:2],
        "marge_brute_reference": n.marge, "part_importatrice": n.part_imp,
    } for n in NAT_CLASSES])
    total = sum(w for _, _, w in GOUVERNORATS)
    ref_gouv = pd.DataFrame([{"gouvernorat_code": c, "libelle": l, "poids_entreprises": round(w / total, 4)}
                             for c, l, w in GOUVERNORATS])
    ref_ndp = build_ref_ndp()
    ref_codes = pd.DataFrame(CODES, columns=["domaine", "code", "libelle", "synthetique"])
    ref_taux = pd.DataFrame(TAUX_RETENUE, columns=["nature", "taux"])
    buyers = build_public_buyers()
    return {
        "ref_nat": ref_nat,
        "ref_gouvernorats": ref_gouv,
        "ref_ndp": ref_ndp,
        "ref_codes": ref_codes,
        "ref_taux_retenue": ref_taux,
        "ref_acheteurs_publics": buyers,
    }
