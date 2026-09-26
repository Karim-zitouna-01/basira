// Réseau de contreparties en flux d'argent : qui paie l'entreprise (à gauche) → l'entreprise → qui elle paie (à droite).
// Chaque flèche suit le paiement et porte le nom de la relation ; au-delà de quelques contreparties par côté, le reste
// est regroupé (« + N autres ») pour rester lisible. Les autres entreprises du portefeuille liées aux mêmes contreparties
// sont listées sous le graphe plutôt que dessinées.
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { entreprisesLiees } from "../lib/donnees.js";
import { SEGMENTS } from "../lib/palettes.js";
import { fmtCompact, fmtDate, fmtDT } from "../lib/format.js";

const PAR_COTE = 6;          // contreparties visibles par côté avant regroupement
const H_CARTE = 42;
const PAS = 54;              // pas vertical entre deux cartes
const ENTRANTS = new Set(["Client", "Client (honoraires)", "Acheteur public"]);
const EST_MF = /^\d{7}[A-Z]{3}\d{3}$/;
const couleurSegment = (s) => `var(--seg-${SEGMENTS[s]?.jeton ?? "norm"})`;
// Libellé court posé sur la flèche (le détail est dans l'infobulle de la carte)
const COURT = {
  "Achat · annexe V": "Achat", "Vente · annexe V": "Vente", "Paiement public": "Paiement", "Honoraires reçus": "Honoraires",
  "Autres flux": "Autres", "Fournisseur étranger": "Import", "Fournisseur local": "Achat", Client: "Vente", "Acheteur public": "Paiement"
};
const LIEES_MAX = 3;   // contreparties listées sous le graphe
const CHIPS_MAX = 2;   // entreprises affichées par contrepartie (le reste en « +N »)

// Texte tronqué à la largeur disponible (approximation : 6,1 px par caractère à 12 px)
const couper = (t, largeur, px = 6.1) => {
  const n = Math.max(4, Math.floor(largeur / px));
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
};

// Nom de l'entreprise centrale sur deux lignes au plus (coupure aux espaces)
function deuxLignes(t, n) {
  if (t.length <= n) return [t];
  const mots = t.split(" ");
  let l1 = "";
  while (mots.length && (l1 + " " + mots[0]).trim().length <= n) l1 = `${l1} ${mots.shift()}`.trim();
  const reste = mots.join(" ");
  return [l1 || t.slice(0, n), reste.length > n ? `${reste.slice(0, n - 1)}…` : reste].filter(Boolean);
}

// Point et tangente d'une courbe de Bézier cubique (pour poser les libellés sur les flèches)
const bezier = (p0, p1, p2, p3, t) => {
  const u = 1 - t;
  return [0, 1].map((k) => u ** 3 * p0[k] + 3 * u * u * t * p1[k] + 3 * u * t * t * p2[k] + t ** 3 * p3[k]);
};

function preparer(entreprise, montants) {
  const noeuds = entreprise.network_nodes.map((n) => {
    const selection = montants.get(n.id) ?? 0;
    return {
      ...n,
      sens: n.sens ?? (ENTRANTS.has(n.type) ? "entrant" : "sortant"),
      relation: n.relation ?? n.type,
      montant: selection || n.montant_dt || 0,
      horsSelection: !selection
    };
  });
  const tri = (a, b) => (b.risk_flag - a.risk_flag) || (a.horsSelection - b.horsSelection) || (b.montant - a.montant);
  return {
    gauche: noeuds.filter((n) => n.sens === "entrant").sort(tri),
    droite: noeuds.filter((n) => n.sens === "sortant").sort(tri)
  };
}

