// Copilote IA : panneau latéral. Chaque question part avec le contexte de la page
// affichée (filtres actifs, agrégats visibles), jamais avec la base complète.
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useContextePage } from "../lib/contextePage.jsx";
import { demanderAssistant, meta, modeApi } from "../lib/donnees.js";
import { repondreDemo } from "../lib/copiloteDemo.js";
import { fmtCompact, fmtDate, fmtMoisIso } from "../lib/format.js";
import { History, SendHorizontal, Sparkles, X } from "lucide-react";

const ACTIONS_RAPIDES = [
  { intention: "anomalie", libelle: "🔍 Expliquer l'anomalie de recoupement" },
  { intention: "conformite", libelle: "📜 Conformité LOB 2019-15 & Code des Douanes" },
  { intention: "rapport", libelle: "📄 Générer le pré-rapport d'audit" }
];
// Fiche entreprise avec l'API : questions que l'assistant de Basira sait traiter à partir de ses outils
const ACTIONS_API = [
  { intention: "pourquoi", libelle: "🔍 Pourquoi ce score ?", question: "Pourquoi le risque de cette entreprise a-t-il changé ?" },
  { intention: "reseau", libelle: "🕸️ Analyser le réseau", question: "Que montre le réseau de fournisseurs et de clients de cette entreprise ?" },
  { intention: "lettre", libelle: "📄 Rédiger la demande d'information", question: "Rédige un projet de lettre de demande d'information." }
];
const MODES = { llm: "Qwen 3.5 local", modele_texte: "Réponse de repli (sans LLM)" };

export function resumerContexte(c) {
  if (!c) return "Aucune donnée affichée";
  if (c.page === "liste") {
    const f = [c.filtres.segment, c.filtres.recherche && `« ${c.filtres.recherche} »`].filter(Boolean);
    return `Liste des entreprises · ${c.nb_affichees} affichées${f.length ? ` · filtre ${f.join(", ")}` : ""}`;
  }
  const f = c.filtres_actifs;
  const parts = [
    f.periode && (f.periode.debut === f.periode.fin ? fmtMoisIso(f.periode.debut) : `${fmtMoisIso(f.periode.debut)} → ${fmtMoisIso(f.periode.fin)}`),
    f.systemes.length && f.systemes.join(", "),
    f.contreparties.length && f.contreparties.join(", "),
    f.pays.length && f.pays.join(", ")
  ].filter(Boolean);
  return `${c.titre} · ${parts.length ? parts.join(" · ") : "12 mois, sans filtre"} · ${c.selection.nb_operations} opérations (${fmtCompact(c.selection.total_dt)})`;
}

