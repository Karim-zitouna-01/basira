// Formats d'affichage : montants « 420 000 DT » / « 3,2 MD », dates JJ/MM/AAAA
const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const espace = (s) => s.replace(/[  ]/g, " ");

export const fmtDT = (v) => espace(nombre.format(v ?? 0)) + " DT";

export function fmtCompact(v) {
  const a = Math.abs(v ?? 0);
  if (a >= 1e6) return espace((v / 1e6).toLocaleString("fr-FR", { maximumFractionDigits: 1 })) + " MD";
  if (a >= 1e3) return espace((v / 1e3).toLocaleString("fr-FR", { maximumFractionDigits: 0 })) + " k DT";
  return fmtDT(v);
}

export const fmtDate = (iso) => (iso ? iso.slice(0, 10).split("-").reverse().join("/") : "—");

const MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
export const fmtMois = (d) => `${MOIS_COURTS[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`;
export const fmtMoisIso = (m) => fmtMois(new Date(`${m}-01T00:00:00`));
