// Dossiers suivis (favoris) et entreprises consultées récemment, mémorisés dans le navigateur.
import { useSyncExternalStore } from "react";

const CLE = "suivis-inspecteur";
const DEFAUT = { favoris: ["1000001BAM000", "1000008JAM000"], recents: [] };
let etat = lire();
const abonnes = new Set();

function lire() {
  try { return { ...DEFAUT, ...JSON.parse(localStorage.getItem(CLE) ?? "{}") }; } catch { return DEFAUT; }
}
function ecrire(suivant) {
  etat = suivant;
  try { localStorage.setItem(CLE, JSON.stringify(etat)); } catch { /* stockage indisponible */ }
  abonnes.forEach((f) => f());
}

export function basculerFavori(mf) {
  const favoris = etat.favoris.includes(mf) ? etat.favoris.filter((x) => x !== mf) : [...etat.favoris, mf];
  ecrire({ ...etat, favoris });
}
export function noterConsultation(mf) {
  ecrire({ ...etat, recents: [mf, ...etat.recents.filter((x) => x !== mf)].slice(0, 5) });
}
export function useSuivis() {
  return useSyncExternalStore((f) => { abonnes.add(f); return () => abonnes.delete(f); }, () => etat);
}
