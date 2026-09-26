// Palettes candidates (voir src/index.css). Le choix final supprimera le sélecteur.
import { modeApi } from "./donnees.js";
export const PALETTES = [
  { id: "A", nom: "A · Ardoise" },
  { id: "B", nom: "B · Bleu République" },
  { id: "C", nom: "C · Pierre & Sable" },
  { id: "D", nom: "D · Contrat Basira" }
];

export const SEGMENTS = {
  PRIORITAIRE: { libelle: "Haut Risque", jeton: "prio" },
  SURVEILLANCE: { libelle: "Anomalie Émergente", jeton: "surv" },
  NORMAL: { libelle: "Normal", jeton: "norm" },
  CONFIANCE: { libelle: "Conforme (OEA)", jeton: "conf" }
};
export const ORDRE_SEGMENTS = ["PRIORITAIRE", "SURVEILLANCE", "NORMAL", "CONFIANCE"];

// API : sources réellement simulées (douane, paiements publics, annexe V des déclarations employeur)
export const SOURCES = modeApi
  ? [
      { id: "SINDA", libelle: "Système SINDA", jeton: "--src-sinda" },
      { id: "ADEB", libelle: "Application ADEB", jeton: "--src-adeb" },
      { id: "ANNEXE V", libelle: "Annexe V (achats déclarés par les clients et auprès des fournisseurs)", jeton: "--src-tj" }
    ]
  : [
      { id: "SINDA", libelle: "Système SINDA", jeton: "--src-sinda" },
      { id: "ADEB", libelle: "Application ADEB", jeton: "--src-adeb" },
      { id: "TJ", libelle: "Plateforme TJ", jeton: "--src-tj" },
      { id: "RAFIK", libelle: "RAFIK", jeton: "--src-rafik" }
    ];

// Lit la valeur courante d'un jeton CSS (les graphiques D3/DC en ont besoin en JS)
export const jeton = (nom) => getComputedStyle(document.documentElement).getPropertyValue(nom).trim();
export const couleurSegment = (segment) => jeton(`--seg-${SEGMENTS[segment]?.jeton ?? "norm"}`);
