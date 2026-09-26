import { MessageSquare } from "lucide-react";

export default function BoutonCopilote({ copilote }) {
  return (
    <button type="button" onClick={copilote.basculer} aria-pressed={copilote.ouvert}
      className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[13px] font-semibold ${copilote.ouvert ? "border border-bordure bg-carte text-encre" : "bg-action text-action-encre"}`}>
      <MessageSquare size={14} aria-hidden="true" />{copilote.ouvert ? "Masquer le copilote" : "Copilote IA"}
    </button>
  );
}
