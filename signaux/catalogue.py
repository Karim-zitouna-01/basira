"""The immutable 16-signal interface consumed by Member C."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    code: str
    lens: str
    unit: str
    sources: tuple[str, ...]


CATALOGUE = (
    Signal("COH_IMPORT_VS_CA", "COHERENCE", "pts", ("douane", "dgi_declarations")),
    Signal(
        "COH_CLIENTS_VS_CA", "COHERENCE", "x", ("dgi_annexe5", "dgi_annexe2", "dgi_declarations")
    ),
    Signal("COH_ADEB_VS_CA", "COHERENCE", "x", ("adeb", "dgi_declarations")),
    Signal("COH_TVA_IMPORT", "COHERENCE", "x", ("douane", "dgi_declarations")),
    Signal("COH_VALEUR_REF", "COHERENCE", "x", ("douane",)),
    Signal("CHG_CA", "CHANGEMENT", "z", ("dgi_declarations",)),
    Signal("CHG_IMPORTS", "CHANGEMENT", "z", ("douane",)),
    Signal("CHG_TVA_DEDUCTIBLE", "CHANGEMENT", "z", ("dgi_declarations",)),
    Signal("CHG_NOUVEAUX_FOURNISSEURS", "CHANGEMENT", "n", ("douane", "dgi_annexe5")),
    Signal("CHG_NOUVELLES_CATEGORIES", "CHANGEMENT", "n", ("douane",)),
    Signal("CHG_DEPOTS", "CHANGEMENT", "n", ("dgi_declarations",)),
    Signal("PAI_MARGE", "PAIRS", "z", ("douane", "dgi_declarations")),
    Signal("PAI_MAHALANOBIS", "PAIRS", "d", ("douane", "dgi_declarations")),
    Signal("RES_FOURNISSEUR_PARTAGE", "RESEAU", "n", ("graphe", "douane", "dgi_annexe5")),
    Signal("RES_COQUILLE", "RESEAU", "%", ("graphe", "dgi_annexe5")),
    Signal(
        "RES_PROXIMITE_REDRESSE", "RESEAU", "d", ("graphe", "douane", "dgi_annexe5", "dgi_annexe2")
    ),
)
CODES = tuple(signal.code for signal in CATALOGUE)
INDICATORS = ("MARGE", "TVA_DED_SUR_COLL", "CA_PAR_SALARIE", "IMPORTS_SUR_CA")
