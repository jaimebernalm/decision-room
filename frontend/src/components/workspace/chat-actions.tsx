import { translate as tr, useLanguage } from "@/lib/i18n";
import type { ReactNode } from "react";
import { PanelRightOpen, Pin, PinOff, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAction } from "@/lib/hooks";
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
  useLanguage();
  const assistant = useAssistant();
  const { removeChat, refresh } = useWorkspace();
  const action = useAction();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          disabled={action.busy}
          onSelect={() => {
            void action.run(async () => {
              try {
                await api(`/api/chats/${chat.id}/pin`, {
                  business_id: chat.business_id,
                  pinned: !chat.pinned_at,
                });
                if (action.isMounted()) refresh();
              } catch (error) {
                if (action.isMounted()) toast.error((error as Error).message);
              }
            });
          }}
        >
          {chat.pinned_at ? <PinOff /> : <Pin />}
          {chat.pinned_at ? tr("Desfijar chat") : tr("Fijar chat")}
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={!assistant}
          onSelect={() => {
            assistant?.openConversation(chat.id);
            onOpenPanel?.();
          }}
        >
          <PanelRightOpen />
          {tr(" Abrir en panel")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => removeChat(chat)}>
          <Trash2 />
          {tr(" Eliminar chat")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
