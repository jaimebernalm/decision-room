import { translate as tr, useLanguage } from "@/lib/i18n";
import { useState, type ReactNode, type CSSProperties } from "react";
import {
  ArrowLeft,
  Building2,
  FileText,
  Home,
  MessageSquare,
  Plus,
  MoreHorizontal,
  Minimize2,
} from "lucide-react";
import { LayoutGroup } from "motion/react";
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
import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/lib/workspace";
import { store, shortTitle, analysisHref } from "@/lib/api";
import { AssistantProvider, useAssistant } from "@/lib/assistant";
import { ChatActions } from "./chat-actions";
import { AssistantFrame } from "./assistant-frame";
import { AssistantToggle } from "./floating-assistant";
import { SpaceMenu } from "./space-menu";
import { BusinessSwitcher } from "./business-switcher";
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
  useLanguage();
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
      <SidebarHeader className="p-3">
        <BusinessSwitcher />
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
                  tooltip={tr(label)}
                >
                  <a
                    href={`#${key}`}
                    onClick={close}
                    aria-label={tr(label)}
                    aria-current={route === key ? "page" : undefined}
                  >
                    <Icon />
                    <span>{tr(label)}</span>
                  </a>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
        <SidebarGroup role="region" aria-label={tr("Chats")}>
          <SidebarGroupLabel
            className="workspace-section-label workspace-chat-heading"
            aria-label={tr("Chats")}
          >
            <a
              href="#chats"
              onClick={close}
              aria-label={tr("Chats")}
              title={tr("Chats")}
              className="workspace-library-link inline-flex items-center rounded-md hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group-data-[collapsible=icon]:hidden"
            >
              <MessageSquare className="hidden size-4 group-data-[collapsible=icon]:block" />
              <span className="group-data-[collapsible=icon]:hidden">
                {tr("Chats")}
              </span>
            </a>
            <Button
              asChild
              variant="ghost"
              size="icon"
              className="workspace-new-chat ml-auto size-7"
            >
              <a
                href="#ask"
                aria-label={tr("Nuevo chat")}
                title={tr("Nuevo chat")}
                onClick={() => {
                  assistant?.newConversation("page");
                  close();
                }}
              >
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
                    aria-label={tr("Opciones de {0}", { "0": chat.title })}
                  >
                    <MoreHorizontal />
                  </SidebarMenuAction>
                </ChatActions>
              </SidebarMenuItem>
            ))}
            {listing.conversations.length > 6 && (
              <SidebarMenuItem>
                <SidebarMenuButton asChild tooltip={tr("Ver todos los chats")}>
                  <a
                    href="#chats"
                    onClick={close}
                    aria-label={tr("Ver todos los chats")}
                  >
                    <MoreHorizontal />
                    <span>{tr("Ver todos")}</span>
                  </a>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )}
          </SidebarMenu>
          {!chatRows.length && (
            <p className="px-2 py-1 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
              {tr("Todavía no hay chats")}
            </p>
          )}
        </SidebarGroup>
        <SidebarGroup role="region" aria-label={tr("Informes")}>
          <SidebarGroupLabel
            className="workspace-section-label workspace-report-heading"
            aria-label={tr("Informes")}
          >
            <a
              href="#reports"
              onClick={close}
              aria-label={tr("Informes")}
              title={tr("Informes")}
              className="workspace-library-link inline-flex items-center rounded-md hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group-data-[collapsible=icon]:h-6 group-data-[collapsible=icon]:w-full group-data-[collapsible=icon]:justify-center"
            >
              <span
                aria-hidden="true"
                className="hidden h-px w-4 bg-sidebar-border group-data-[collapsible=icon]:block"
              />
              <span className="group-data-[collapsible=icon]:hidden">
                {tr("Informes")}
              </span>
            </a>
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
                <SidebarMenuButton
                  asChild
                  tooltip={tr("Ver todos los informes")}
                >
                  <a
                    href="#reports"
                    onClick={close}
                    aria-label={tr("Ver todos los informes")}
                  >
                    <MoreHorizontal />
                    <span>{tr("Ver todos")}</span>
                  </a>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )}
          </SidebarMenu>
          {!reportRows.length && (
            <p className="px-2 py-1 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
              {tr("Todavía no hay informes")}
            </p>
          )}
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="p-3">
        <SpaceMenu />
      </SidebarFooter>
      {!isMobile && state === "expanded" && (
        <div
          role="separator"
          aria-label={tr("Anchura de la barra lateral")}
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
  useLanguage();
  const { route } = useWorkspace();
  const assistant = useAssistant();
  const back = route.startsWith("chat-report/")
    ? {
        href: `#chat/${route.split("/")[1]}`,
        label: tr("Volver al chat"),
      }
    : route === "ask" || route.startsWith("chat/")
      ? { href: "#chats", label: tr("Volver a chats") }
      : route.startsWith("report/") || route.startsWith("analysis/")
        ? { href: "#reports", label: tr("Volver a informes") }
        : null;
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 px-4 sm:px-6">
      <SidebarTrigger aria-label={tr("Abrir o cerrar navegación")} />
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
            aria-label={tr("Reducir chat")}
            title={tr("Reducir chat")}
            onClick={() => assistant.reduceConversation(route.split("/")[1])}
          >
            <Minimize2 />
          </Button>
        )}
        <AssistantToggle />
      </div>
    </header>
  );
}
