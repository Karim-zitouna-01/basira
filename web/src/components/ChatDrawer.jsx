// Copilote IA : panneau latéral. Chaque question part avec le contexte de la page
// affichée (filtres actifs, agrégats visibles), jamais avec la base complète.
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowUp, Eye, History, Sparkles, X } from "lucide-react";
import { useContextePage } from "../lib/contextePage.jsx";
import { demanderAssistant, meta, modeApi } from "../lib/donnees.js";
import { repondreDemo } from "../lib/copiloteDemo.js";
import { fmtDate, fmtMoisIso } from "../lib/format.js";
import { libelleCitation } from "../lib/signaux.js";
import LatticeLoader from "./LatticeLoader/LatticeLoader.jsx";

const ACTIONS_RAPIDES = [
  { intention: "anomalie", libelle: "Expliquer l'anomalie de recoupement" },
  { intention: "conformite", libelle: "Conformité LOB 2019-15 & Code des Douanes" },
  { intention: "rapport", libelle: "Générer le pré-rapport d'audit" }
];
// Avec l'API : questions que l'assistant de Basira sait traiter (outils sur la fiche, données de l'écran sur la liste)
const ACTIONS_API = [
  { intention: "pourquoi", libelle: "Pourquoi ce score ?", question: "Pourquoi le risque de cette entreprise a-t-il changé ?" },
  { intention: "reseau", libelle: "Analyser le réseau", question: "Que montre le réseau de fournisseurs et de clients de cette entreprise ?" },
  { intention: "lettre", libelle: "Rédiger la demande d'information", question: "Rédige un projet de lettre de demande d'information." }
];
const ACTIONS_LISTE = [
  { intention: "priorites", libelle: "Quels dossiers ouvrir en premier ?", question: "Parmi les entreprises affichées, lesquelles dois-je examiner en premier et pourquoi ?" },
  { intention: "evolution", libelle: "Qu'est-ce qui a changé ce mois-ci ?", question: "Qu'est-ce qui a changé ce mois-ci dans le portefeuille affiché ?" },
  { intention: "synthese", libelle: "Synthèse de la sélection", question: "Fais une synthèse courte de la sélection affichée." }
];

// Loader React Bits (LatticeLoader), aux couleurs de l'interface
const LOADER = {
  pattern: "orbit", grid: 3, shape: "round", color: "var(--action)", doneColor: "var(--seg-conf)", errorColor: "var(--seg-surv)",
  cellSize: 5, gap: 2, step: 90, idleOpacity: 0.15, glow: false, showTimer: true
};

// Libellé court de ce que voit le copilote (une ligne)
export function resumerContexte(c) {
  if (!c) return "Aucune donnée affichée";
  if (c.page === "liste") {
    const f = [c.filtres.segment, c.filtres.recherche && `« ${c.filtres.recherche} »`].filter(Boolean);
    return `Liste · ${c.nb_affichees} entreprises${f.length ? ` · ${f.join(", ")}` : ""}`;
  }
  const p = c.filtres_actifs?.periode;
  const periode = p ? (p.debut === p.fin ? fmtMoisIso(p.debut) : `${fmtMoisIso(p.debut)} → ${fmtMoisIso(p.fin)}`) : "12 mois";
  const filtres = [...(c.filtres_actifs?.systemes ?? []), ...(c.filtres_actifs?.contreparties ?? [])];
  return `${c.titre} · ${periode}${filtres.length ? ` · ${filtres.length} filtre${filtres.length > 1 ? "s" : ""}` : ""}`;
}

const lienExterne = { a: ({ node, ...p }) => <a {...p} target="_blank" rel="noreferrer" /> }; // eslint-disable-line no-unused-vars

function Reponse({ m }) {
  const [toutes, setToutes] = useState(false);
  const citations = m.citations ?? [];
  const visibles = toutes ? citations : citations.slice(0, 3);
  const repli = m.mode === "modele_texte";
  return (
    <div className="flex flex-col gap-2">
      <div className="md text-[13px] leading-relaxed text-encre">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={lienExterne}>{m.texte}</ReactMarkdown>
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        {m.duree != null && (
          <LatticeLoader {...LOADER} status={m.mode === "erreur" ? "error" : repli ? "error" : "done"} elapsed={m.duree}
            label="" doneLabel="Répondu en" errorLabel={m.mode === "erreur" ? "Échec après" : "Réponse de repli ·"}
            fontSize={11.5} cellSize={3} gap={1} className="text-attenue" />
        )}
        {repli && m.raison && <span className="text-[11.5px] text-attenue">{m.raison}</span>}
        {visibles.map((c) => (
          <span key={`${c.type}:${c.ref}`} title={c.ref}
            className="max-w-[210px] truncate rounded-full border border-bordure px-2 py-0.5 text-[11px] text-encre-2">
            {libelleCitation(c)}
          </span>
        ))}
        {citations.length > 3 && !toutes && (
          <button type="button" onClick={() => setToutes(true)} className="text-[11px] font-semibold text-action-texte">+{citations.length - 3}</button>
        )}
      </div>
    </div>
  );
}

