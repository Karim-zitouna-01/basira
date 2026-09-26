// Page d'une entreprise (design_references/reference 2). Le copilote occupe la colonne de droite.
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CalendarDays, ChevronRight, Star } from "lucide-react";
import { chargerFiche, meta, trouverEntreprise } from "../lib/donnees.js";
import { useContextePage } from "../lib/contextePage.jsx";
import { basculerFavori, noterConsultation, useSuivis } from "../lib/suivis.js";
import { SEGMENTS } from "../lib/palettes.js";
import { fmtMoisIso } from "../lib/format.js";
import Pastille from "../components/Pastille.jsx";
import BoutonCopilote from "../components/BoutonCopilote.jsx";
import DashboardVisualizations from "../components/DashboardVisualizations.jsx";
import PourquoiScore from "../components/PourquoiScore.jsx";

const MOIS = meta.mois_couverts;
const PERIODES = [
  { id: "12", libelle: "12 derniers mois", valeur: null },
  { id: "6", libelle: "6 derniers mois", valeur: { debut: MOIS.at(-6), fin: MOIS.at(-1) } },
  { id: "3", libelle: "3 derniers mois", valeur: { debut: MOIS.at(-3), fin: MOIS.at(-1) } },
  { id: "1", libelle: `${fmtMoisIso(MOIS.at(-1))} seulement`, valeur: { debut: MOIS.at(-1), fin: MOIS.at(-1) } }
];
const idPeriode = (p) => PERIODES.find((x) => JSON.stringify(x.valeur) === JSON.stringify(p))?.id ?? "perso";

// Fiche complète chargée à la demande (API) ; `undefined` = en cours, `null` = introuvable
function useFiche(mf) {
  const [etat, setEtat] = useState({ mf: null, fiche: undefined, erreur: null });
  useEffect(() => {
    let actif = true;
    chargerFiche(mf).then(
      (fiche) => actif && setEtat({ mf, fiche, erreur: null }),
      (erreur) => actif && setEtat({ mf, fiche: null, erreur: erreur.message })
    );
    return () => { actif = false; };
  }, [mf]);
  return etat.mf === mf ? etat : { mf, fiche: undefined, erreur: null };
}

export default function FicheEntreprise({ copilote, palette }) {
  const { mf } = useParams();
  const { fiche: entreprise, erreur } = useFiche(mf);
  const { setContexte } = useContextePage();
  const { favoris } = useSuivis();
  const [selection, setSelection] = useState(null);
  const [periode, setPeriode] = useState(null);

  useEffect(() => { if (entreprise) noterConsultation(entreprise.mf); setPeriode(null); }, [entreprise]);

  // Ce que le copilote voit : identité, trajectoire et la sélection affichée (période, filtres, indicateurs)
  useEffect(() => {
    if (!entreprise || !selection) return;
    const e = entreprise;
    setContexte({
      page: "fiche_entreprise",
      titre: e.company_name,
      entreprise: {
        mf: e.mf, company_id: e.company_id, company_name: e.company_name, sector_nacef: e.sector_nacef, gouvernorat: e.gouvernorat,
        current_risk_score: e.current_risk_score, risk_status: SEGMENTS[e.segment].libelle, risk_delta_2m: e.risk_delta_2m,
        primary_trigger: e.primary_trigger, recoupment_gap_dt: e.recoupment_gap_dt, recommended_action: e.recommended_action
      },
      historique_score: e.historique_mensuel.map((h) => ({ mois: h.mois, score: h.score, statut: SEGMENTS[h.segment].libelle })),
      controles_passes: e.controles_passes,
      ...selection
    });
  }, [entreprise, selection, setContexte]);

  const surSelection = useCallback((s) => setSelection(s), []);
  const surPeriode = useCallback((p) => setPeriode(p), []);

  if (entreprise === undefined) {
    return <div className="px-6 py-10 text-encre-2">Chargement de la fiche {trouverEntreprise(mf)?.company_name ?? mf}…</div>;
  }
  if (!entreprise) {
    return (
      <div className="px-6 py-10">
        <p className="text-encre-2">{erreur ? `Fiche indisponible : ${erreur}.` : `Aucune entreprise ne correspond au matricule ${mf}.`}</p>
        <Link to="/" className="font-semibold text-action-texte">Retour à la liste des entreprises</Link>
      </div>
    );
  }

  const e = entreprise;
  const suivie = favoris.includes(e.mf);
  const choix = idPeriode(periode);
  return (
    <div className="flex flex-col gap-4 px-6 py-5">
      <header className="flex flex-col gap-3">
        <nav className="flex items-center gap-1 text-[12.5px] text-attenue" aria-label="Fil d'Ariane">
          <Link to="/" className="hover:text-encre">Entreprises</Link>
          <ChevronRight size={13} aria-hidden="true" />
          <span className="text-encre-2">{e.company_name}</span>
        </nav>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-[21px] font-bold leading-tight text-encre">{e.company_name}</h1>
              <Pastille segment={e.segment} />
              <button type="button" onClick={() => basculerFavori(e.mf)} aria-pressed={suivie}
                className="flex items-center gap-1 rounded-md border border-bordure px-2 py-0.5 text-[12px] text-encre-2 hover:border-attenue">
                <Star size={13} fill={suivie ? "var(--seg-surv)" : "none"} stroke={suivie ? "var(--seg-surv)" : "currentColor"} aria-hidden="true" />
                {suivie ? "Suivie" : "Suivre"}
              </button>
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[12.5px] text-encre-2">
              <span className="font-mono">{e.company_id}</span>
              <span>NAT {e.sector_nacef}</span>
              <span>{e.gouvernorat}</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label htmlFor="periode" className="flex items-center gap-1.5 rounded-md border border-bordure bg-carte px-2.5 py-1.5 text-[12.5px] text-encre-2">
              <CalendarDays size={14} aria-hidden="true" />
              <span className="sr-only">Période analysée</span>
              <select id="periode" value={choix} onChange={(ev) => setPeriode(PERIODES.find((p) => p.id === ev.target.value)?.valeur ?? null)}
                className="bg-transparent font-semibold text-encre outline-none">
                {PERIODES.map((p) => <option key={p.id} value={p.id}>{p.libelle}</option>)}
                {choix === "perso" && <option value="perso">{periode.debut === periode.fin ? fmtMoisIso(periode.debut) : `${fmtMoisIso(periode.debut)} → ${fmtMoisIso(periode.fin)}`}</option>}
              </select>
            </label>
            <BoutonCopilote copilote={copilote} />
          </div>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-1 rounded-xl border border-bordure bg-carte px-4 py-2.5 text-[13px]">
          <span className="min-w-0 text-encre"><span className="text-attenue">Déclencheur principal : </span>{e.primary_trigger}</span>
          <span className="text-encre"><span className="text-attenue">Action recommandée : </span><span className="font-semibold">{e.recommended_action}</span>
            <span className="text-attenue"> · la décision appartient à l'inspecteur</span></span>
        </div>
      </header>

      {e.detail && <PourquoiScore key={`pourquoi-${e.mf}`} mf={e.mf} detail={e.detail} />}

      <DashboardVisualizations key={e.mf} entreprise={e} palette={palette} periode={periode} onPeriode={surPeriode} onSelection={surSelection} />
    </div>
  );
}