function Carte({ n, x, y, l, selectionnee, onClic, onOuvrir }) {
  const accent = n.risk_flag ? "var(--seg-prio)" : n.segment ? couleurSegment(n.segment) : "var(--bordure)";
  const titre = `${n.label} · ${n.type}\n${n.relation}${n.montant ? ` · ${fmtDT(n.montant)}` : ""}${n.depuis ? `\nDepuis le ${fmtDate(n.depuis)}` : ""}${n.risk_flag ? "\n⚠ contrepartie signalée" : ""}`;
  const ouvrable = EST_MF.test(n.id);
  const lTexte = l - (ouvrable ? 34 : 20);
  return (
    <g transform={`translate(${x},${y - H_CARTE / 2})`} opacity={n.horsSelection && !n.agregat ? 0.55 : 1}
      className="cursor-pointer" onClick={onClic} role="button" tabIndex={0}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onClic()}>
      <title>{titre}</title>
      <rect width={l} height={H_CARTE} rx={8} fill="var(--carte)"
        stroke={selectionnee ? "var(--encre)" : n.risk_flag ? "var(--seg-prio)" : "var(--bordure)"} strokeWidth={selectionnee ? 2 : 1} />
      <rect x={0} y={0} width={4} height={H_CARTE} rx={2} fill={accent} />
      <text x={12} y={17} fontSize={12} fontWeight={600} fill="var(--encre)">
        {n.risk_flag && <tspan fill="var(--seg-prio-texte)">⚠ </tspan>}
        {couper(n.label, lTexte - (n.risk_flag ? 14 : 0))}
      </text>
      <text x={12} y={32} fontSize={10.5} fill="var(--attenue)">
        {n.montant ? fmtCompact(n.montant) : "—"}
        {n.nouvelle && !n.agregat && <tspan fill="var(--seg-surv-texte)" fontWeight={600}> · nouvelle relation</tspan>}
      </text>
      {ouvrable && (
        <g transform={`translate(${l - 22},${H_CARTE / 2 - 8})`} onClick={(e) => { e.stopPropagation(); onOuvrir(n.id); }}>
          <title>Ouvrir la fiche de {n.label}</title>
          <rect width={16} height={16} rx={4} fill="var(--fond-2)" />
          <path d="M5.5 10.5 L10.5 5.5 M6.5 5.5 H10.5 V9.5" stroke="var(--encre-2)" strokeWidth={1.4} fill="none" strokeLinecap="round" />
        </g>
      )}
    </g>
  );
}

