// Pastille de filtre avec menu déroulant : valeurs et effectifs issus des groupes crossfilter
// (les effectifs tiennent compte des autres filtres actifs).
import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";

export default function FiltreMenu({ icone: Icone, libelle, options, selection, onChange }) {
  const [ouvert, setOuvert] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!ouvert) return;
    const fermer = (e) => { if (!ref.current?.contains(e.target)) setOuvert(false); };
    const echap = (e) => e.key === "Escape" && setOuvert(false);
    document.addEventListener("mousedown", fermer);
    document.addEventListener("keydown", echap);
    return () => { document.removeEventListener("mousedown", fermer); document.removeEventListener("keydown", echap); };
  }, [ouvert]);

  const basculer = (v) => onChange(selection.includes(v) ? selection.filter((x) => x !== v) : [...selection, v]);
  const actif = selection.length > 0;
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOuvert((o) => !o)}
        aria-expanded={ouvert}
        className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[12.5px] ${actif ? "border-encre bg-carte font-semibold text-encre" : "border-bordure bg-carte text-encre-2 hover:border-attenue"}`}
      >
        {Icone && <Icone size={13} aria-hidden="true" />}
        {libelle}{actif && ` : ${selection.length === 1 ? options.find((o) => o.valeur === selection[0])?.libelle ?? selection[0] : selection.length}`}
        <ChevronDown size={13} aria-hidden="true" />
      </button>
      {ouvert && (
        <div className="absolute left-0 top-full z-30 mt-1 w-[280px] rounded-lg border border-bordure bg-carte p-1 shadow-lg">
          {options.map((o) => {
            const coche = selection.includes(o.valeur);
            return (
              <button key={o.valeur} type="button" onClick={() => basculer(o.valeur)} disabled={!o.effectif && !coche}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[12.5px] text-encre-2 hover:bg-fond-2 disabled:opacity-40">
                <span className={`grid size-4 shrink-0 place-items-center rounded border ${coche ? "border-encre bg-encre text-carte" : "border-bordure"}`}>{coche && <Check size={11} />}</span>
                {o.pastille && <span className="size-2 shrink-0 rounded-full" style={{ background: o.pastille }} />}
                <span className="min-w-0 flex-1 truncate">{o.libelle}</span>
                <span className="chiffres text-[11.5px] text-attenue">{o.effectif}</span>
              </button>
            );
          })}
          {actif && (
            <button type="button" onClick={() => onChange([])} className="mt-1 w-full rounded-md px-2 py-1.5 text-left text-[12px] font-semibold text-action-texte hover:bg-fond-2">
              Effacer ce filtre
            </button>
          )}
        </div>
      )}
    </div>
  );
}
