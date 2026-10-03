import { translate as tr, useLanguage } from "@/lib/i18n";
import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { Card } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

/** Excerpt of reviewed text: complete first sentence, never an invented summary. */
export function reportLead(text: string) {
  return text.match(/^([\s\S]+?[.!?])\s+(?=[A-ZÁÉÍÓÚÜÑ¿¡])/)?.[1] || text;
}

export function ReportSection({
  title,
  preview,
  number,
  id,
  children,
  actions,
  visual,
  lead,
  defaultOpen = false,
  hasDetails = true,
}: {
  title: string;
  preview?: string;
  number?: string;
  id?: string;
  children: ReactNode;
  actions?: ReactNode;
  visual?: ReactNode;
  lead?: ReactNode;
  defaultOpen?: boolean;
  hasDetails?: boolean;
}) {
  useLanguage();
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card
        id={id}
        tabIndex={-1}
        className="gap-0 rounded-none bg-transparent py-0 pb-7 shadow-none ring-0 border-b scroll-mt-6"
      >
        <div className="flex items-start pt-6 pb-4">
          <div className="flex min-w-0 flex-1 items-start gap-3">
            {number && (
              <span
                aria-hidden
                className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-xs text-muted-foreground"
              >
                {number}
              </span>
            )}
            <div className="min-w-0 flex-1 space-y-2">
              <h3 className="text-xl font-semibold leading-tight tracking-tight sm:text-2xl">
                {title}
              </h3>
              {preview && (
                <span className="block text-sm leading-6 text-muted-foreground">
                  {preview}
                </span>
              )}
            </div>
          </div>
          {actions && <div className="shrink-0 pl-2">{actions}</div>}
        </div>
        {lead && <div className="pb-5 text-sm leading-7">{lead}</div>}
        {visual && <div className="space-y-7 pb-4">{visual}</div>}
        {hasDetails && (
          <CollapsibleTrigger
            aria-label={`${open ? tr("Ocultar datos y fuentes") : tr("Datos y fuentes")}: ${title}`}
            className="group flex w-fit cursor-pointer items-center gap-2 rounded py-1 text-left text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring motion-reduce:transition-none"
          >
            {open ? tr("Ocultar datos y fuentes") : tr("Datos y fuentes")}
            <ChevronDown
              aria-hidden
              className="size-4 transition-transform group-data-[state=open]:rotate-180 motion-reduce:transition-none"
            />
          </CollapsibleTrigger>
        )}
        {hasDetails && (
          <CollapsibleContent>
            <div className="mt-4 space-y-5 rounded-lg bg-muted/30 px-4 py-4 text-sm leading-7">
              {children}
            </div>
          </CollapsibleContent>
        )}
      </Card>
    </Collapsible>
  );
}
