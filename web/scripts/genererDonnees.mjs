// Enrichit src/data/mockData.json : historique mensuel (12 mois) et opérations
// unitaires (SINDA, ADEB, Plateforme TJ, RAFIK) pour chaque entreprise.
// Les champs de synthèse existants restent la référence : les totaux générés
// les respectent (volume d'import, paiements ADEB, variation des imports).
// Exécution : npm run donnees  (idempotent, graine fixe 2026)
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const FICHIER = path.join(path.dirname(fileURLToPath(import.meta.url)), "../src/data/mockData.json");
const MOIS = ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"];
const PAYS = {
  FE00231: "Chine", FE00412: "Chine", FE00517: "Chine", FE00602: "Turquie", FE00788: "Émirats arabes unis",
  FE00910: "Turquie", FE01022: "Allemagne", FE01130: "France", FE01201: "Espagne",
  FE01305: "Turquie", FE01410: "Espagne", FE01502: "France"
};

// Générateur pseudo-aléatoire déterministe (mulberry32)
let graine = 2026;
function alea() {
  graine = (graine + 0x6d2b79f5) | 0;
  let t = Math.imul(graine ^ (graine >>> 15), 1 | graine);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
const bruit = (amplitude) => 1 + (alea() * 2 - 1) * amplitude;
const arrondi = (v) => Math.round(v);
const jour = (mois) => `${mois}-${String(1 + Math.floor(alea() * 27)).padStart(2, "0")}`;

// Répartit un total sur des poids, somme exacte garantie
function repartir(total, poids) {
  const somme = poids.reduce((a, b) => a + b, 0) || 1;
  const parts = poids.map((p) => arrondi((total * p) / somme));
  parts[parts.length - 1] += total - parts.reduce((a, b) => a + b, 0);
  return parts;
}

// Imports mensuels : 9 mois de base puis 3 mois relevés de la variation annoncée
function importsMensuels(e) {
  if (!e.sinda_import_vol_dt) return MOIS.map(() => 0);
  const v = e.sinda_import_variance_pct / 100;
  const poids = MOIS.map((_, i) => (i < 9 ? 1 : 1 + v) * bruit(0.12));
  return repartir(e.sinda_import_vol_dt, poids);
}

// Trajectoire du score : stable jusqu'en 2026-06, puis bascule vers le score courant
function trajectoire(e) {
  const delta = Number(e.risk_delta_2m);
  const depart = e.current_risk_score - delta;
  return MOIS.map((_, i) => {
    if (i === 11) return e.current_risk_score;
    if (i === 10) return Math.round(depart + delta / 2);
    return Math.max(0, Math.min(100, Math.round(depart + (alea() * 4 - 2))));
  });
}

// Profils particuliers issus du contrat (cas héros)
const DORMANT_JUSQUA = { "1000004EAM000": 8 }; // Delta Trade : inactive puis reprise
const NON_DEPOSEES = { "1000004EAM000": [6, 7, 9, 10] };
const CA_NUL = new Set(["1000008JAM000"]); // Omega Négoce : aucun CA déclaré

function enrichir(e) {
  const imports = importsMensuels(e);
  const scores = trajectoire(e);
  const noeuds = e.network_nodes;
  const etrangers = noeuds.filter((n) => n.type === "Fournisseur étranger");
  const acheteurs = noeuds.filter((n) => n.type === "Acheteur public");
  const locaux = noeuds.filter((n) => n.type === "Fournisseur local");
  const transporteurs = noeuds.filter((n) => n.type === "Transporteur");
  const clients = noeuds.filter((n) => n.type === "Client");
  const forteHausse = e.sinda_import_variance_pct >= 100;
  const operations = [];
  let seq = 0;
  const op = (o) => operations.push({ id: `${e.mf}-${String(++seq).padStart(4, "0")}`, ...o });

  // SINDA : déclarations d'importation. Les fournisseurs signalés n'apparaissent
  // qu'au moment de la hausse (nouveaux fournisseurs).
  MOIS.forEach((mois, i) => {
    if (!imports[i]) return;
    const actifs = etrangers.filter((f) => !(f.risk_flag && forteHausse) || i >= 9);
    const liste = actifs.length ? actifs : etrangers;
    const poids = liste.map((f) => (f.risk_flag && i >= 9 ? 3 : 1) * bruit(0.3));
    repartir(imports[i], poids).forEach((montant, k) => {
      const f = liste[k];
      const nbDeclarations = montant > 150000 ? 2 : 1;
      repartir(montant, Array.from({ length: nbDeclarations }, () => bruit(0.3))).forEach((m) => {
        const sousEvalue = e.mf === "1000002CAM000" && f.risk_flag;
        op({
          date: jour(mois), mois, source: "SINDA", type_operation: "Déclaration d'importation",
          contrepartie_id: f.id, contrepartie: f.label, contrepartie_type: f.type, contrepartie_signalee: f.risk_flag,
          pays: PAYS[f.id] ?? "Autre", montant_dt: m,
          circuit: f.risk_flag ? (alea() < 0.5 ? "Orange" : "Rouge") : e.segment === "CONFIANCE" ? "Vert" : alea() < 0.7 ? "Vert" : "Orange",
          reference: `${mois.slice(0, 4)}/${300 + Math.floor(alea() * 200)}/00${Math.floor(10000 + alea() * 89999)}-00${1 + Math.floor(alea() * 4)}`,
          observation: sousEvalue ? "Valeur unitaire inférieure au prix de référence" : null
        });
      });
    });
  });

  // ADEB : paiements de marchés publics
  if (e.adeb_contracts_val_dt && acheteurs.length) {
    const moisPaiement = MOIS.map((_, i) => i).filter(() => alea() < 0.55);
    const retenus = moisPaiement.length >= 3 ? moisPaiement : [2, 5, 9, 11];
    repartir(e.adeb_contracts_val_dt, retenus.map(() => bruit(0.5))).forEach((montant, k) => {
      const a = acheteurs[k % acheteurs.length];
      const mois = MOIS[retenus[k]];
      op({
        date: jour(mois), mois, source: "ADEB", type_operation: "Paiement de marché public",
        contrepartie_id: a.id, contrepartie: a.label, contrepartie_type: a.type, contrepartie_signalee: a.risk_flag,
        pays: "Tunisie", montant_dt: montant, circuit: null,
        reference: `ORD-${mois.slice(0, 4)}-${String(Math.floor(alea() * 9999)).padStart(4, "0")}`,
        observation: e.mf === "1000003DAM000" ? "Retenue à la source TVA 25 % non reversée" : null
      });
    });
  }

  // Plateforme TJ / El-Factoura : factures reçues des fournisseurs locaux et transporteurs
  MOIS.forEach((mois, i) => {
    [...locaux, ...transporteurs].forEach((f) => {
      const nouveau = f.risk_flag && forteHausse && i < 9;
      if (nouveau || alea() < 0.35) return;
      const base = f.type === "Transporteur" ? 9000 : 42000;
      op({
        date: jour(mois), mois, source: "TJ", type_operation: f.type === "Transporteur" ? "Facture reçue (transport)" : "Facture reçue",
        contrepartie_id: f.id, contrepartie: f.label, contrepartie_type: f.type, contrepartie_signalee: f.risk_flag,
        pays: "Tunisie", montant_dt: arrondi(base * bruit(0.5) * (f.risk_flag && i >= 9 ? 2.5 : 1)), circuit: null,
        reference: `TJ-${mois.replace("-", "")}-${String(Math.floor(alea() * 999999)).padStart(6, "0")}`,
        observation: f.risk_flag ? "Fournisseur non vérifié sur la Plateforme TJ" : null
      });
    });
  });

  // Plateforme TJ : achats déclarés par les clients (retenue à la source). Pour Omega
  // Négoce, ces montants constituent l'écart de recoupement.
  if (clients.length) {
    const total = e.recoupment_gap_dt;
    const poids = [];
    const cles = [];
    MOIS.forEach((mois, i) => clients.forEach((c) => { poids.push(bruit(0.4)); cles.push([mois, c]); }));
    repartir(total, poids).forEach((montant, k) => {
      const [mois, c] = cles[k];
      op({
        date: jour(mois), mois, source: "TJ", type_operation: "Achat déclaré par un client (retenue à la source)",
        contrepartie_id: c.id, contrepartie: c.label, contrepartie_type: c.type, contrepartie_signalee: c.risk_flag,
        pays: "Tunisie", montant_dt: montant, circuit: null,
        reference: `RS-${mois.replace("-", "")}-${String(Math.floor(alea() * 999999)).padStart(6, "0")}`,
        observation: "Montant absent du CA déclaré"
      });
    });
  }

  // RAFIK : arriérés de Delta Trade
  if (e.mf === "1000004EAM000") {
    repartir(85000, [1, 1.4, 1.2]).forEach((montant, k) => {
      const mois = MOIS[[4, 7, 10][k]];
      op({
        date: jour(mois), mois, source: "RAFIK", type_operation: "Arriéré fiscal constaté",
        contrepartie_id: "RECETTE-SOUSSE", contrepartie: "Recette des finances de Sousse", contrepartie_type: "Administration",
        contrepartie_signalee: false, pays: "Tunisie", montant_dt: montant, circuit: null,
        reference: `RAF-${mois.replace("-", "")}-${String(Math.floor(alea() * 9999)).padStart(4, "0")}`,
        observation: "Titre de recouvrement émis"
      });
    });
  }

  operations.sort((a, b) => a.date.localeCompare(b.date));

  // Historique mensuel (déclaré vs observé)
  const baseImports = imports.slice(0, 9).reduce((a, b) => a + b, 0) / 9;
  const caBase = CA_NUL.has(e.mf) ? 0 : e.mf === "1000003DAM000" ? 610000 / 12 : Math.max(baseImports * 1.45, 40000);
  // Écart de recoupement mensuel : l'écart annuel réparti selon l'intensité du risque du mois
  const ecarts = e.recoupment_gap_dt ? repartir(e.recoupment_gap_dt, scores.map((sc) => sc * sc)) : MOIS.map(() => 0);
  const segmentDuMois = (sc) =>
    e.segment === "CONFIANCE" && sc < 15 ? "CONFIANCE" : sc >= 70 ? "PRIORITAIRE" : sc >= 40 ? "SURVEILLANCE" : "NORMAL";
  const historique_mensuel = MOIS.map((mois, i) => {
    const deDuMois = operations.filter((o) => o.mois === mois);
    const somme = (f) => deDuMois.filter(f).reduce((a, o) => a + o.montant_dt, 0);
    const dormant = i < (DORMANT_JUSQUA[e.mf] ?? -1);
    const deposee = !(NON_DEPOSEES[e.mf] ?? []).includes(i);
    // Croissance légitime (Zeta) : le CA suit les imports
    const suitImports = e.segment === "NORMAL" || e.segment === "CONFIANCE";
    const ca = !deposee || dormant ? 0 : suitImports && imports[i] ? imports[i] * 1.45 * bruit(0.05) : caBase * bruit(0.06);
    return {
      mois,
      score: scores[i],
      segment: segmentDuMois(scores[i]),
      ecart_recoupement_dt: ecarts[i],
      declaration_deposee: deposee,
      ca_declare_dt: arrondi(ca),
      imports_sinda_dt: imports[i],
      paiements_adeb_dt: somme((o) => o.source === "ADEB"),
      factures_tj_dt: somme((o) => o.source === "TJ"),
      arrieres_rafik_dt: somme((o) => o.source === "RAFIK")
    };
  });

  return { ...e, historique_mensuel, operations };
}

// Contrôles et décisions passés (historique de l'entreprise)
const CONTROLES = {
  "1000007HAM000": [{ date: "2024-05-14", type: "Contrôle A Posteriori", resultat: "Clôturé sans redressement", montant_redresse_dt: 0 }],
  "1000031SAM000": [{ date: "2023-11-02", type: "Vérification approfondie", resultat: "Clôturé sans redressement", montant_redresse_dt: 0 }],
  "1000004EAM000": [{ date: "2022-03-21", type: "Demande d'Information", resultat: "Sans réponse, dossier transmis à RAFIK", montant_redresse_dt: 0 }],
  "1000002CAM000": [{ date: "2024-09-10", type: "Contrôle A Posteriori", resultat: "Redressement mineur (valeur en douane)", montant_redresse_dt: 38000 }],
  "1000006GAM000": [{ date: "2025-02-17", type: "Demande d'Information", resultat: "Hausse des imports justifiée par un nouveau marché", montant_redresse_dt: 0 }]
};

// Sessions du copilote (historique des conversations, par date et entreprise)
const SESSIONS = [
  { id: "S-0007", date: "2026-08-28", mf: "1000001BAM000", entreprise: "Alpha SARL", titre: "Origine de la hausse des imports SINDA" },
  { id: "S-0006", date: "2026-08-27", mf: "1000008JAM000", entreprise: "Omega Négoce SUARL", titre: "Clients déclarant des achats sans CA correspondant" },
  { id: "S-0005", date: "2026-08-21", mf: "1000003DAM000", entreprise: "Gamma Travaux SA", titre: "Paiements ADEB et retenue TVA 25 %" },
  { id: "S-0004", date: "2026-08-12", mf: "1000002CAM000", entreprise: "Beta Import SUARL", titre: "Écart de valeur en douane, articles NDP 8516" },
  { id: "S-0003", date: "2026-07-30", mf: "1000006GAM000", entreprise: "Zeta Industries SA", titre: "Croissance légitime, justification du CA" },
  { id: "S-0002", date: "2026-07-18", mf: "1000007HAM000", entreprise: "Eta Pharma SA", titre: "Éligibilité au Circuit Vert" }
];

const donnees = JSON.parse(fs.readFileSync(FICHIER, "utf8"));
donnees.meta.mois_couverts = MOIS;
donnees.meta.sessions_copilote = SESSIONS;
donnees.entreprises = donnees.entreprises.map((brut) => {
  const { historique_mensuel, operations, controles_passes, ...e } = brut;
  return { ...enrichir(e), controles_passes: CONTROLES[e.mf] ?? [] };
});
fs.writeFileSync(FICHIER, JSON.stringify(donnees, null, 2) + "\n");

const nbOps = donnees.entreprises.reduce((a, e) => a + e.operations.length, 0);
console.log(`${donnees.entreprises.length} entreprises, ${nbOps} opérations, ${MOIS.length} mois d'historique → ${path.relative(process.cwd(), FICHIER)}`);
