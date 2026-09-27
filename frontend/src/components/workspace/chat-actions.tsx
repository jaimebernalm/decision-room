import type { ReactNode } from "react";
import { PanelRightOpen, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAssistant } from "@/lib/assistant";
import { useWorkspace } from "@/lib/workspace";
import type { Chat } from "@/lib/types";

export function ChatActions({
  chat,
  children,
  onOpenPanel,
}: {
  chat: Chat;
  children: ReactNode;
  onOpenPanel?: () => void;
}) {
  const assistant = useAssistant();
  const { removeChat } = useWorkspace();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          disabled={!assistant}
          onSelect={() => {
            assistant?.openConversation(chat.id);
            onOpenPanel?.();
          }}
        >
          <PanelRightOpen /> Abrir en panel
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => removeChat(chat)}>
          <Trash2 /> Eliminar conversación
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
