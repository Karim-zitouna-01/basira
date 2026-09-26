// « Pourquoi ce score ? » (contrat §6, fiche entreprise) : contributions de chaque signal en points, phrase
// vérifiable, lignes brutes à l'appui (preuves), position face aux pairs, et décision de l'inspecteur.
import { useState } from "react";
import { ChevronDown, ChevronRight, Gavel, Lightbulb, Users } from "lucide-react";
import { chargerPreuves, enregistrerDecision, oublierFiche } from "../lib/donnees.js";
import { fmtCompact, fmtDT, fmtDate } from "../lib/format.js";
import { LIBELLES_SOURCES, nettoyerFait } from "../lib/signaux.js";

const LENTILLES = {
  COHERENCE: ["Cohérence entre sources", "var(--seg-prio)"], CHANGEMENT: ["Changement de comportement", "var(--seg-surv)"],
  PAIRS: ["Comparaison aux pairs", "var(--action)"], RESEAU: ["Réseau", "var(--src-tj)"], COMBINAISON: ["Combinaison", "var(--encre-2)"]
};
const DECISIONS = {
  AUCUNE: "Aucune action", RELANCE: "Relance de conformité", DEMANDE_INFO: "Demande d'information",
  VERIFICATION: "Vérification approfondie", SIGNALEMENT_DOUANE: "Signalement à la douane"
};
const VISIBLES = 4;
const nombre = (v, d = 1) => v.toLocaleString("fr-FR", { maximumFractionDigits: d });
const pts = (v) => `${v >= 0 ? "+" : ""}${nombre(v)}`;
const estMontant = (nom) => /CA par salarié/.test(nom);
const fmtIndicateur = (nom, v) => (v === null || v === undefined ? "—" : estMontant(nom) ? fmtCompact(v) : `${Math.round(v * 100)} %`);

function Carte({ titre, icone: Icone, droite, children, className = "" }) {
  return (
    <section className={`flex min-w-0 flex-col gap-3 rounded-xl border border-bordure bg-carte p-4 ${className}`}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-[13.5px] font-semibold text-encre">
          <Icone size={14} className="text-attenue" aria-hidden="true" />{titre}
        </h2>
        {droite}
      </div>
      {children}
    </section>
  );
}

