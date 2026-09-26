// Barre latérale : identité institutionnelle, recherche rapide, navigation,
// dossiers suivis et consultations récentes (cf. design_references/reference 1).
import { useMemo, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Building2, Clock, Landmark, Palette, Search, Star } from "lucide-react";
import { listerEntreprises, trouverEntreprise } from "../lib/donnees.js";
import { useSuivis } from "../lib/suivis.js";
import { PALETTES, SEGMENTS } from "../lib/palettes.js";

function Section({ titre, icone: Icone, children }) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-1.5 px-2 pb-1 text-[11px] font-semibold uppercase tracking-[0.06em] text-attenue">
        <Icone size={12} aria-hidden="true" />{titre}
      </div>
      {children}
    </div>
  );
}

function LienEntreprise({ mf }) {
  const e = trouverEntreprise(mf);
  if (!e) return null;
  return (
    <NavLink
      to={`/entreprise/${mf}`}
      className={({ isActive }) => `flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px] ${isActive ? "bg-fond-2 font-semibold text-encre" : "text-encre-2 hover:bg-fond-2"}`}
    >
      <span className="size-2 shrink-0 rounded-full" style={{ background: `var(--seg-${SEGMENTS[e.segment].jeton})` }} />
      <span className="truncate">{e.company_name}</span>
    </NavLink>
  );
}

export default function BarreLaterale({ palette, onPalette }) {
  const navigate = useNavigate();
  const { favoris, recents } = useSuivis();
  const [q, setQ] = useState("");
  const toutes = listerEntreprises();
  const resultats = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return [];
    return toutes.filter((e) => `${e.company_name} ${e.company_id}`.toLowerCase().includes(t)).slice(0, 6);
  }, [q, toutes]);

  const ouvrir = (mf) => { setQ(""); navigate(`/entreprise/${mf}`); };

  return (
    <nav className="flex h-full w-[248px] shrink-0 flex-col gap-5 border-r border-bordure bg-carte px-3 py-4" aria-label="Navigation principale">
      <Link to="/" className="flex items-start gap-2.5 px-1">
        <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-encre text-carte"><Landmark size={18} aria-hidden="true" /></span>
        <span className="min-w-0">
          <span className="block text-[14px] font-bold leading-tight text-encre">Poste de l'inspecteur</span>
          <span className="block text-[11px] leading-snug text-attenue">République Tunisienne · Ministère des Finances &amp; Direction Générale des Douanes</span>
        </span>
      </Link>

      <div className="relative">
        <label htmlFor="recherche-rapide" className="sr-only">Rechercher une entreprise</label>
        <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-attenue" aria-hidden="true" />
        <input
          id="recherche-rapide"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && resultats[0]) ouvrir(resultats[0].mf); if (e.key === "Escape") setQ(""); }}
          placeholder="Raison sociale, matricule…"
          className="w-full rounded-md border border-bordure bg-fond py-1.5 pl-8 pr-2 text-[13px] placeholder:text-attenue"
        />
        {resultats.length > 0 && (
          <ul className="absolute inset-x-0 top-full z-20 mt-1 overflow-hidden rounded-md border border-bordure bg-carte shadow-lg">
            {resultats.map((e) => (
              <li key={e.mf}>
                <button type="button" onClick={() => ouvrir(e.mf)} className="flex w-full flex-col px-3 py-2 text-left hover:bg-fond-2">
                  <span className="text-[13px] font-semibold text-encre">{e.company_name}</span>
                  <span className="font-mono text-[11px] text-attenue">{e.company_id}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-col gap-0.5">
        <NavLink
          to="/"
          end
          className={({ isActive }) => `flex items-center justify-between rounded-md px-2 py-1.5 text-[13px] ${isActive ? "bg-fond-2 font-semibold text-encre" : "text-encre-2 hover:bg-fond-2"}`}
        >
          <span className="flex items-center gap-2"><Building2 size={15} aria-hidden="true" />Entreprises</span>
          <span className="chiffres rounded bg-fond-2 px-1.5 text-[11px] text-attenue">{toutes.length}</span>
        </NavLink>
      </div>

      <Section titre="Dossiers suivis" icone={Star}>
        {favoris.length ? favoris.map((mf) => <LienEntreprise key={mf} mf={mf} />) : (
          <p className="px-2 text-[12px] text-attenue">Cliquez l'étoile d'une entreprise pour la suivre.</p>
        )}
      </Section>

      {recents.length > 0 && (
        <Section titre="Consultés récemment" icone={Clock}>
          {recents.map((mf) => <LienEntreprise key={mf} mf={mf} />)}
        </Section>
      )}

      <div className="mt-auto flex flex-col gap-3">
        <label htmlFor="palette" className="flex flex-col gap-1 px-1 text-[11px] font-semibold uppercase tracking-[0.06em] text-attenue">
          <span className="flex items-center gap-1.5"><Palette size={12} aria-hidden="true" />Palette (temporaire)</span>
          <select id="palette" value={palette} onChange={(e) => onPalette(e.target.value)}
            className="rounded-md border border-bordure bg-carte px-2 py-1 text-[12.5px] font-normal normal-case tracking-normal text-encre">
            {PALETTES.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
          </select>
        </label>
        <div className="flex items-center gap-2.5 rounded-lg border border-bordure px-2.5 py-2">
          <span className="grid size-8 place-items-center rounded-full bg-fond-2 text-[12px] font-bold text-encre-2">ID</span>
          <span className="min-w-0">
            <span className="block text-[13px] font-semibold text-encre">Inspecteur (démo)</span>
            <span className="block truncate text-[11.5px] text-attenue">Contrôle A Posteriori · Sfax</span>
          </span>
        </div>
      </div>
    </nav>
  );
}
