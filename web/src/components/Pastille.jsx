import { Badge } from "@mantine/core";
import { SEGMENTS } from "../lib/palettes.js";
import { COULEURS_SEGMENT } from "../lib/theme.js";

// Statut de risque : point de couleur + libellé (jamais la couleur seule)
export default function Pastille({ segment, taille = "sm" }) {
  const s = SEGMENTS[segment];
  return (
    <Badge variant="light" color={COULEURS_SEGMENT[segment]} size={taille === "lg" ? "md" : "sm"}
      leftSection={<span className="block size-1.5 rounded-full" style={{ background: COULEURS_SEGMENT[segment] }} />}
      styles={{ root: { flexShrink: 0, overflow: "visible" }, label: { color: `var(--seg-${s.jeton}-texte)`, overflow: "visible" } }}>
      {s.libelle}
    </Badge>
  );
}
