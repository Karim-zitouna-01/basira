// Carte d'indicateur (références 1 et 2) : icône + titre, valeur, variation, mini-courbe éventuelle.
import { forwardRef } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

const TONS = { mauvais: "var(--seg-prio-texte)", bon: "var(--seg-conf-texte)", neutre: "var(--attenue)" };

const CarteKpi = forwardRef(function CarteKpi({ icone: Icone, titre, valeur, unite, variation, onClick, actif, aide }, sparkRef) {
  const Fleche = variation?.sens === "hausse" ? ArrowUpRight : variation?.sens === "baisse" ? ArrowDownRight : Minus;
  const Balise = onClick ? "button" : "div";
  return (
    <Balise
      type={onClick ? "button" : undefined}
      onClick={onClick}
      aria-pressed={onClick ? !!actif : undefined}
      title={aide}
      className={`flex min-w-0 flex-col gap-2 rounded-xl border bg-carte p-4 text-left ${actif ? "border-encre shadow-[0_0_0_1px_var(--encre)]" : "border-bordure"} ${onClick ? "cursor-pointer hover:border-attenue" : ""}`}
    >
      <span className="flex items-center gap-2 text-[13px] font-medium text-encre-2">
        {Icone && <span className="grid size-6 place-items-center rounded-md border border-bordure text-attenue"><Icone size={13} aria-hidden="true" /></span>}
        {titre}
      </span>
      <span className="flex items-end justify-between gap-3">
        <span className="flex min-w-0 flex-col gap-1.5">
          <span className="chiffres text-[22px] font-bold leading-none text-encre">
            {valeur}{unite && <span className="ml-1 text-[13px] font-medium text-attenue">{unite}</span>}
          </span>
          {variation && (
            <span className="flex items-center gap-1 whitespace-nowrap text-[12px] font-semibold" style={{ color: TONS[variation.ton ?? "neutre"] }}>
              <Fleche size={14} aria-hidden="true" />{variation.texte}
            </span>
          )}
        </span>
        {sparkRef && <span ref={sparkRef} className="sparkline block h-[46px] w-[40%] min-w-[80px] max-w-[140px] shrink-0" />}
      </span>
    </Balise>
  );
});

export default CarteKpi;
