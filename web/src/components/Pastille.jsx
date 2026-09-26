import { SEGMENTS } from "../lib/palettes.js";

// Statut de risque : point de couleur + libellé (jamais la couleur seule)
export default function Pastille({ segment, taille = "sm" }) {
  const s = SEGMENTS[segment];
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full font-semibold ${taille === "lg" ? "px-3 py-1 text-[13px]" : "px-2 py-0.5 text-[11.5px]"}`}
      style={{
        color: `var(--seg-${s.jeton}-texte)`,
        background: `color-mix(in srgb, var(--seg-${s.jeton}) 14%, white)`
      }}
    >
      <span className="size-2 rounded-full" style={{ background: `var(--seg-${s.jeton})` }} />
      {s.libelle}
    </span>
  );
}