export default function ChatDrawer({ onFermer }) {
  const navigate = useNavigate();
  const { contexte } = useContextePage();
  const [conversations, setConversations] = useState({});
  const [saisie, setSaisie] = useState("");
  const [historiqueOuvert, setHistoriqueOuvert] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const finRef = useRef(null);

  // Une conversation par page : la liste, puis une par entreprise
  const cle = contexte?.page === "fiche_entreprise" ? contexte.entreprise.company_id : "liste";
  const messages = conversations[cle] ?? [];
  const resume = resumerContexte(contexte);
  const viaApi = modeApi && contexte?.page === "fiche_entreprise";
  const actions = viaApi ? ACTIONS_API : ACTIONS_RAPIDES;
  const dernierMode = [...messages].reverse().find((m) => m.mode)?.mode;
  const badge = viaApi ? (MODES[dernierMode] ?? "Assistant Basira") : modeApi ? "Calcul sur la liste affichée" : "Mode démo : réponses simulées";

  useEffect(() => { finRef.current?.scrollIntoView({ block: "end" }); }, [messages.length, enCours]);

  const sessionsParDate = useMemo(() => {
    const groupes = new Map();
    for (const s of meta.sessions_copilote) groupes.set(s.date, [...(groupes.get(s.date) ?? []), s]);
    return [...groupes.entries()];
  }, []);

  function envoyer(question, intention = "libre") {
    if (!question.trim() || enCours || !contexte) return;
    const instantane = structuredClone(contexte);
    const ajouter = (m) => setConversations((c) => ({ ...c, [cle]: [...(c[cle] ?? []), m] }));
    ajouter({ role: "inspecteur", texte: question, resume });
    setSaisie("");
    setEnCours(true);
    if (viaApi) {
      // POST /api/assistant (contrat §6.2) : l'assistant lit la fiche, les preuves et le réseau par ses outils
      const historique = messages.map((m) => ({ role: m.role === "inspecteur" ? "user" : "assistant", contenu: m.texte }));
      demanderAssistant({ mf: instantane.entreprise.mf, question, historique })
        .then((r) => ajouter({ role: "copilote", texte: r.reponse, citations: r.citations ?? [], mode: r.mode }))
        .catch((err) => ajouter({ role: "copilote", texte: `L'assistant est indisponible (${err.message}).`, mode: "erreur" }))
        .finally(() => setEnCours(false));
      return;
    }
    // Liste des entreprises (ou jeu fictif) : réponse calculée localement sur les données affichées
    setTimeout(() => {
      ajouter({ role: "copilote", texte: repondreDemo(question, instantane, intention) });
      setEnCours(false);
    }, 450);
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-bordure px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-[14px] font-bold text-encre">Copilote IA</h2>
          <span className="rounded-full bg-fond-2 px-2 py-0.5 text-[11px] font-semibold text-attenue">{badge}</span>
        </div>
        <div className="flex items-center gap-1">
          <button type="button" onClick={() => setHistoriqueOuvert((o) => !o)} aria-expanded={historiqueOuvert}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-[12.5px] font-semibold text-action-texte hover:bg-fond-2"><History size={14} aria-hidden="true" />Historique</button>
          <button type="button" onClick={onFermer} aria-label="Fermer le copilote" className="grid size-7 place-items-center rounded-md text-attenue hover:bg-fond-2"><X size={16} /></button>
        </div>
      </div>

      {historiqueOuvert && (
        <div className="max-h-[45%] overflow-y-auto border-b border-bordure bg-fond px-4 py-3">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-attenue">Sessions précédentes</div>
          <div className="flex flex-col gap-3">
            {sessionsParDate.map(([date, sessions]) => (
              <div key={date} className="flex flex-col gap-1.5">
                <div className="chiffres text-[12px] font-semibold text-encre-2">{fmtDate(date)}</div>
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

      {/* Bandeau : ce que le copilote voit en ce moment */}
      <div className="border-b border-bordure px-4 py-3">
        <div className="rounded-md border px-3 py-2" style={{ borderColor: "color-mix(in srgb, var(--action) 35%, white)", background: "color-mix(in srgb, var(--action) 6%, white)" }}>
          <div className="text-[10.5px] font-bold uppercase tracking-[0.06em] text-action-texte">Contexte de la page</div>
          <div className="text-[12.5px] text-encre">{resume}</div>
          <details className="mt-1">
            <summary className="cursor-pointer text-[12px] text-encre-2">Voir les données transmises</summary>
            <pre className="mt-1 max-h-56 overflow-auto rounded bg-carte p-2 font-mono text-[10.5px] leading-snug text-encre-2">{JSON.stringify(contexte, null, 2)}</pre>
          </details>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-3" aria-live="polite">
        {!messages.length && (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 px-4 text-center">
            <span className="grid size-10 place-items-center rounded-full bg-fond-2 text-action-texte"><Sparkles size={18} aria-hidden="true" /></span>
            <p className="text-[16px] font-semibold text-encre">Bonjour, comment puis-je vous aider ?</p>
            <p className="max-w-[34ch] text-[12.5px] text-attenue">
              Je réponds à partir de ce qui est affiché : la période, les filtres et les indicateurs de la page sont joints à votre question.
            </p>
          </div>
        )}
        {messages.map((m, i) => m.role === "inspecteur" ? (
          <div key={i} className="flex flex-col items-end gap-1">
            <div className="max-w-[92%] rounded-lg bg-action px-3 py-2 text-[13px] text-action-encre">{m.texte}</div>
            <div className="max-w-[92%] text-right text-[11px] text-attenue">Envoyé avec : {m.resume}</div>
          </div>
        ) : (
          <div key={i} className="flex max-w-[96%] flex-col gap-1.5">
            <div className="whitespace-pre-line rounded-lg bg-fond-2 px-3 py-2 text-[13px] leading-relaxed text-encre-2">{m.texte}</div>
            {m.citations?.length > 0 && (
              <div className="flex flex-wrap items-center gap-1 text-[11px] text-attenue">
                Sources :
                {m.citations.map((c) => (
                  <span key={`${c.type}:${c.ref}`} className="rounded bg-fond px-1.5 py-0.5 font-mono text-[10.5px] text-encre-2" title={c.type === "preuve" ? "Ligne de données brute" : "Signal"}>{c.ref}</span>
                ))}
              </div>
            )}
            {m.mode && m.mode !== "erreur" && <div className="text-[11px] text-attenue">{MODES[m.mode] ?? m.mode} · la décision appartient à l'inspecteur</div>}
          </div>
        ))}
        {enCours && <div className="text-[12.5px] text-attenue">Le copilote analyse les données affichées…</div>}
        <div ref={finRef} />
      </div>

      <div className="flex flex-col gap-2 border-t border-bordure px-4 py-3">
        <div className="flex flex-wrap gap-1.5">
          {actions.map((a) => (
            <button key={a.intention} type="button" disabled={enCours} onClick={() => envoyer(a.question ?? a.libelle.replace(/^\S+\s/, ""), a.intention)}
              className="rounded-full border border-bordure bg-carte px-2.5 py-1 text-[12px] text-encre-2 hover:border-attenue disabled:opacity-50">
              {a.libelle}
            </button>
          ))}
        </div>
        <form className="flex items-end gap-2 rounded-xl border border-bordure bg-carte p-2 focus-within:border-attenue" onSubmit={(e) => { e.preventDefault(); envoyer(saisie); }}>
          <label htmlFor="question" className="sr-only">Question au copilote</label>
          <textarea id="question" rows={2} value={saisie} onChange={(e) => setSaisie(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); envoyer(saisie); } }}
            placeholder="Posez votre question sur les données affichées…"
            className="min-w-0 flex-1 resize-none bg-transparent px-1 py-1 text-[13px] outline-none placeholder:text-attenue" />
          <button type="submit" disabled={enCours || !saisie.trim()} aria-label="Envoyer la question"
            className="grid size-8 shrink-0 place-items-center rounded-lg bg-action text-action-encre disabled:opacity-40"><SendHorizontal size={15} /></button>
        </form>
      </div>
    </div>
  );
}
