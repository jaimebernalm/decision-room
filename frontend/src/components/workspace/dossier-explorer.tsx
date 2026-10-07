import { createContext, useContext, useId, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import "./dossier-explorer.css";

export type ExplorerGroup = {
  id: string;
  title: string;
  count?: number;
  description?: string;
  attention?: boolean;
  pending?: boolean;
};

const ExplorerContext = createContext({ active: "", prefix: "" });

export function DossierExplorer({
  groups,
  value,
  onValueChange,
  label,
  navigationFooter,
  navigation,
  children,
}: {
  groups: ExplorerGroup[];
  value: string;
  onValueChange: (id: string) => void;
  label: string;
  navigationFooter?: ReactNode;
  navigation?: ReactNode;
  children: ReactNode;
}) {
  const prefix = useId();
  const active = groups.some((group) => group.id === value)
    ? value
    : (
        groups.find((group) => (group.count || 0) > 0) ||
        groups.find((group) => !["review", "ungrouped"].includes(group.id)) ||
        groups[0]
      )?.id || "";
  return (
    <ExplorerContext.Provider value={{ active, prefix }}>
      <div className="dossier-explorer">
        <div className="dossier-explorer-layout">
          <nav className="dossier-explorer-nav" aria-label={label}>
            {navigation ||
              groups.map((group) => (
                <DossierExplorerLink
                  key={group.id}
                  group={group}
                  onSelect={() => onValueChange(group.id)}
                />
              ))}
            {navigationFooter && (
              <div className="dossier-explorer-footer">{navigationFooter}</div>
            )}
          </nav>
          <div className="min-w-0">{children}</div>
        </div>
      </div>
    </ExplorerContext.Provider>
  );
}

export function DossierExplorerLink({
  group,
  onSelect,
}: {
  group: ExplorerGroup;
  onSelect: () => void;
}) {
  const { active, prefix } = useContext(ExplorerContext);
  const link = (
    <Button
      type="button"
      id={`${prefix}-group-${group.id}`}
      variant="ghost"
      className="dossier-explorer-link"
      aria-pressed={active === group.id}
      aria-label={
        group.count === undefined
          ? group.title
          : `${group.title} ${group.count}`
      }
      aria-controls={group.pending ? undefined : `${prefix}-panel-${group.id}`}
      onClick={onSelect}
    >
      <span className="min-w-0 break-words whitespace-normal">
        {group.title}
      </span>
      {group.count !== undefined && (
        <Badge
          variant="secondary"
          className={`ml-auto shrink-0 ${group.attention && group.count > 0 ? "bg-destructive/10 text-destructive" : ""}`}
        >
          {group.count}
        </Badge>
      )}
    </Button>
  );
  return group.description ? (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>{link}</TooltipTrigger>
        <TooltipContent
          side="bottom"
          align="start"
          className="max-w-[min(20rem,calc(100vw-2rem))] whitespace-pre-wrap [overflow-wrap:anywhere]"
        >
          {group.description}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  ) : (
    link
  );
}

export function DossierExplorerPanel({
  id,
  children,
}: {
  id: string;
  children: ReactNode;
}) {
  const { active, prefix } = useContext(ExplorerContext);
  return (
    <section
      id={`${prefix}-panel-${id}`}
      aria-labelledby={`${prefix}-group-${id}`}
      hidden={active !== id}
      className="min-w-0"
    >
      {children}
    </section>
  );
}