export default function GrapheReseau({ entreprise, montants, contrepartiesFiltrees, onClicContrepartie }) {
  const navigate = useNavigate();
  const conteneur = useRef(null);
  const [L, setL] = useState(720);
  const [tout, setTout] = useState({ gauche: false, droite: false });
  useEffect(() => {
    const el = conteneur.current;
    const obs = new ResizeObserver(() => { const l = Math.round(el.clientWidth); if (l && Math.abs(l - L) > 10) setL(l); });
    obs.observe(el);
    return () => obs.disconnect();
  }, [L]);
  useEffect(() => setTout({ gauche: false, droite: false }), [entreprise.mf]);

  const { gauche, droite } = useMemo(() => preparer(entreprise, montants), [entreprise, montants]);

  // Au-delà de PAR_COTE, les plus petites contreparties sont regroupées en une carte cliquable
  const colonne = (liste, cote) => {
    if (tout[cote] || liste.length <= PAR_COTE + 1) return liste;
    const reste = liste.slice(PAR_COTE);
    return [...liste.slice(0, PAR_COTE), {
      id: `__autres_${cote}`, agregat: true, label: `+ ${reste.length} autres contreparties`, type: "", relation: "Autres flux",
      montant: reste.reduce((s, n) => s + n.montant, 0), sens: cote === "gauche" ? "entrant" : "sortant"
    }];
  };
  const G = colonne(gauche, "gauche");
  const D = colonne(droite, "droite");

  // cartes assez étroites pour laisser aux libellés des flèches un couloir entre les colonnes
  const cw = Math.round(Math.min(210, Math.max(140, L * 0.25)));
  const lc = 150;
  const lignes = Math.max(G.length, D.length, 1);
  const H = Math.max(160, lignes * PAS + 24);
  const yc = H / 2;
  const xc = L / 2 - lc / 2;
  const yDe = (i, n) => yc + (i - (n - 1) / 2) * PAS;
  const max = Math.max(1, ...[...G, ...D].map((n) => n.montant));
  const epaisseur = (m) => 1.2 + 3.3 * Math.sqrt(m / max);
  const segCentre = entreprise.segment;
  const nomCentre = deuxLignes(entreprise.company_name, Math.floor((lc - 16) / 6.9));
  const hc = 52 + nomCentre.length * 16;

  const clic = (n) => (n.agregat ? setTout((t) => ({ ...t, [n.sens === "entrant" ? "gauche" : "droite"]: true })) : onClicContrepartie(n.label));

  const fleche = (n, i, liste, cote) => {
    const y = yDe(i, liste.length);
    // les flèches arrivent réparties le long du bord de l'entreprise, pas en un seul point
    const yEnt = yc + (i - (liste.length - 1) / 2) * Math.min(7, 44 / Math.max(1, liste.length - 1));
    // gauche : contrepartie → entreprise ; droite : entreprise → contrepartie (sens du paiement)
    const [p0, p3] = cote === "gauche" ? [[cw, y], [xc - 3, yEnt]] : [[xc + lc, yEnt], [L - cw - 3, y]];
    const dx = (p3[0] - p0[0]) * 0.45;
    const p1 = [p0[0] + dx, p0[1]], p2 = [p3[0] - dx, p3[1]];
    const [lx, ly] = bezier(p0, p1, p2, p3, cote === "gauche" ? 0.28 : 0.72);
    const couleur = n.risk_flag ? "var(--seg-prio)" : "var(--attenue)";
    const libelle = COURT[n.relation] ?? couper(n.relation, 70, 5.6);
    const lg = libelle.length * 5.6 + 12;
    return (
      <g key={`f-${n.id}`} opacity={n.horsSelection && !n.agregat ? 0.45 : 1}>
        <path d={`M${p0[0]},${p0[1]} C${p1[0]},${p1[1]} ${p2[0]},${p2[1]} ${p3[0]},${p3[1]}`} fill="none" stroke={couleur}
          strokeOpacity={n.risk_flag ? 0.85 : 0.5} strokeWidth={epaisseur(n.montant)} strokeDasharray={n.nouvelle ? "5 4" : undefined}
          markerEnd={`url(#pointe-${n.risk_flag ? "prio" : "neutre"})`} />
        <g transform={`translate(${lx - lg / 2},${ly - 9})`} pointerEvents="none">
          <rect width={lg} height={18} rx={9} fill="var(--carte)" stroke={n.risk_flag ? "var(--seg-prio)" : "var(--bordure)"} />
          <text x={lg / 2} y={12.5} textAnchor="middle" fontSize={10} fontWeight={600}
            fill={n.risk_flag ? "var(--seg-prio-texte)" : "var(--encre-2)"}>{libelle}</text>
        </g>
      </g>
    );
  };

  // Autres entreprises du portefeuille liées aux mêmes contreparties (API : calculé côté serveur)
  const liees = useMemo(() => {
    const visibles = [...gauche, ...droite].filter((n) => n.risk_flag).concat([...gauche, ...droite].filter((n) => !n.risk_flag));
    return visibles.map((n) => ({
      n,
      autres: (entreprise.liens_portefeuille ? entreprise.liens_portefeuille[n.id] ?? [] : entreprisesLiees(n.id, entreprise.mf))
        .filter((o) => o.mf !== n.id)
    })).filter((x) => x.autres.length).slice(0, LIEES_MAX);
  }, [entreprise, gauche, droite]);

  const vide = !gauche.length && !droite.length;
  return (
    <div ref={conteneur} className="flex flex-col gap-3">
      <div className="grid grid-cols-3 text-[11px] font-semibold uppercase tracking-[0.05em] text-attenue">
        <span>Paient l'entreprise</span>
        <span className="flex items-center justify-center gap-1">Flux d'argent <ArrowRight size={12} aria-hidden="true" /></span>
        <span className="text-right">Payés par l'entreprise</span>
      </div>
      {vide ? (
        <p className="py-8 text-center text-[12.5px] text-attenue">Aucune contrepartie sur la période.</p>
      ) : (
        <svg viewBox={`0 0 ${L} ${H}`} width={L} height={H} role="img" aria-label={`Flux entre ${entreprise.company_name} et ses contreparties`} className="max-w-full">
          <defs>
            {[["prio", "var(--seg-prio)"], ["neutre", "var(--attenue)"]].map(([id, c]) => (
              <marker key={id} id={`pointe-${id}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse" markerUnits="userSpaceOnUse">
                <path d="M0,0 L10,5 L0,10 z" fill={c} />
              </marker>
            ))}
          </defs>
          {!G.length && <text x={cw / 2} y={yc} textAnchor="middle" fontSize={11.5} fill="var(--attenue)">Aucun client déclaré</text>}
          {!D.length && <text x={L - cw / 2} y={yc} textAnchor="middle" fontSize={11.5} fill="var(--attenue)">Aucun fournisseur déclaré</text>}
          {G.map((n, i) => fleche(n, i, G, "gauche"))}
          {D.map((n, i) => fleche(n, i, D, "droite"))}
          <g transform={`translate(${xc},${yc - hc / 2})`}>
            <title>{entreprise.company_name}</title>
            <rect width={lc} height={hc} rx={10} fill="var(--carte)" stroke={couleurSegment(segCentre)} strokeWidth={2} />
            {nomCentre.map((ligne, k) => (
              <text key={k} x={lc / 2} y={22 + k * 16} textAnchor="middle" fontSize={12.5} fontWeight={700} fill="var(--encre)">{ligne}</text>
            ))}
            <text x={lc / 2} y={hc - 28} textAnchor="middle" fontSize={11} fill="var(--attenue)">score {entreprise.current_risk_score}/100</text>
            <text x={lc / 2} y={hc - 12} textAnchor="middle" fontSize={11} fontWeight={600} fill={couleurSegment(segCentre)}>{SEGMENTS[segCentre]?.libelle}</text>
          </g>
          {G.map((n, i) => (
            <Carte key={n.id} n={n} x={0} y={yDe(i, G.length)} l={cw} selectionnee={contrepartiesFiltrees.includes(n.label)}
              onClic={() => clic(n)} onOuvrir={(mf) => navigate(`/entreprise/${mf}`)} />
          ))}
          {D.map((n, i) => (
            <Carte key={n.id} n={n} x={L - cw} y={yDe(i, D.length)} l={cw} selectionnee={contrepartiesFiltrees.includes(n.label)}
              onClic={() => clic(n)} onOuvrir={(mf) => navigate(`/entreprise/${mf}`)} />
          ))}
        </svg>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-attenue">
        <span className="inline-flex items-center gap-1.5"><svg width="20" height="8" aria-hidden="true"><line x1="0" y1="4" x2="14" y2="4" stroke="var(--attenue)" strokeWidth="2" /><path d="M13,0 L20,4 L13,8 z" fill="var(--attenue)" /></svg>sens du paiement, épaisseur = montant</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm border-2" style={{ borderColor: "var(--seg-prio)" }} />contrepartie signalée</span>
        <span className="inline-flex items-center gap-1.5"><svg width="20" height="6" aria-hidden="true"><line x1="0" y1="3" x2="20" y2="3" stroke="var(--attenue)" strokeWidth="2" strokeDasharray="5 3" /></svg>relation nouvelle (moins de 18 mois)</span>
        {(tout.gauche || tout.droite) && (
          <button type="button" onClick={() => setTout({ gauche: false, droite: false })} className="font-semibold text-action-texte">Regrouper les petites contreparties</button>
        )}
      </div>

      {liees.length > 0 && (
        <div className="flex flex-col gap-1.5 border-t border-bordure pt-3">
          <span className="text-[11px] font-semibold uppercase tracking-[0.05em] text-attenue">Mêmes contreparties dans le portefeuille</span>
          {liees.map(({ n, autres }) => (
            <div key={n.id} className="flex min-w-0 items-center gap-1.5 overflow-hidden text-[12px]">
              <span className={`mr-1 max-w-[190px] shrink-0 truncate font-medium ${n.risk_flag ? "text-prio-texte" : "text-encre-2"}`} title={n.label}>{n.risk_flag && "⚠ "}{n.label}</span>
              {autres.length > CHIPS_MAX && <span className="order-last shrink-0 text-[11.5px] text-attenue">+{autres.length - CHIPS_MAX}</span>}
              {autres.slice(0, CHIPS_MAX).map((o) => (
                <button key={o.mf} type="button" onClick={() => navigate(`/entreprise/${o.mf}`)}
                  title={o.company_name}
                  className="inline-flex min-w-0 max-w-[200px] items-center gap-1 rounded-full border border-bordure px-2 py-0.5 text-[11.5px] text-encre-2 hover:border-attenue hover:text-encre">
                  <span className="size-1.5 shrink-0 rounded-full" style={{ background: couleurSegment(o.segment) }} />
                  <span className="truncate">{o.company_name}</span><ArrowUpRight size={11} className="shrink-0" aria-hidden="true" />
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
