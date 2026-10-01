import { translate as tr, useLanguage } from "@/lib/i18n";
import {
  ChevronsUpDown,
  HelpCircle,
  Monitor,
  Moon,
  Sun,
  Palette,
  Languages,
} from "lucide-react";
import { useTheme } from "next-themes";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
  DropdownMenuPortal,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  useSidebar,
} from "@/components/ui/sidebar";

// The local app has a workspace, but no account or user profile.
export function SpaceMenu() {
  useLanguage();
  const { language, setLanguage } = useLanguage();
  const { isMobile, setOpenMobile } = useSidebar();
  const { theme, setTheme } = useTheme();
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              aria-label={tr("Opciones del espacio local")}
              className="data-[state=open]:bg-sidebar-accent"
            >
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-accent">
                <Monitor className="size-4" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
                <span className="truncate font-medium">
                  {tr("Espacio local")}
                </span>
                <span className="truncate text-xs text-muted-foreground">
                  Decision Room
                </span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
            className="w-56"
          >
            <DropdownMenuLabel>{tr("Espacio local")}</DropdownMenuLabel>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>
                <Palette />
                {tr("Apariencia")}
              </DropdownMenuSubTrigger>
              <DropdownMenuPortal>
                <DropdownMenuSubContent>
                  <DropdownMenuRadioGroup
                    value={theme || "light"}
                    onValueChange={setTheme}
                  >
                    <DropdownMenuRadioItem value="light">
                      <Sun />
                      {tr("Claro")}
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="dark">
                      <Moon />
                      {tr("Oscuro")}
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="system">
                      <Monitor />
                      {tr("Automático")}
                    </DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuPortal>
            </DropdownMenuSub>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>
                <Languages />
                {tr("Idioma")}
              </DropdownMenuSubTrigger>
              <DropdownMenuPortal>
                <DropdownMenuSubContent>
                  <DropdownMenuRadioGroup
                    value={language}
                    onValueChange={(value) => {
                      if (value === "en" || value === "es") setLanguage(value);
                    }}
                  >
                    <DropdownMenuRadioItem value="en">
                      English
                    </DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="es">{tr("Español")}</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuPortal>
            </DropdownMenuSub>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <a
                href="#how"
                onClick={() => {
                  if (isMobile) setOpenMobile(false);
                }}
              >
                <HelpCircle />
                {tr("Cómo funciona")}
              </a>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
