import { ChevronsUpDown, HelpCircle, Monitor, Moon, Sun } from "lucide-react";
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
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  useSidebar,
} from "@/components/ui/sidebar";

// The local app has a workspace, but no account or user profile.
export function SpaceMenu() {
  const { isMobile, setOpenMobile } = useSidebar();
  const { theme, setTheme } = useTheme();
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              aria-label="Opciones del espacio local"
              className="data-[state=open]:bg-sidebar-accent"
            >
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-accent">
                <Monitor className="size-4" />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
                <span className="truncate font-medium">Espacio local</span>
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
            <DropdownMenuLabel>Apariencia</DropdownMenuLabel>
            <DropdownMenuRadioGroup
              value={theme || "light"}
              onValueChange={setTheme}
            >
              <DropdownMenuRadioItem value="light">
                <Sun />
                Claro
              </DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="dark">
                <Moon />
                Oscuro
              </DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="system">
                <Monitor />
                Automático
              </DropdownMenuRadioItem>
            </DropdownMenuRadioGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <a
                href="#how"
                onClick={() => {
                  if (isMobile) setOpenMobile(false);
                }}
              >
                <HelpCircle />
                Cómo funciona
              </a>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
