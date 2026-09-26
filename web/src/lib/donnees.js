// Point d'accès unique aux données.
// VITE_API_URL renseignée (ex. http://localhost:8000) : API FastAPI de Basira, routes /api/front/* (mêmes formes
// que le jeu fictif) + routes du contrat §6 (preuves, décision, assistant). Vide : jeu fictif local (mockData.json).
import mockData from "../data/mockData.json";

const API = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
export const modeApi = API !== "";

// Liaisons vivantes : mises à jour par chargerPortefeuille() avant le premier rendu (voir main.jsx)
export let meta = mockData.meta;
let entreprises = mockData.entreprises;
const SEGMENTS = ["PRIORITAIRE", "SURVEILLANCE", "NORMAL", "CONFIANCE"];

async function requete(chemin, options) {
  const r = await fetch(`${API}${chemin}`, options);
  if (!r.ok) throw new Error(`${chemin} : HTTP ${r.status}`);
  return r.json();
}

// Le portefeuille arrive compact (h = 12 × [score, segment, enjeu, imports]) : on le remet au format des pages
function deplier(e, mois) {
  const { h, ...reste } = e;
  return {
    ...reste,
    network_nodes: [],
    historique_mensuel: h.map(([score, seg, enjeu, imports], i) => ({
      mois: mois[i], score, segment: SEGMENTS[seg], ecart_recoupement_dt: enjeu, imports_sinda_dt: imports
    }))
  };
}

export async function chargerPortefeuille() {
  if (!modeApi) return;
  const p = await requete("/api/front/portefeuille");
  meta = { ...mockData.meta, ...p.meta, titre: "Portefeuille Basira (données synthétiques)", sessions_copilote: mockData.meta.sessions_copilote };
  entreprises = p.entreprises.map((e) => deplier(e, p.meta.mois_couverts));
}

export const listerEntreprises = () => entreprises;
export const trouverEntreprise = (mf) => entreprises.find((e) => e.mf === mf) ?? null;

// Fiche complète (opérations, réseau, contrôles, détail du score) : chargée à la demande, gardée en cache
const fiches = new Map();
export function chargerFiche(mf) {
  if (!modeApi) return Promise.resolve(mockData.entreprises.find((e) => e.mf === mf) ?? null);
  if (!fiches.has(mf)) {
    fiches.set(mf, requete(`/api/front/entreprises/${mf}`).catch((err) => { fiches.delete(mf); if (/404/.test(err.message)) return null; throw err; }));
  }
  return fiches.get(mf);
}
export const oublierFiche = (mf) => fiches.delete(mf);

// Entreprises du portefeuille liées à une contrepartie (graphe de réseau, jeu fictif uniquement)
export function entreprisesLiees(idContrepartie, sauf) {
  return entreprises.filter(
    (e) => e.mf !== sauf && (e.network_nodes.some((n) => n.id === idContrepartie) || e.mf === idContrepartie)
  );
}

// Routes du contrat §6 (mode API uniquement)
export const chargerVoisins = (id) => requete(`/api/front/voisins/${encodeURIComponent(id)}`);
export const chargerPreuves = (mf, signal) => requete(`/api/entreprises/${mf}/preuves?signal=${encodeURIComponent(signal)}`);
export const enregistrerDecision = (mf, corps) =>
  requete(`/api/entreprises/${mf}/decision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps) });
export const demanderAssistant = (corps) =>
  requete("/api/assistant", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps) });

// Même question, en flux (text/event-stream) : `surEvenement(type, données)` reçoit les étapes (`etape`) et les actions
// sur le graphe (`graphe`) au fil de l'eau ; la promesse rend la réponse finale. Repli sur la route classique si le flux échoue.
export async function demanderAssistantFlux(corps, surEvenement) {
  let r;
  try {
    r = await fetch(`${API}/api/assistant/flux`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps) });
  } catch {
    r = null;
  }
  if (!r?.ok || !r.body) {
    const rep = await demanderAssistant(corps);
    (rep.graphe ?? []).forEach((a) => surEvenement("graphe", a));
    return rep;
  }
  const lecteur = r.body.getReader();
  const decodeur = new TextDecoder();
  let tampon = "", finale = null;
  for (;;) {
    const { value, done } = await lecteur.read();
    if (done) break;
    tampon += decodeur.decode(value, { stream: true });
    let fin;
    while ((fin = tampon.indexOf("\n\n")) >= 0) {
      const bloc = tampon.slice(0, fin);
      tampon = tampon.slice(fin + 2);
      const type = /^event: (.+)$/m.exec(bloc)?.[1];
      const brut = /^data: (.+)$/m.exec(bloc)?.[1];
      if (!type || !brut) continue;
      const donnees = JSON.parse(brut);
      if (type === "reponse") finale = donnees;
      else if (type === "erreur") throw new Error(donnees.detail);
      else surEvenement(type, donnees);
    }
  }
  if (!finale) throw new Error("flux interrompu");
  return finale;
}
