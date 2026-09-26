// « Pourquoi ce score ? » (contrat §6, fiche entreprise) : contributions de chaque signal en points, phrase
// vérifiable, lignes brutes à l'appui (preuves), position face aux pairs, et décision de l'inspecteur.
import { useState } from "react";
import { ChevronDown, ChevronRight, FileSearch, Gavel, Lightbulb, Users } from "lucide-react";
import { chargerPreuves, enregistrerDecision, oublierFiche } from "../lib/donnees.js";
import { fmtCompact, fmtDT, fmtDate } from "../lib/format.js";

const LENTILLES = {
  COHERENCE: "Cohérence entre sources", CHANGEMENT: "Changement de comportement", PAIRS: "Comparaison aux pairs",
  RESEAU: "Réseau", COMBINAISON: "Combinaison"
};
const DECISIONS = {
  AUCUNE: "Aucune action", RELANCE: "Relance de conformité", DEMANDE_INFO: "Demande d'information",
  VERIFICATION: "Vérification approfondie", SIGNALEMENT_DOUANE: "Signalement à la douane"
};
const SOURCES = {
  douane_articles: "Douane (SINDA)", employeur_annexe5: "Annexe V", employeur_annexe2: "Annexe II",
  adeb_paiements: "ADEB", declarations_mensuelles: "Déclaration mensuelle"
};
const pts = (v) => `${v >= 0 ? "+" : ""}${v.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}`;
const pct = (v) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)} %`);
const valeurIndicateur = (nom, v) => (v === null || v === undefined ? "—" : /CA par salarié/.test(nom) ? fmtCompact(v) : pct(v));

function Section({ titre, icone: Icone, children, className = "" }) {
  return (
    <section className={`flex min-w-0 flex-col gap-3 rounded-xl border border-bordure bg-carte p-4 ${className}`}>
      <h2 className="flex items-center gap-2 text-[13.5px] font-semibold text-encre">
        <Icone size={14} className="text-attenue" aria-hidden="true" />{titre}
      </h2>
      {children}
    </section>
  );
}

function Preuves({ mf, code }) {
  const [etat, setEtat] = useState({ ouvert: false, donnees: null, erreur: null });
  const basculer = () => {
    if (!etat.ouvert && !etat.donnees) {
      chargerPreuves(mf, code).then((d) => setEtat({ ouvert: true, donnees: d, erreur: null }), (e) => setEtat({ ouvert: true, donnees: null, erreur: e.message }));
    }
    setEtat((s) => ({ ...s, ouvert: !s.ouvert }));
  };
  const lignes = etat.donnees?.lignes ?? [];
  return (
    <div className="flex flex-col gap-1.5">
      <button type="button" onClick={basculer} aria-expanded={etat.ouvert}
        className="inline-flex w-fit items-center gap-1 text-[12.5px] font-semibold text-action-texte hover:underline">
        {etat.ouvert ? <ChevronDown size={13} /> : <ChevronRight size={13} />}Voir les preuves
      </button>
      {etat.ouvert && (
        <div className="max-h-[260px] overflow-auto rounded-lg border border-bordure">
          {etat.erreur && <p className="p-3 text-[12.5px] text-prio-texte">Preuves indisponibles : {etat.erreur}</p>}
          {!etat.erreur && !etat.donnees && <p className="p-3 text-[12.5px] text-attenue">Chargement…</p>}
          {etat.donnees && (
            <table className="w-full border-collapse text-[12px]">
              <thead className="sticky top-0 bg-fond text-left text-attenue">
                <tr>{["Date", "Source", "Pièce", "Montant"].map((t) => <th key={t} className="px-2 py-1.5 font-medium">{t}</th>)}</tr>
              </thead>
              <tbody>
                {lignes.map((l) => (
                  <tr key={`${l.source}:${l.ref}`} className="border-t border-bordure align-top">
                    <td className="chiffres whitespace-nowrap px-2 py-1.5 text-encre-2">{fmtDate(l.date)}</td>
                    <td className="whitespace-nowrap px-2 py-1.5 text-encre-2">{SOURCES[l.source] ?? l.source}</td>
                    <td className="px-2 py-1.5 text-encre">
                      {l.libelle}
                      <span className="block font-mono text-[10.5px] text-attenue">{l.ref}</span>
                      {l.champs?.prix_reference_tnd && (
                        <span className={`block text-[11px] ${l.champs.prix_unitaire_tnd < 0.9 * l.champs.prix_reference_tnd ? "font-semibold text-prio-texte" : "text-attenue"}`}>
                          Prix unitaire {fmtDT(l.champs.prix_unitaire_tnd)} pour une référence de {fmtDT(l.champs.prix_reference_tnd)}
                        </span>
                      )}
                    </td>
                    <td className="chiffres whitespace-nowrap px-2 py-1.5 text-right text-encre">{l.montant === null ? "—" : fmtDT(l.montant)}</td>
                  </tr>
                ))}
                {!lignes.length && <tr><td colSpan={4} className="p-3 text-attenue">Aucune ligne brute rattachée à ce signal.</td></tr>}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
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
    <Section titre="Décision de l'inspecteur" icone={Gavel}>
      <p className="-mt-1 text-[12px] text-attenue">Action suggérée : <strong className="text-encre">{DECISIONS[suggeree]}</strong>. Basira propose, l'inspecteur décide.</p>
      <form onSubmit={envoyer} className="flex flex-col gap-2">
        <label className="flex flex-col gap-1 text-[12.5px] text-encre-2">
          Décision
          <select value={decision} onChange={(e) => setDecision(e.target.value)} className="rounded-md border border-bordure bg-carte px-2 py-1.5 text-[13px] text-encre">
            {Object.entries(DECISIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12.5px] text-encre-2">
          Justification
          <textarea rows={2} value={justification} onChange={(e) => setJustification(e.target.value)} placeholder="Motif de la décision (obligatoire)"
            className="resize-none rounded-md border border-bordure bg-carte px-2 py-1.5 text-[13px] text-encre placeholder:text-attenue" />
        </label>
        <button type="submit" disabled={etat.envoi || !justification.trim()}
          className="rounded-md bg-action px-3 py-1.5 text-[13px] font-semibold text-action-encre disabled:opacity-40">
          {etat.envoi ? "Enregistrement…" : "Enregistrer la décision"}
        </button>
        {etat.erreur && <p className="text-[12px] text-prio-texte">Échec : {etat.erreur}</p>}
      </form>
      {historique.length > 0 && (
        <ol className="flex flex-col gap-1.5 border-t border-bordure pt-2">
          {[...historique].reverse().map((d) => (
            <li key={d.id_decision} className="text-[12px] text-encre-2">
              <span className="chiffres text-attenue">{fmtDate(d.date_heure)}</span> · <strong className="text-encre">{DECISIONS[d.decision] ?? d.decision}</strong> — {d.justification}
            </li>
          ))}
        </ol>
      )}
    </Section>
  );
}

export default function PourquoiScore({ mf, detail }) {
  const contributions = detail.contributions ?? [];
  const max = Math.max(1, ...contributions.map((c) => c.points));
  const base = Math.round((detail.score - contributions.reduce((s, c) => s + c.points, 0)) * 10) / 10;
  const e = detail.enjeu ?? {};
  const pairs = detail.pairs ?? { indicateurs: [] };
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <Section titre="Pourquoi ce score ?" icone={Lightbulb} className="xl:col-span-2">
        <div className="-mt-1 flex flex-col gap-1">
          <p className="text-[13px] leading-relaxed text-encre">{detail.resume_fr}</p>
          <p className="text-[12px] text-attenue">
            Score {detail.score.toLocaleString("fr-FR")}/100 = base {base.toLocaleString("fr-FR")} + contributions ci-dessous
            {e.estime > 0 && <> · enjeu estimé {fmtCompact(e.estime)} (fourchette {fmtCompact(e.bas)} – {fmtCompact(e.haut)})</>}
          </p>
        </div>
        <ul className="flex flex-col divide-y divide-bordure">
          {contributions.map((c) => (
            <li key={c.code_signal} className="flex flex-col gap-1.5 py-2.5 first:pt-0">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="text-[13px] font-semibold text-encre">{c.libelle}</span>
                <span className="rounded-full bg-fond-2 px-2 py-0.5 text-[11px] text-encre-2">{LENTILLES[c.lentille] ?? c.lentille}</span>
                <span className="font-mono text-[10.5px] text-attenue">{c.code_signal}</span>
                <span className="ml-auto flex items-center gap-2">
                  <span className="h-2 w-28 overflow-hidden rounded-full bg-fond-2">
                    <span className="block h-full rounded-full bg-prio" style={{ width: `${(100 * Math.max(0, c.points)) / max}%` }} />
                  </span>
                  <span className="chiffres w-16 text-right text-[13px] font-bold text-encre">{pts(c.points)} pts</span>
                </span>
              </div>
              {c.fait_fr && <p className="text-[12.5px] leading-snug text-encre-2">{c.fait_fr}</p>}
              {c.nb_preuves > 0 && <Preuves mf={mf} code={c.code_signal} />}
            </li>
          ))}
          {!contributions.length && <li className="py-2 text-[12.5px] text-attenue">Aucun signal ne contribue au score ce mois-ci.</li>}
        </ul>
      </Section>
      <div className="flex flex-col gap-4">
        <Decision mf={mf} suggeree={detail.action_suggeree} initiales={detail.decisions ?? []} />
        {pairs.indicateurs.length > 0 && (
          <Section titre={`Face à ses pairs (${pairs.nb_pairs} entreprises)`} icone={Users}>
            <p className="-mt-2 text-[11.5px] text-attenue">{pairs.groupe}</p>
            <ul className="flex flex-col gap-1.5">
              {pairs.indicateurs.map((i) => (
                <li key={i.nom} className="flex flex-col text-[12.5px]">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="text-encre-2">{i.nom}</span>
                    <strong className="chiffres text-encre">{valeurIndicateur(i.nom, i.entreprise)}</strong>
                  </span>
                  <span className="chiffres text-right text-[11.5px] text-attenue">
                    pairs : médiane {valeurIndicateur(i.nom, i.mediane_pairs)} · P10–P90 {valeurIndicateur(i.nom, i.p10)} – {valeurIndicateur(i.nom, i.p90)}
                  </span>
                </li>
              ))}
            </ul>
          </Section>
        )}
        <p className="flex items-center gap-1.5 px-1 text-[11.5px] text-attenue"><FileSearch size={12} aria-hidden="true" />Chaque point du score renvoie à des lignes de données brutes.</p>
      </div>
    </div>
  );
}
