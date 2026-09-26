import { useState, type ReactNode, type CSSProperties } from "react";
import {
  BarChart3,
  Building2,
  ChevronDown,
  FileText,
  HelpCircle,
  Home,
  MessageSquare,
  MoreHorizontal,
  Plus,
  Trash2,
  PanelLeft,
  Sun,
  Moon,
} from "lucide-react";
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
  SidebarInset,
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
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { useWorkspace } from "@/lib/workspace";
import { store, shortTitle } from "@/lib/api";
const navigation = [
  ["home", "Inicio", Home],
  ["reports", "Informes", BarChart3],
  ["my-business", "Mi negocio", Building2],
] as const;
export function Layout({ children }: { children: ReactNode }) {
  const [width, setWidth] = useState(() =>
    Number(store.get("dr-sidebar-width", 256)),
  );
  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": `${Math.max(216, Math.min(width, 420))}px`,
        } as CSSProperties
      }
    >
      <Navigation width={width} setWidth={setWidth} />
      <SidebarInset className="relative h-svh min-w-0 overflow-hidden md:h-[calc(100svh-1rem)]">
        <Topbar />
        {children}
      </SidebarInset>
    </SidebarProvider>
  );
}
function Navigation({
  width,
  setWidth,
}: {
  width: number;
  setWidth: (v: number) => void;
}) {
  const { workspace, listing, route, removeChat } = useWorkspace(),
    { isMobile, setOpenMobile, state } = useSidebar();
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
  return (
    <Sidebar variant="inset" collapsible="icon">
      <SidebarHeader className="gap-4 p-3">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <a href="#home" onClick={close}>
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <PanelLeft className="size-4" />
                </span>
                <span className="text-base font-semibold tracking-tight">
                  Decision Room
                </span>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton className="h-10">
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
        <Button
          asChild
          className="w-full group-data-[collapsible=icon]:size-8 group-data-[collapsible=icon]:p-0"
        >
          <a href="#ask" onClick={close}>
            <Plus />
            <span className="group-data-[collapsible=icon]:hidden">
              Nuevo chat
            </span>
          </a>
        </Button>
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
                    (key === "reports" && route.startsWith("analysis")) ||
                    (key === "my-business" &&
                      ["files", "business"].includes(route))
                  }
                  tooltip={label}
                >
                  <a
                    href={`#${key}`}
                    onClick={close}
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
        <SidebarGroup>
          <SidebarGroupLabel>Conversaciones</SidebarGroupLabel>
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
                    aria-current={
                      route === `chat/${chat.id}` ? "page" : undefined
                    }
                  >
                    <MessageSquare />
                    <span>{shortTitle(chat.title)}</span>
                  </a>
                </SidebarMenuButton>
                <SidebarMenuAction
                  showOnHover
                  onClick={() => removeChat(chat)}
                  aria-label={`Eliminar chat ${chat.title}`}
                >
                  <Trash2 />
                </SidebarMenuAction>
              </SidebarMenuItem>
            ))}
            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                isActive={route === "chats"}
                tooltip="Todas las conversaciones"
              >
                <a href="#chats" onClick={close}>
                  <MoreHorizontal />
                  <span>Ver conversaciones</span>
                </a>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Análisis recientes</SidebarGroupLabel>
          <SidebarMenu>
            {workspace.analyses.slice(0, 5).map((item) => (
              <SidebarMenuItem key={item.id}>
                <SidebarMenuButton asChild tooltip={item.title}>
                  <a
                    href={`#analysis/${item.id}`}
                    onClick={close}
                    aria-current={
                      route === `analysis/${item.id}` ? "page" : undefined
                    }
                  >
                    <FileText />
                    <span>{shortTitle(item.title)}</span>
                  </a>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
            <SidebarMenuItem>
              <SidebarMenuButton asChild tooltip="Todos los análisis">
                <a href="#analyses" onClick={close}>
                  <BarChart3 />
                  <span>Ver análisis</span>
                </a>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="p-3">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="Cómo funciona">
              <a href="#how" onClick={close}>
                <HelpCircle />
                <span>Cómo funciona</span>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <div className="px-2 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
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
  const { route, workspace } = useWorkspace();
  const { theme, setTheme } = useTheme();
  const title = route.startsWith("chat/")
    ? "Conversación"
    : route.startsWith("report/") || route.startsWith("chat-report/")
      ? "Informe"
      : route.startsWith("analysis/")
        ? "Análisis"
        : {
            home: "Inicio",
            ask: "Nuevo chat",
            chats: "Conversaciones",
            reports: "Informes",
            analyses: "Análisis",
            "my-business": "Mi negocio",
            files: "Datos y archivos",
            business: "Presentación",
            businesses: "Negocios",
            "business-new": "Nuevo negocio",
            new: "Nuevo análisis",
            how: "Cómo funciona",
          }[route] || "Mi espacio";
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b px-4 sm:px-6">
      <SidebarTrigger aria-label="Abrir o cerrar navegación" />
      <Separator orientation="vertical" className="h-4!" />
      <span className="hidden truncate text-sm text-muted-foreground sm:inline">
        {workspace.business?.name || "Mi espacio"}
      </span>
      <span className="hidden text-muted-foreground sm:inline">/</span>
      <span className="truncate text-sm font-medium">{title}</span>
      <div className="ml-auto flex items-center gap-2">
        <Badge variant="outline" className="hidden sm:inline-flex">
          Local
        </Badge>
        <Button
          variant="ghost"
          size="icon"
          aria-label={theme === "dark" ? "Usar tema claro" : "Usar tema oscuro"}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? <Sun /> : <Moon />}
        </Button>
      </div>
    </header>
  );
}