function Preuves({ mf, code, nb }) {
  const [etat, setEtat] = useState({ ouvert: false, donnees: null, erreur: null });
  const basculer = () => {
    if (!etat.ouvert && !etat.donnees) {
      chargerPreuves(mf, code).then((d) => setEtat({ ouvert: true, donnees: d, erreur: null }), (e) => setEtat({ ouvert: true, donnees: null, erreur: e.message }));
    }
    setEtat((s) => ({ ...s, ouvert: !s.ouvert }));
  };
  const lignes = etat.donnees?.lignes ?? [];
  return (
    <>
      <button type="button" onClick={basculer} aria-expanded={etat.ouvert}
        className="inline-flex shrink-0 items-center gap-0.5 whitespace-nowrap text-[12px] font-semibold text-action-texte hover:underline">
        {etat.ouvert ? <ChevronDown size={13} /> : <ChevronRight size={13} />}Preuves ({nb})
      </button>
      {etat.ouvert && (
        <div className="mt-1 max-h-[240px] w-full basis-full overflow-auto rounded-lg border border-bordure">
          {etat.erreur && <p className="p-3 text-[12px] text-prio-texte">Preuves indisponibles : {etat.erreur}</p>}
          {!etat.erreur && !etat.donnees && <p className="p-3 text-[12px] text-attenue">Chargement…</p>}
          {etat.donnees && (
            <table className="w-full border-collapse text-[12px]">
              <tbody>
                {lignes.map((l) => {
                  const sousEvalue = l.champs?.prix_reference_tnd && l.champs.prix_unitaire_tnd < 0.9 * l.champs.prix_reference_tnd;
                  return (
                    <tr key={`${l.source}:${l.ref}`} className="border-t border-bordure align-top first:border-t-0">
                      <td className="chiffres whitespace-nowrap px-2.5 py-1.5 text-attenue">{fmtDate(l.date)}</td>
                      <td className="px-2.5 py-1.5">
                        <span className="text-encre">{l.libelle}</span>
                        <span className="block text-[11px] text-attenue" title={l.ref}>
                          {LIBELLES_SOURCES[l.source] ?? l.source}
                          {l.champs?.prix_reference_tnd && (
                            <span className={sousEvalue ? "font-semibold text-prio-texte" : ""}>
                              {" "}· prix {fmtDT(l.champs.prix_unitaire_tnd)} pour une référence de {fmtDT(l.champs.prix_reference_tnd)}
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="chiffres whitespace-nowrap px-2.5 py-1.5 text-right text-encre">{l.montant === null ? "—" : fmtDT(l.montant)}</td>
                    </tr>
                  );
                })}
                {!lignes.length && <tr><td className="p-3 text-attenue">Aucune ligne brute rattachée à ce signal.</td></tr>}
              </tbody>
            </table>
          )}
        </div>
      )}
    </>
  );
}

function Contribution({ mf, c, max }) {
  const [lentille, couleur] = LENTILLES[c.lentille] ?? [c.lentille, "var(--attenue)"];
  const fait = nettoyerFait(c.fait_fr);
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 gap-y-1 py-3 first:pt-0 last:pb-0">
      <div className="flex min-w-0 items-baseline gap-2">
        <span className="mt-1 size-2 shrink-0 self-start rounded-full" style={{ background: couleur }} title={lentille} />
        <span className="truncate text-[13px] font-semibold text-encre" title={`${c.libelle} · ${c.code_signal}`}>{c.libelle}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-fond-2 sm:block">
          <span className="block h-full rounded-full" style={{ width: `${(100 * Math.max(0, c.points)) / max}%`, background: couleur }} />
        </span>
        <span className="chiffres w-[62px] text-right text-[13px] font-bold text-encre">{pts(c.points)} pts</span>
      </div>
      <div className="col-span-full flex min-w-0 flex-wrap items-baseline gap-x-3 pl-4">
        {fait && <p className="min-w-0 flex-1 text-[12.5px] leading-snug text-encre-2">{fait}</p>}
        {c.nb_preuves > 0 && <Preuves mf={mf} code={c.code_signal} nb={c.nb_preuves} />}
      </div>
    </li>
  );
}

function Decision({ mf, suggeree, initiales }) {
  const [decision, setDecision] = useState(suggeree);
  const [justification, setJustification] = useState("");
  const [historique, setHistorique] = useState(initiales);
  const [etat, setEtat] = useState({ envoi: false, erreur: null });
  const envoyer = (ev) => {
    ev.preventDefault();
    if (!justification.trim()) return;
    setEtat({ envoi: true, erreur: null });
    enregistrerDecision(mf, { decision, justification: justification.trim(), inspecteur: "demo" }).then(
      (r) => {
        setHistorique((h) => [...h, { id_decision: r.id_decision, date_heure: r.date_heure, decision, justification: justification.trim() }]);
        setJustification("");
        setEtat({ envoi: false, erreur: null });
        oublierFiche(mf);
      },
      (e) => setEtat({ envoi: false, erreur: e.message })
    );
  };
  return (
    <Carte titre="Décision" icone={Gavel}>
      <form onSubmit={envoyer} className="flex flex-col gap-2">
        <label className="sr-only" htmlFor="decision">Décision</label>
        <select id="decision" value={decision} onChange={(e) => setDecision(e.target.value)}
          className="w-full rounded-md border border-bordure bg-carte px-2 py-1.5 text-[13px] text-encre">
          {Object.entries(DECISIONS).map(([k, v]) => <option key={k} value={k}>{v}{k === suggeree ? " (suggérée)" : ""}</option>)}
        </select>
        <label className="sr-only" htmlFor="justification">Justification</label>
        <textarea id="justification" rows={2} value={justification} onChange={(e) => setJustification(e.target.value)} placeholder="Justification (obligatoire)"
          className="resize-none rounded-md border border-bordure bg-carte px-2 py-1.5 text-[13px] text-encre placeholder:text-attenue" />
        <button type="submit" disabled={etat.envoi || !justification.trim()}
          className="rounded-md bg-action px-3 py-1.5 text-[13px] font-semibold text-action-encre disabled:opacity-40">
          {etat.envoi ? "Enregistrement…" : "Enregistrer"}
        </button>
        {etat.erreur && <p className="text-[12px] text-prio-texte">Échec : {etat.erreur}</p>}
      </form>
      <p className="text-[11.5px] text-attenue">Basira propose, l'inspecteur décide.</p>
      {historique.length > 0 && (
        <ol className="flex flex-col gap-1.5 border-t border-bordure pt-2">
          {[...historique].reverse().map((d) => (
            <li key={d.id_decision} className="text-[12px] text-encre-2">
              <span className="chiffres text-attenue">{fmtDate(d.date_heure)}</span> · <strong className="text-encre">{DECISIONS[d.decision] ?? d.decision}</strong>
              <span className="block text-attenue">{d.justification}</span>
            </li>
          ))}
        </ol>
      )}
    </Carte>
  );
}

// Position de l'entreprise dans la plage P10–P90 de ses pairs (bande), médiane (trait), entreprise (point)
function Jauge({ i }) {
  const v = i.entreprise;
  const bornes = [i.p10, i.p90, i.mediane_pairs, v].filter((x) => x !== null && x !== undefined);
  let [lo, hi] = [Math.min(...bornes), Math.max(...bornes)];
  const marge = (hi - lo) * 0.08 || 1;
  [lo, hi] = [lo - marge, hi + marge];
  const x = (val) => `${(100 * (val - lo)) / (hi - lo)}%`;
  const hors = v !== null && v !== undefined && (v < i.p10 || v > i.p90);
  return (
    <li className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-2 text-[12.5px]">
        <span className="truncate text-encre-2">{i.nom}</span>
        <strong className={`chiffres ${hors ? "text-prio-texte" : "text-encre"}`}>{fmtIndicateur(i.nom, v)}</strong>
      </div>
      <div className="relative h-2 rounded-full bg-fond-2" title={`Pairs : médiane ${fmtIndicateur(i.nom, i.mediane_pairs)}, P10–P90 ${fmtIndicateur(i.nom, i.p10)} – ${fmtIndicateur(i.nom, i.p90)}`}>
        {i.p10 !== null && i.p90 !== null && <span className="absolute inset-y-0 rounded-full bg-bordure" style={{ left: x(i.p10), width: `calc(${x(i.p90)} - ${x(i.p10)})` }} />}
        {i.mediane_pairs !== null && <span className="absolute -inset-y-0.5 w-0.5 bg-attenue" style={{ left: x(i.mediane_pairs) }} />}
        {v !== null && v !== undefined && (
          <span className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-carte"
            style={{ left: x(v), background: hors ? "var(--seg-prio)" : "var(--encre)" }} />
        )}
      </div>
    </li>
  );
}

export default function PourquoiScore({ mf, detail }) {
  const [tout, setTout] = useState(false);
  const contributions = detail.contributions ?? [];
  const visibles = tout ? contributions : contributions.slice(0, VISIBLES);
  const max = Math.max(1, ...contributions.map((c) => c.points));
  const somme = contributions.reduce((s, c) => s + c.points, 0);
  const base = detail.score - somme;
  const e = detail.enjeu ?? {};
  const pairs = detail.pairs ?? { indicateurs: [] };
  return (
    <div className="grid gap-4 @4xl:grid-cols-[minmax(0,1fr)_300px]">
      <Carte titre="Pourquoi ce score ?" icone={Lightbulb}
        droite={<span className="chiffres text-[20px] font-bold leading-none text-encre">{nombre(detail.score)}<span className="text-[12px] font-medium text-attenue"> /100</span></span>}>
        <p className="-mt-1 text-[12px] text-attenue">
          Base {nombre(base)} + {nombre(somme)} pts apportés par {contributions.length} signal{contributions.length > 1 ? "aux" : ""}
          {e.estime > 0 && <> · enjeu estimé <strong className="text-encre-2">{fmtCompact(e.estime)}</strong> ({fmtCompact(e.bas)} – {fmtCompact(e.haut)})</>}
        </p>
        <ul className="flex flex-col divide-y divide-bordure">
          {visibles.map((c) => <Contribution key={c.code_signal} mf={mf} c={c} max={max} />)}
          {!contributions.length && <li className="py-2 text-[12.5px] text-attenue">Aucun signal ne contribue au score ce mois-ci.</li>}
        </ul>
        {contributions.length > VISIBLES && (
          <button type="button" onClick={() => setTout((t) => !t)} className="self-start text-[12px] font-semibold text-action-texte">
            {tout ? "Masquer les signaux secondaires" : `Afficher ${contributions.length - VISIBLES} signal${contributions.length - VISIBLES > 1 ? "aux" : ""} secondaire${contributions.length - VISIBLES > 1 ? "s" : ""}`}
          </button>
        )}
      </Carte>
      <div className="grid content-start gap-4 @2xl:grid-cols-2 @4xl:grid-cols-1">
        <Decision mf={mf} suggeree={detail.action_suggeree} initiales={detail.decisions ?? []} />
        {pairs.indicateurs.length > 0 && (
          <Carte titre="Face à ses pairs" icone={Users} droite={<span className="text-[11.5px] text-attenue">{pairs.nb_pairs} entreprises</span>}>
            <ul className="flex flex-col gap-3">
              {pairs.indicateurs.map((i) => <Jauge key={i.nom} i={i} />)}
            </ul>
            <p className="flex items-center gap-3 text-[11px] text-attenue">
              <span className="inline-flex items-center gap-1"><span className="h-1.5 w-4 rounded-full bg-bordure" />P10–P90</span>
              <span className="inline-flex items-center gap-1"><span className="h-2.5 w-0.5 bg-attenue" />médiane</span>
              <span className="inline-flex items-center gap-1"><span className="size-2 rounded-full bg-encre" />entreprise</span>
            </p>
          </Carte>
        )}
      </div>
    </div>
  );
}
