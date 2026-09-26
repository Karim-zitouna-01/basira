// Filtre à choix multiples : valeurs et effectifs issus des groupes crossfilter
// (les effectifs tiennent compte des autres filtres actifs).
import { Button, Checkbox, Group, Popover, ScrollArea, Stack, Text, UnstyledButton } from "@mantine/core";
import { ChevronDown } from "lucide-react";

export default function FiltreMenu({ icone: Icone, libelle, options, selection, onChange }) {
  const basculer = (v) => onChange(selection.includes(v) ? selection.filter((x) => x !== v) : [...selection, v]);
  const actif = selection.length > 0;
  const resume = actif ? (selection.length === 1 ? options.find((o) => o.valeur === selection[0])?.libelle ?? selection[0] : `${selection.length}`) : null;
  return (
    <Popover position="bottom-start" shadow="md" width={290} withinPortal>
      <Popover.Target>
        <Button variant={actif ? "light" : "default"} size="sm" leftSection={Icone && <Icone size={14} />} rightSection={<ChevronDown size={14} />}
          fw={actif ? 600 : 500} maw={260} styles={{ label: { overflow: "hidden", textOverflow: "ellipsis" } }}>
          {libelle}{resume && ` : ${resume}`}
        </Button>
      </Popover.Target>
      <Popover.Dropdown p={6}>
        <ScrollArea.Autosize mah={320} type="auto">
          <Stack gap={0}>
            {options.map((o) => {
              const coche = selection.includes(o.valeur);
              return (
                <UnstyledButton key={o.valeur} onClick={() => basculer(o.valeur)} disabled={!o.effectif && !coche}
                  className="rounded-md px-2 py-1.5 hover:bg-fond-2 disabled:opacity-40">
                  <Group gap={8} wrap="nowrap">
                    <Checkbox checked={coche} readOnly size="xs" tabIndex={-1} />
                    {o.pastille && <span className="size-2 shrink-0 rounded-full" style={{ background: o.pastille }} />}
                    <Text size="sm" className="min-w-0 flex-1" truncate>{o.libelle}</Text>
                    <Text size="xs" c="dimmed" className="chiffres">{o.effectif.toLocaleString("fr-FR")}</Text>
                  </Group>
                </UnstyledButton>
              );
            })}
          </Stack>
        </ScrollArea.Autosize>
        {actif && <Button variant="subtle" size="compact-sm" fullWidth mt={4} onClick={() => onChange([])}>Effacer ce filtre</Button>}
      </Popover.Dropdown>
    </Popover>
  );
}
