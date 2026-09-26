// Carte d'indicateur : icône + titre, valeur, variation, mini-courbe éventuelle (DC.js, via la ref).
import { forwardRef } from "react";
import { Group, Paper, Text, ThemeIcon, Tooltip, UnstyledButton } from "@mantine/core";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

const TONS = { mauvais: "var(--seg-prio-texte)", bon: "var(--seg-conf-texte)", neutre: "var(--attenue)" };

const CarteKpi = forwardRef(function CarteKpi({ icone: Icone, titre, valeur, unite, variation, onClick, actif, aide }, sparkRef) {
  const Fleche = variation?.sens === "hausse" ? ArrowUpRight : variation?.sens === "baisse" ? ArrowDownRight : Minus;
  const contenu = (
    <Paper withBorder radius="lg" p="md" className={`h-full ${actif ? "!border-[var(--mantine-color-basira-6)] shadow-[0_0_0_1px_var(--mantine-color-basira-6)]" : ""} ${onClick ? "transition-colors hover:!border-[var(--attenue)]" : ""}`}>
      <Group gap={8} wrap="nowrap" mb={10}>
        {Icone && <ThemeIcon variant="light" color="ardoise" size={26} radius="md"><Icone size={14} /></ThemeIcon>}
        <Text size="sm" c="dimmed" fw={500} truncate>{titre}</Text>
      </Group>
      <Group justify="space-between" align="flex-end" wrap="nowrap" gap="sm">
        <div className="min-w-0">
          <Text fz={26} fw={700} lh={1} className="chiffres whitespace-nowrap">
            {valeur}{unite && <Text span size="sm" c="dimmed" fw={500} ml={4}>{unite}</Text>}
          </Text>
          {variation && (
            <Group gap={3} mt={8} wrap="nowrap" style={{ color: TONS[variation.ton ?? "neutre"] }}>
              <Fleche size={14} aria-hidden="true" />
              <Text size="xs" fw={600} c="inherit" className="whitespace-nowrap">{variation.texte}</Text>
            </Group>
          )}
        </div>
        {sparkRef && <span ref={sparkRef} className="sparkline block h-[46px] w-[42%] min-w-[80px] max-w-[150px] shrink-0" />}
      </Group>
    </Paper>
  );
  const avecAide = aide ? <Tooltip label={aide}>{onClick ? <UnstyledButton onClick={onClick} aria-pressed={!!actif} className="h-full w-full text-left">{contenu}</UnstyledButton> : <div className="h-full">{contenu}</div>}</Tooltip> : null;
  if (avecAide) return avecAide;
  return onClick ? <UnstyledButton onClick={onClick} aria-pressed={!!actif} className="h-full w-full text-left">{contenu}</UnstyledButton> : contenu;
});

export default CarteKpi;
