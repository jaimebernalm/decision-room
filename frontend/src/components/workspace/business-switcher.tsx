import { translate as tr, useLanguage } from "@/lib/i18n";
import { useState } from "react";
import {
  Building2,
  Check,
  ChevronsUpDown,
  LoaderCircle,
  Plus,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useWorkspace } from "@/lib/workspace";
import { useAction } from "@/lib/hooks";
import { api } from "@/lib/api";

export function BusinessSwitcher() {
  useLanguage();
  const { workspace, refresh } = useWorkspace();
  const { isMobile, setOpenMobile } = useSidebar();
  const [open, setOpen] = useState(false);
  const action = useAction();
  const active = workspace.business;
  const businesses = active
    ? [active, ...workspace.businesses.filter((b) => b.id !== active.id)]
    : workspace.businesses;
  const close = () => {
    setOpen(false);
    if (isMobile) setOpenMobile(false);
  };
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu
          open={open}
          onOpenChange={(value) => {
            if (!action.busy) setOpen(value);
          }}
        >
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              aria-label={active?.name || tr("Tus negocios")}
              className="data-[state=open]:bg-sidebar-accent"
            >
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <Building2 className="size-4" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
                <span className="truncate font-medium">
                  {active?.name || tr("Tus negocios")}
                </span>
                <span className="truncate text-xs text-muted-foreground">
                  {action.busy ? tr("Cambiando de negocio…") : tr("Mi espacio")}
                </span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            side={isMobile ? "bottom" : "right"}
            align="start"
            sideOffset={4}
            className="w-64"
          >
            <DropdownMenuLabel>{tr("Tus negocios")}</DropdownMenuLabel>
            {businesses.map((b) => (
              <DropdownMenuItem
                key={b.id}
                disabled={action.busy}
                aria-label={
                  b.id === active?.id
                    ? tr("{0}, negocio activo", { "0": b.name })
                    : b.name
                }
                onSelect={(event) => {
                  event.preventDefault();
                  if (b.id === active?.id) {
                    close();
                    return;
                  }
                  void action.run(async () => {
                    await api("/api/business/select", { business_id: b.id });
                    if (!action.isMounted()) return;
                    refresh();
                    close();
                    location.hash = "home";
                  });
                }}
              >
                <Building2 />
                <span className="truncate">{b.name}</span>
                {b.id === active?.id && <Check className="ml-auto" />}
              </DropdownMenuItem>
            ))}
            {action.busy && (
              <p
                role="status"
                className="flex items-center gap-2 px-2 py-1 text-xs text-muted-foreground"
              >
                <LoaderCircle className="size-3 animate-spin" />
                {tr("Cambiando de negocio…")}
              </p>
            )}
            {action.error && (
              <p role="alert" className="px-2 py-1 text-xs text-destructive">
                {action.error}
              </p>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild disabled={action.busy}>
              <a href="#businesses" onClick={close}>
                <Building2 />
                {tr("Gestionar negocios")}
              </a>
            </DropdownMenuItem>
            <DropdownMenuItem asChild disabled={action.busy}>
              <a href="#business-new" onClick={close}>
                <Plus />
                {tr("Crear negocio")}
              </a>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
