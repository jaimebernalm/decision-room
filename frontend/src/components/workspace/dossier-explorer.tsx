import { createContext, useContext, useId, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import "./dossier-explorer.css";

const ExplorerContext = createContext({ active: "", prefix: "" });

export function DossierExplorer({
  groups,
  value,
  onValueChange,
  label,
  children,
}: {
  groups: { id: string; title: string; count?: number }[];
  value: string;
  onValueChange: (id: string) => void;
  label: string;
  children: ReactNode;
}) {
  const prefix = useId();
  const active = groups.some((group) => group.id === value)
    ? value
    : (groups.find((group) => (group.count || 0) > 0) || groups[0])?.id || "";
  return (
    <ExplorerContext.Provider value={{ active, prefix }}>
      <div className="dossier-explorer">
        <div className="dossier-explorer-layout">
          <nav className="dossier-explorer-nav" aria-label={label}>
            {groups.map((group) => (
              <Button
                key={group.id}
                id={`${prefix}-group-${group.id}`}
                variant="ghost"
                className="dossier-explorer-link"
                aria-pressed={active === group.id}
                aria-label={
                  group.count === undefined
                    ? group.title
                    : `${group.title} ${group.count}`
                }
                aria-controls={`${prefix}-panel-${group.id}`}
                onClick={() => onValueChange(group.id)}
              >
                <span className="min-w-0 break-words whitespace-normal">
                  {group.title}
                </span>
                {group.count !== undefined && (
                  <Badge variant="secondary" className="ml-auto shrink-0">
                    {group.count}
                  </Badge>
                )}
              </Button>
            ))}
          </nav>
          <div className="min-w-0">{children}</div>
        </div>
      </div>
    </ExplorerContext.Provider>
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
