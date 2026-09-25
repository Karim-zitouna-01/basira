"""Global constants: time window, calibration targets, scenario counts, hero cases."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

SEED = 2026
N_DEFAULT = 5250

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------
# The world is simulated from 2023-01 so that the fiscal year 2023 (IS, annex V)
# is complete, but raw event tables are only published from 2023-09 on.
SIM_START = "2023-01"
WINDOW_START = "2023-09"
WINDOW_END = "2026-08"
# Snapshot date of the extraction: the declaration of 2026-08 is due 2026-09-28,
# so filing dates may run until this date.
SNAPSHOT_DATE = pd.Timestamp("2026-09-30")
WINDOW_START_DATE = pd.Timestamp("2023-09-01")
WINDOW_END_DATE = pd.Timestamp("2026-08-31")

SIM_MONTHS: list[str] = [str(p) for p in pd.period_range(SIM_START, WINDOW_END, freq="M")]
T = len(SIM_MONTHS)  # 44
OUT0 = SIM_MONTHS.index(WINDOW_START)  # 8: first published month
METRIC_START = "2024-09"
METRIC_T0 = SIM_MONTHS.index(METRIC_START)  # 20
EXERCICES = [2023, 2024, 2025]

# Control history window
CONTROL_AVIS_START = pd.Timestamp("2024-10-01")
CONTROL_AVIS_END = pd.Timestamp("2026-06-30")

# Foreign-supplier novelty is only meaningful after 12 months of observation.
NOVELTY_BURN_IN = SIM_MONTHS.index("2024-09")


def month_index(mois: str) -> int:
    return SIM_MONTHS.index(mois)


def year_of(t: int) -> int:
    return int(SIM_MONTHS[t][:4])


def latest_exercice_available(t: int) -> int:
    """Employer declaration of year N is filed by 28 Feb N+1, usable from March N+1."""
    y, m = int(SIM_MONTHS[t][:4]), int(SIM_MONTHS[t][5:7])
    return y - 1 if m >= 3 else y - 2


# ---------------------------------------------------------------------------
# Population calibration (modele_donnees.md 3.1 / 3.2)
# ---------------------------------------------------------------------------
SIZE_CLASSES = ["0-2", "3-9", "10-49", "50-99", "100+"]
SIZE_WEIGHTS = [0.45, 0.30, 0.18, 0.04, 0.03]
# Median annual turnover (TND) per size class, before the sector multiplier.
SIZE_CA_MEDIAN = {"0-2": 300_000, "3-9": 700_000, "10-49": 1_500_000, "50-99": 5_000_000, "100+": 15_000_000}

FORME_WEIGHTS = {"SARL": 0.73, "SUARL": 0.23, "SA": 0.04}

CIRCUIT_WEIGHTS = {"V": 0.70, "O": 0.22, "R": 0.08}
CONTROL_RATE_PER_YEAR = 0.03
CONTROL_ORIGINS = {"PROGRAMME_RISQUE": 0.55, "RECOUPEMENT": 0.20, "DENONCIATION": 0.10, "ALEATOIRE": 0.15}

LATE_RATE = 0.06
MISSING_RATE = 0.02

# ---------------------------------------------------------------------------
# Scenario counts at N = 5250 (modele_donnees.md 3.3), with minimums for small samples
# ---------------------------------------------------------------------------
SCENARIO_COUNTS = {
    "A": (80, 5),            # under-declared turnover; 1/3 in groups of 4-6 importers
    "B_NETWORKS": (10, 1),   # fake-invoice rings (4-6 clients + 1-2 shells each)
    "C": (50, 2),            # customs undervaluation
    "D": (30, 2),            # undeclared public revenue
    "E": (25, 2),            # dormant then active
    "DORMANT": (75, 2),      # dormant, never reactivated (no scenario)
    "F": (50, 2),            # margin compression
    "CROISSANCE_LEGITIME": (100, 3),
    "CITOYEN_MODELE": (400, 8),
    "MICRO_SANS_SALARIE": (135, 3),  # recent companies with no staff, honest (shell look-alikes)
}

SCENARIO_START_RANGE = ("2025-03", "2026-06")


def scaled_count(key: str, n: int) -> int:
    full, minimum = SCENARIO_COUNTS[key]
    return max(minimum, int(round(full * n / N_DEFAULT)))


# ---------------------------------------------------------------------------
# Hero cases (contrat_integration.md section 7, modele_donnees.md 3.5)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Hero:
    mf: str
    raison_sociale: str
    forme: str
    code_nat: str
    gouvernorat: int
    scenario: str
    start: str | None
    effectif: int
    date_debut: str
    ca_annuel: float
    centre: str


HEROES = [
    Hero("1000001BAM000", "Alpha SARL", "SARL", "46.69", 34, "A", "2026-06", 23, "2014-03-01", 1_150_000, "CRCI"),
    Hero("1000002CAM000", "Beta Import SUARL", "SUARL", "46.43", 13, "C", "2026-01", 8, "2017-09-15", 2_400_000, "CRCI"),
    Hero("1000003DAM000", "Gamma Travaux SA", "SA", "42.11", 11, "D", "2025-06", 35, "2009-05-04", 650_000, "CRCI"),
    Hero("1000004EAM000", "Delta Trade SARL", "SARL", "46.90", 52, "E", "2026-03", 1, "2016-02-10", 0, "CRCI"),
    Hero("1000005FAM000", "Epsilon Textile SARL", "SARL", "14.13", 32, "F", "2025-09", 40, "2011-11-21", 2_600_000, "DME"),
    Hero("1000006GAM000", "Zeta Industries SA", "SA", "25.11", 31, "CROISSANCE_LEGITIME", "2026-02", 85, "2006-06-12", 7_500_000, "DME"),
    Hero("1000007HAM000", "Eta Pharma SA", "SA", "46.46", 12, "CITOYEN_MODELE", None, 120, "2002-01-07", 28_000_000, "DGE"),
    Hero("1000008JAM000", "Omega Négoce SUARL", "SUARL", "46.90", 11, "COQUILLE", "2025-03", 0, "2024-11-04", 0, "CRCI"),
]
HERO_MFS = {h.mf for h in HEROES}
ALPHA_MF = "1000001BAM000"
OMEGA_MF = "1000008JAM000"
ALPHA_SUPPLIER = "FE00231"
ALPHA_SUPPLIER_NAME = "Shenzhen Tools Co."  # label used in the contract mocks
# Second member of Alpha's group, named in the contract's network example.
KAPPA = ("1000311KAM000", "Kappa Equipements SARL")
ALPHA_GROUP_SIZE = 5  # Alpha + 4 other A importers
OMEGA_CLIENTS = 5
