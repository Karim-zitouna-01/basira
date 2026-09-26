// Copilote IA : panneau latéral. Chaque question part avec le contexte de la page
// affichée (filtres actifs, agrégats visibles), jamais avec la base complète.
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ActionIcon, Anchor, Badge, Button, Group, Stack, Text, Textarea, ThemeIcon, Tooltip } from "@mantine/core";
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
          <Tooltip key={`${c.type}:${c.ref}`} label={c.ref}>
            <Badge variant="default" size="sm" radius="xl" maw={220} fw={500} className="cursor-help">{libelleCitation(c)}</Badge>
          </Tooltip>
        ))}
        {citations.length > 3 && !toutes && (
          <Anchor size="xs" fw={600} onClick={() => setToutes(true)}>+{citations.length - 3}</Anchor>
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
      <Group justify="space-between" gap="xs" px="md" py={10} className="border-b border-bordure" wrap="nowrap">
        <Group gap={8} wrap="nowrap">
          <ThemeIcon variant="light" size={28} radius="md"><Sparkles size={15} /></ThemeIcon>
          <Text fw={700} size="md">Copilote</Text>
          <Tooltip label={viaApi ? "Qwen 3.5 9B, servi sur le réseau local : aucune donnée ne sort" : "Réponses simulées (jeu fictif)"}>
            <Badge variant="dot" color={enLigne ? "teal" : "orange"} size="sm" fw={500}>{viaApi ? "Qwen 3.5 · local" : "Démo"}</Badge>
          </Tooltip>
        </Group>
        <Group gap={2} wrap="nowrap">
          <Tooltip label="Sessions précédentes">
            <ActionIcon onClick={() => setHistoriqueOuvert((o) => !o)} aria-expanded={historiqueOuvert} aria-label="Sessions précédentes"><History size={16} /></ActionIcon>
          </Tooltip>
          <Tooltip label="Fermer"><ActionIcon onClick={onFermer} aria-label="Fermer le copilote"><X size={17} /></ActionIcon></Tooltip>
        </Group>
      </Group>

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
              <ThemeIcon variant="light" size={40} radius="xl"><Sparkles size={19} /></ThemeIcon>
              <Text fw={700} size="lg">Que voulez-vous comprendre ?</Text>
              <Text size="sm" c="dimmed" maw={300}>Chaque chiffre de la réponse est vérifié dans les données. La décision reste la vôtre.</Text>
            </div>
            <Stack gap={6}>
              {actions.map((a) => (
                <Button key={a.intention} variant="default" justify="space-between" fw={500} rightSection={<ArrowUp size={14} className="rotate-45 text-attenue" />}
                  onClick={() => envoyer(a.question ?? a.libelle, a.intention)}>
                  {a.libelle}
                </Button>
              ))}
            </Stack>
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
              <Button key={a.intention} variant="default" size="compact-xs" radius="xl" fw={500} className="shrink-0" disabled={enCours}
                onClick={() => envoyer(a.question ?? a.libelle, a.intention)}>
                {a.libelle}
              </Button>
            ))}
          </div>
        )}
        <form onSubmit={(e) => { e.preventDefault(); envoyer(saisie); }}>
          <Textarea autosize minRows={1} maxRows={5} radius="lg" value={saisie} onChange={(e) => setSaisie(e.currentTarget.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); envoyer(saisie); } }}
            placeholder="Posez une question…" aria-label="Question au copilote" rightSectionWidth={42}
            rightSection={
              <ActionIcon type="submit" variant="filled" color="basira" radius="md" disabled={enCours || !saisie.trim()} aria-label="Envoyer la question">
                <ArrowUp size={15} />
              </ActionIcon>
            } />
        </form>
      </div>
    </div>
  );
}
