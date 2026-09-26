// Page d'une entreprise (design_references/reference 2). Le copilote occupe la colonne de droite.
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ActionIcon, Anchor, Badge, Breadcrumbs, CloseButton, Code, Group, Paper, SegmentedControl, Text, Title, Tooltip } from "@mantine/core";
import { ChevronRight, Star } from "lucide-react";
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
  { id: "12", court: "12 mois", libelle: "12 derniers mois", valeur: null },
  { id: "6", court: "6 mois", libelle: "6 derniers mois", valeur: { debut: MOIS.at(-6), fin: MOIS.at(-1) } },
  { id: "3", court: "3 mois", libelle: "3 derniers mois", valeur: { debut: MOIS.at(-3), fin: MOIS.at(-1) } },
  { id: "1", court: fmtMoisIso(MOIS.at(-1)), libelle: `${fmtMoisIso(MOIS.at(-1))} seulement`, valeur: { debut: MOIS.at(-1), fin: MOIS.at(-1) } }
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
    <div className="@container flex flex-col gap-5 px-6 py-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <Breadcrumbs separator={<ChevronRight size={12} />} fz="xs">
            <Anchor component={Link} to="/" size="xs" c="dimmed">Entreprises</Anchor>
            <Text size="xs" c="dimmed" truncate maw={260}>{e.company_name}</Text>
          </Breadcrumbs>
          <Group gap={10} wrap="nowrap" className="min-w-0">
            <Title order={1} fz={24} lh={1.2} className="truncate" title={e.company_name}>{e.company_name}</Title>
            <Pastille segment={e.segment} taille="lg" />
            <Tooltip label={suivie ? "Ne plus suivre ce dossier" : "Suivre ce dossier"}>
              <ActionIcon onClick={() => basculerFavori(e.mf)} aria-pressed={suivie} aria-label={suivie ? "Ne plus suivre" : "Suivre ce dossier"}>
                <Star size={17} fill={suivie ? "var(--seg-surv)" : "none"} stroke={suivie ? "var(--seg-surv)" : "currentColor"} />
              </ActionIcon>
            </Tooltip>
          </Group>
          <Group gap={8} wrap="nowrap" className="min-w-0">
            <Code fz={12}>{e.company_id}</Code>
            <Text size="sm" c="dimmed" truncate title={e.sector_nacef}>NAT {e.sector_nacef}</Text>
            <Text size="sm" c="dimmed">· {e.gouvernorat}</Text>
          </Group>
        </div>
        <Group gap="xs" wrap="wrap">
          {choix === "perso" && (
            <Badge variant="light" size="lg" rightSection={<CloseButton size="xs" onClick={() => setPeriode(null)} aria-label="Revenir à 12 mois" />}>
              {periode.debut === periode.fin ? fmtMoisIso(periode.debut) : `${fmtMoisIso(periode.debut)} → ${fmtMoisIso(periode.fin)}`}
            </Badge>
          )}
          <SegmentedControl size="xs" aria-label="Période analysée" value={choix === "perso" ? "" : choix}
            onChange={(v) => setPeriode(PERIODES.find((p) => p.id === v)?.valeur ?? null)}
            data={PERIODES.map((p) => ({ value: p.id, label: p.court }))} />
          <BoutonCopilote copilote={copilote} />
        </Group>
      </header>

      {e.detail ? (
        <PourquoiScore key={`pourquoi-${e.mf}`} mf={e.mf} detail={e.detail} />
      ) : (
        // Jeu fictif : pas de détail du score, on garde le déclencheur de D
        <div className="rounded-xl border border-bordure bg-carte px-4 py-2.5 text-[13px] text-encre">
          <span className="text-attenue">Déclencheur principal : </span>{e.primary_trigger}
          <span className="text-attenue"> · Action recommandée : </span><span className="font-semibold">{e.recommended_action}</span>
        </div>
      )}

      <DashboardVisualizations key={e.mf} entreprise={e} palette={palette} periode={periode} onPeriode={surPeriode} onSelection={surSelection} />
    </div>
  );
}
