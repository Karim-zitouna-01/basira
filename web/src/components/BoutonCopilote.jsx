import { Button } from "@mantine/core";
import { MessageSquare, PanelRightClose } from "lucide-react";

export default function BoutonCopilote({ copilote }) {
  return copilote.ouvert ? (
    <Button variant="default" size="sm" onClick={copilote.basculer} aria-pressed leftSection={<PanelRightClose size={15} />}>Masquer le copilote</Button>
  ) : (
    <Button size="sm" onClick={copilote.basculer} aria-pressed={false} leftSection={<MessageSquare size={15} />}>Copilote IA</Button>
  );
}