export default function ChatDrawer({ onFermer }) {
  const navigate = useNavigate();
  const { contexte } = useContextePage();
  const [conversations, setConversations] = useState({});
  const [saisie, setSaisie] = useState("");
  const [historiqueOuvert, setHistoriqueOuvert] = useState(false);
  const [voirDonnees, setVoirDonnees] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const finRef = useRef(null);

  // Une conversation par page : la liste, puis une par entreprise
  const surFiche = contexte?.page === "fiche_entreprise";
  const cle = surFiche ? contexte.entreprise.company_id : "liste";
  const messages = conversations[cle] ?? [];
  const resume = resumerContexte(contexte);
  const viaApi = modeApi; // API : les deux pages passent par l'assistant (Qwen), avec les données de l'écran jointes
  const actions = !viaApi ? ACTIONS_RAPIDES : surFiche ? ACTIONS_API : ACTIONS_LISTE;
  const dernier = [...messages].reverse().find((m) => m.mode);
  const enLigne = viaApi && dernier?.mode !== "modele_texte" && dernier?.mode !== "erreur";

  useEffect(() => { finRef.current?.scrollIntoView({ block: "end", behavior: "smooth" }); }, [messages.length, enCours]);

  const sessionsParDate = useMemo(() => {
    const groupes = new Map();
    for (const s of meta.sessions_copilote) groupes.set(s.date, [...(groupes.get(s.date) ?? []), s]);
    return [...groupes.entries()];
  }, []);

  function envoyer(question, intention = "libre") {
    if (!question.trim() || enCours || !contexte) return;
    const instantane = structuredClone(contexte);
    const ajouter = (m) => setConversations((c) => ({ ...c, [cle]: [...(c[cle] ?? []), m] }));
    ajouter({ role: "inspecteur", texte: question });
    setSaisie("");
    setEnCours(true);
    const t0 = performance.now();
    const duree = () => (performance.now() - t0) / 1000;
    if (viaApi) {
      // POST /api/assistant (contrat §6.2) : sur la fiche, l'assistant lit aussi la fiche, les preuves et le réseau
      // par ses outils ; sur la liste (sans mf), il répond à partir des données affichées
      const historique = messages.map((m) => ({ role: m.role === "inspecteur" ? "user" : "assistant", contenu: m.texte }));
      demanderAssistant({ mf: surFiche ? instantane.entreprise.mf : null, question, historique, contexte: instantane })
        .then((r) => ajouter({ role: "copilote", texte: r.reponse, citations: r.citations ?? [], mode: r.mode, raison: r.raison_repli, duree: duree() }))
        .catch((err) => ajouter({ role: "copilote", texte: `L'assistant est indisponible (${err.message}).`, mode: "erreur", duree: duree() }))
        .finally(() => setEnCours(false));
      return;
    }
    // Jeu fictif : réponse calculée localement sur les données affichées
    setTimeout(() => {
      ajouter({ role: "copilote", texte: repondreDemo(question, instantane, intention), duree: duree() });
      setEnCours(false);
    }, 450);
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-bordure px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <h2 className="text-[14px] font-bold text-encre">Copilote</h2>
          <span className="inline-flex items-center gap-1.5 text-[11.5px] text-attenue"
            title={viaApi ? "Qwen 3.5 9B, servi sur le réseau local : aucune donnée ne sort" : "Réponses simulées (jeu fictif)"}>
            <span className="size-1.5 rounded-full" style={{ background: enLigne ? "var(--seg-conf)" : "var(--seg-surv)" }} />
            {viaApi ? "Qwen 3.5 · local" : "Démo"}
          </span>
        </div>
        <div className="flex items-center gap-0.5">
          <button type="button" onClick={() => setHistoriqueOuvert((o) => !o)} aria-expanded={historiqueOuvert} title="Sessions précédentes"
            className="grid size-7 place-items-center rounded-md text-attenue hover:bg-fond-2 hover:text-encre"><History size={15} /></button>
          <button type="button" onClick={onFermer} aria-label="Fermer le copilote" title="Fermer"
            className="grid size-7 place-items-center rounded-md text-attenue hover:bg-fond-2 hover:text-encre"><X size={16} /></button>
        </div>
      </div>

      {/* Ce que le copilote voit : une ligne discrète, détail à la demande */}
      <div className="border-b border-bordure px-4 py-1.5">
        <button type="button" onClick={() => setVoirDonnees((v) => !v)} aria-expanded={voirDonnees}
          className="flex w-full min-w-0 items-center gap-1.5 text-left text-[11.5px] text-attenue hover:text-encre-2" title="Voir les données jointes aux questions">
          <Eye size={12} className="shrink-0" aria-hidden="true" />
          <span className="truncate">{resume}</span>
        </button>
        {voirDonnees && (
          <pre className="mt-1.5 max-h-48 overflow-auto rounded-md bg-fond p-2 font-mono text-[10.5px] leading-snug text-encre-2">{JSON.stringify(contexte, null, 2)}</pre>
        )}
      </div>

      {historiqueOuvert && (
        <div className="max-h-[45%] overflow-y-auto border-b border-bordure bg-fond px-4 py-3">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-attenue">Sessions précédentes</div>
          <div className="flex flex-col gap-3">
            {sessionsParDate.map(([date, sessions]) => (
              <div key={date} className="flex flex-col gap-1.5">
                <div className="chiffres text-[11.5px] font-semibold text-encre-2">{fmtDate(date)}</div>
                {sessions.map((s) => (
                  <button key={s.id} type="button" onClick={() => { navigate(`/entreprise/${s.mf}`); setHistoriqueOuvert(false); }}
                    className="rounded-md border border-bordure bg-carte px-3 py-2 text-left hover:border-attenue">
                    <div className="text-[12.5px] font-semibold text-encre">{s.entreprise}</div>
                    <div className="text-[12px] text-encre-2">{s.titre}</div>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-4 py-4" aria-live="polite">
        {!messages.length && (
          <div className="flex flex-1 flex-col justify-center gap-4">
            <div className="flex flex-col items-center gap-2 text-center">
              <span className="grid size-9 place-items-center rounded-full bg-fond-2 text-action-texte"><Sparkles size={17} aria-hidden="true" /></span>
              <p className="text-[15px] font-semibold text-encre">Que voulez-vous comprendre ?</p>
              <p className="max-w-[32ch] text-[12px] text-attenue">Chaque chiffre de la réponse est vérifié dans les données. La décision reste la vôtre.</p>
            </div>
            <div className="flex flex-col gap-1.5">
              {actions.map((a) => (
                <button key={a.intention} type="button" onClick={() => envoyer(a.question ?? a.libelle, a.intention)}
                  className="rounded-lg border border-bordure bg-carte px-3 py-2 text-left text-[12.5px] text-encre-2 hover:border-attenue hover:text-encre">
                  {a.libelle}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => m.role === "inspecteur" ? (
          <div key={i} className="ml-auto max-w-[88%] rounded-2xl rounded-br-md bg-action px-3 py-2 text-[13px] leading-snug text-action-encre">{m.texte}</div>
        ) : (
          <Reponse key={i} m={m} />
        ))}
        {enCours && (
          <LatticeLoader {...LOADER} status="working" label={surFiche ? "Lecture de la fiche et des preuves" : "Lecture du portefeuille"}
            doneLabel="Répondu en" errorLabel="Échec après" fontSize={12.5} className="text-encre-2" />
        )}
        <div ref={finRef} />
      </div>

      <div className="flex flex-col gap-2 border-t border-bordure px-3 py-2.5">
        {messages.length > 0 && (
          <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-0.5 [scrollbar-width:none]">
            {actions.map((a) => (
              <button key={a.intention} type="button" disabled={enCours} onClick={() => envoyer(a.question ?? a.libelle, a.intention)}
                className="shrink-0 rounded-full border border-bordure bg-carte px-2.5 py-1 text-[11.5px] text-encre-2 hover:border-attenue disabled:opacity-50">
                {a.libelle}
              </button>
            ))}
          </div>
        )}
        <form className="flex items-end gap-2 rounded-xl border border-bordure bg-carte py-1.5 pl-3 pr-1.5 focus-within:border-attenue"
          onSubmit={(e) => { e.preventDefault(); envoyer(saisie); }}>
          <label htmlFor="question" className="sr-only">Question au copilote</label>
          <textarea id="question" rows={1} value={saisie} onChange={(e) => setSaisie(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); envoyer(saisie); } }}
            placeholder="Posez une question…"
            className="max-h-32 min-w-0 flex-1 resize-none bg-transparent py-1 text-[13px] outline-none [field-sizing:content] placeholder:text-attenue" />
          <button type="submit" disabled={enCours || !saisie.trim()} aria-label="Envoyer la question"
            className="grid size-7 shrink-0 place-items-center rounded-lg bg-action text-action-encre disabled:opacity-30"><ArrowUp size={15} /></button>
        </form>
      </div>
    </div>
  );
}
