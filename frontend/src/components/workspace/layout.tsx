import { useState, type ReactNode, type CSSProperties } from "react";
import {
  ArrowLeft,
  Building2,
  ChevronDown,
  FileText,
  HelpCircle,
  Home,
  MessageSquare,
  Plus,
  MoreHorizontal,
  Minimize2,
  Sun,
  Moon,
} from "lucide-react";
import { LayoutGroup } from "motion/react";
import { useTheme } from "next-themes";
import {
  Sidebar,
  SidebarProvider,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarMenuAction,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Brand } from "@/components/brand";
import { useWorkspace } from "@/lib/workspace";
import { store, shortTitle, analysisHref } from "@/lib/api";
import { AssistantProvider, useAssistant } from "@/lib/assistant";
import { ChatActions } from "./chat-actions";
import { AssistantFrame } from "./assistant-frame";
import { AssistantToggle } from "./floating-assistant";
const navigation = [
  ["home", "Inicio", Home],
  ["my-business", "Mi negocio", Building2],
] as const;
export function Layout({ children }: { children: ReactNode }) {
  const { workspace } = useWorkspace();
  const [width, setWidth] = useState(() =>
    Number(store.get("dr-sidebar-width", 256)),
  );
  return (
    <AssistantProvider key={workspace.business?.id || "empty"}>
      <SidebarProvider
        className="workspace-shell"
        style={
          {
            "--sidebar-width": `${Math.max(216, Math.min(width, 420))}px`,
          } as CSSProperties
        }
      >
        <Navigation width={width} setWidth={setWidth} />
        <LayoutGroup>
          <AssistantFrame header={<Topbar />}>{children}</AssistantFrame>
        </LayoutGroup>
      </SidebarProvider>
    </AssistantProvider>
  );
}
function Navigation({
  width,
  setWidth,
}: {
  width: number;
  setWidth: (v: number) => void;
}) {
  const { workspace, listing, route } = useWorkspace(),
    { isMobile, setOpenMobile, state } = useSidebar();
  const assistant = useAssistant();
  const close = () => {
    if (isMobile) setOpenMobile(false);
  };
  const activeChat = listing.conversations.find(
    (c) => route === `chat/${c.id}`,
  );
  const recent = listing.conversations.slice(0, 6);
  const chatRows =
    activeChat && !recent.includes(activeChat)
      ? [...recent, activeChat]
      : recent;
  const recentReports = workspace.analyses.slice(0, 5);
  const activeReport = workspace.analyses.find((item) =>
    [`analysis/${item.id}`, `report/${item.id}`].includes(route),
  );
  const reportRows =
    activeReport && !recentReports.includes(activeReport)
      ? [...recentReports, activeReport]
      : recentReports;
  return (
    <Sidebar variant="inset" collapsible="icon">
      <SidebarHeader className="gap-4 p-3">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <a
                href="#home"
                onClick={close}
                className="gap-2.5"
                aria-label="Decision Room, inicio"
              >
                <Brand />
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  className="h-10"
                  aria-label={workspace.business?.name || "Mi espacio"}
                >
                  <Building2 />
                  <span className="truncate">
                    {workspace.business?.name || "Mi espacio"}
                  </span>
                  <ChevronDown className="ml-auto" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-60">
                <DropdownMenuItem asChild>
                  <a href="#businesses" onClick={close}>
                    Cambiar de negocio
                  </a>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <a href="#business-new" onClick={close}>
                    Crear otro negocio
                  </a>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu>
            {navigation.map(([key, label, Icon]) => (
              <SidebarMenuItem key={key}>
                <SidebarMenuButton
                  asChild
                  isActive={
                    route === key ||
                    (key === "my-business" &&
                      ["files", "business"].includes(route))
                  }
                  tooltip={label}
                >
                  <a
                    href={`#${key}`}
                    onClick={close}
                    aria-label={label}
                    aria-current={route === key ? "page" : undefined}
                  >
                    <Icon />
                    <span>{label}</span>
                  </a>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
        <SidebarGroup role="region" aria-label="Chats">
          <SidebarGroupLabel
            className="workspace-section-label workspace-chat-heading"
            aria-label="Chats"
          >
            <span>
              <a
                href="#chats"
                onClick={close}
                aria-label="Chats"
                className="hover:text-foreground"
              >
                Chats
              </a>
            </span>
            <Button asChild variant="ghost" size="icon" className="ml-auto size-7">
              <a href="#ask" aria-label="Nuevo chat" title="Nuevo chat" onClick={() => {
                assistant?.newConversation("page");
                close();
              }}>
                <Plus className="size-4" />
              </a>
            </Button>
          </SidebarGroupLabel>
          <SidebarMenu>
            {chatRows.map((chat) => (
              <SidebarMenuItem key={chat.id}>
                <SidebarMenuButton
                  asChild
                  isActive={route === `chat/${chat.id}`}
                  tooltip={chat.title}
                >
                  <a
                    href={`#chat/${chat.id}`}
                    onClick={close}
                    aria-label={chat.title}
                    aria-current={
                      route === `chat/${chat.id}` ? "page" : undefined
                    }
                  >
                    <MessageSquare />
                    <span>{shortTitle(chat.title)}</span>
                  </a>
                </SidebarMenuButton>
                <ChatActions chat={chat} onOpenPanel={close}>
                  <SidebarMenuAction
                    showOnHover
                    aria-label={`Opciones de ${chat.title}`}
                  >
                    <MoreHorizontal />
                  </SidebarMenuAction>
                </ChatActions>
              </SidebarMenuItem>
            ))}
            {listing.conversations.length > 6 && (
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="Ver todos los chats">
                  <a
                    href="#chats"
                    onClick={close}
                    aria-label="Ver todos los chats"
                  >
                    <MoreHorizontal />
                    <span>Ver todos</span>
                  </a>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )}
          </SidebarMenu>
          {!chatRows.length && (
            <p className="px-2 py-1 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
              Todavía no hay chats
            </p>
          )}
        </SidebarGroup>
        <SidebarGroup role="region" aria-label="Informes">
          <SidebarGroupLabel
            className="workspace-section-label"
            aria-label="Informes"
          >
            <span>
              <a
                href="#reports"
                onClick={close}
                aria-label="Informes"
                className="hover:text-foreground"
              >
                Informes
              </a>
            </span>
          </SidebarGroupLabel>
          <SidebarMenu>
            {reportRows.map((item) => (
              <SidebarMenuItem key={item.id}>
                <SidebarMenuButton
                  asChild
                  tooltip={item.title}
                  isActive={item === activeReport}
                >
                  <a
                    href={analysisHref(item)}
                    onClick={close}
                    aria-label={item.title}
                    aria-current={
                      [`analysis/${item.id}`, `report/${item.id}`].includes(
                        route,
                      )
                        ? "page"
                        : undefined
                    }
                  >
                    <FileText />
                    <span>{shortTitle(item.title)}</span>
                  </a>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
            {workspace.analyses.length > 5 && (
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip="Ver todos los informes">
                  <a
                    href="#reports"
                    onClick={close}
                    aria-label="Ver todos los informes"
                  >
                    <MoreHorizontal />
                    <span>Ver todos</span>
                  </a>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )}
          </SidebarMenu>
          {!reportRows.length && (
            <p className="px-2 py-1 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
              Todavía no hay informes
            </p>
          )}
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="p-3">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="Cómo funciona">
              <a href="#how" onClick={close} aria-label="Cómo funciona">
                <HelpCircle />
                <span>Cómo funciona</span>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <div className="workspace-footer-note px-2 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
          Espacio local · Versión de pruebas
        </div>
      </SidebarFooter>
      {!isMobile && state === "expanded" && (
        <div
          role="separator"
          aria-label="Anchura de la barra lateral"
          aria-orientation="vertical"
          aria-valuemin={216}
          aria-valuemax={420}
          aria-valuenow={Math.round(width)}
          tabIndex={0}
          className="absolute inset-y-0 right-0 z-20 w-1 cursor-col-resize hover:bg-border focus-visible:bg-ring"
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId);
            e.preventDefault();
          }}
          onPointerMove={(e) => {
            if (e.currentTarget.hasPointerCapture(e.pointerId)) {
              const value = Math.max(
                216,
                Math.min(e.clientX, 420, innerWidth * 0.4),
              );
              setWidth(value);
              store.set("dr-sidebar-width", value);
            }
          }}
          onKeyDown={(e) => {
            if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
              e.preventDefault();
              const value = Math.max(
                216,
                Math.min(
                  e.key === "Home"
                    ? 216
                    : e.key === "End"
                      ? 420
                      : width + (e.key === "ArrowRight" ? 16 : -16),
                  420,
                ),
              );
              setWidth(value);
              store.set("dr-sidebar-width", value);
            }
          }}
        />
      )}
    </Sidebar>
  );
}
function Topbar() {
  const { route } = useWorkspace();
  const assistant = useAssistant();
  const { theme, setTheme } = useTheme();
  const back = route.startsWith("chat-report/")
    ? {
        href: `#chat/${route.split("/")[1]}`,
        label: "Volver a la conversación",
      }
    : route === "ask" || route.startsWith("chat/")
      ? { href: "#chats", label: "Volver a conversaciones" }
      : route.startsWith("report/") || route.startsWith("analysis/")
        ? { href: "#reports", label: "Volver a informes" }
        : null;
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 px-4 sm:px-6">
      <SidebarTrigger aria-label="Abrir o cerrar navegación" />
      {back && (
        <Button asChild variant="ghost" size="icon" className="rounded-full">
          <a href={back.href} aria-label={back.label} title={back.label}>
            <ArrowLeft />
          </a>
        </Button>
      )}
      <div className="ml-auto flex items-center gap-2">
        {route.startsWith("chat/") && assistant && (
          <Button
            variant="ghost"
            size="icon"
            aria-label="Reducir conversación"
            title="Reducir conversación"
            onClick={() => assistant.reduceConversation(route.split("/")[1])}
          >
            <Minimize2 />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          aria-label={theme === "dark" ? "Usar tema claro" : "Usar tema oscuro"}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? <Sun /> : <Moon />}
        </Button>
        <AssistantToggle />
      </div>
    </header>
  );
}
