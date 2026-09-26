// Libellés lisibles des signaux et des sources de preuves (mêmes libellés que api/front.py).
export const LIBELLES_SIGNAUX = {
  COH_IMPORT_VS_CA: "Imports en hausse, CA stable",
  COH_CLIENTS_VS_CA: "Achats des clients > CA déclaré",
  COH_ADEB_VS_CA: "Paiements publics > CA déclaré",
  COH_TVA_IMPORT: "TVA import sur-déduite",
  COH_VALEUR_REF: "Valeur en douane anormalement basse",
  CHG_CA: "Rupture du CA déclaré",
  CHG_IMPORTS: "Hausse brutale des imports",
  CHG_TVA_DEDUCTIBLE: "Hausse de la TVA déductible",
  CHG_NOUVEAUX_FOURNISSEURS: "Nouveaux fournisseurs",
  CHG_NOUVELLES_CATEGORIES: "Nouvelles catégories importées",
  CHG_DEPOTS: "Déclarations manquantes ou tardives",
  PAI_MARGE: "Marge très inférieure aux pairs",
  PAI_MAHALANOBIS: "Profil atypique pour le secteur",
  RES_FOURNISSEUR_PARTAGE: "Nouveau fournisseur partagé",
  RES_COQUILLE: "Achats auprès de sociétés coquilles",
  RES_PROXIMITE_REDRESSE: "Proche d'une entité redressée",
  CMB_IMPORT_X_NOUV_FOURN: "Imports concentrés sur des nouveaux fournisseurs",
  CMB_COQUILLE_X_TVA: "TVA déduite sur achats à des coquilles",
  NOUVEAU_SCHEMA: "Nouveau schéma de risque"
};

export const LIBELLES_SOURCES = {
  douane_articles: "Douane (SINDA)", employeur_annexe5: "Annexe V", employeur_annexe2: "Annexe II",
  adeb_paiements: "ADEB", declarations_mensuelles: "Déclaration mensuelle"
};

// Libellé court d'une citation de l'assistant : signal → son nom ; preuve « table:id » → la source
export function libelleCitation(c) {
  if (c.type === "signal") return LIBELLES_SIGNAUX[c.ref] ?? c.ref;
  if (c.type === "preuve") return `Pièce · ${LIBELLES_SOURCES[c.ref.split(":")[0]] ?? c.ref.split(":")[0]}`;
  return c.ref;
}

// Les phrases de B se terminent par « Pièce <table:id> : <montant> » : utile en preuve, illisible en résumé
export function nettoyerFait(texte) {
  if (!texte) return "";
  return texte
    .replace(/\s*Pièce\s*:?\s*[a-z_0-9]+(:[^\s:]+)+(\s*:\s*[^.]*?\d[\d  ,.]*\s*(DT|MD))?\.?/g, "")
    .replace(/\s*Enjeu estimé\s*:\s*[^.]+\.?/g, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}
