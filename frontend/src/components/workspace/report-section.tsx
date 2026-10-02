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
}) {
  useLanguage();
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card
        id={id}
        tabIndex={-1}
        className="gap-0 py-0 shadow-none scroll-mt-6"
      >
        <div className="flex items-start p-5">
          <div className="flex min-w-0 flex-1 items-start gap-3">
            {number && (
              <span
                aria-hidden
                className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs text-muted-foreground"
              >
                {number}
              </span>
            )}
            <div className="min-w-0 flex-1 space-y-2">
              <h3 className="text-base font-semibold leading-snug">{title}</h3>
              {preview && (
                <span className="block text-sm leading-6 text-muted-foreground">
                  {preview}
                </span>
              )}
            </div>
          </div>
          {actions && <div className="shrink-0 pl-2">{actions}</div>}
        </div>
        {lead && <div className="px-5 pb-4 text-sm leading-7">{lead}</div>}
        {visual && <div className="space-y-5 px-5 pb-4">{visual}</div>}
        <CollapsibleTrigger
          aria-label={`${open ? tr("Ocultar detalle") : tr("Ver detalle")}: ${title}`}
          className="group flex w-full cursor-pointer items-center justify-between gap-2 border-t px-5 py-3 text-left text-sm font-medium text-primary transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring motion-reduce:transition-none"
        >
          {open ? tr("Ocultar detalle") : tr("Ver detalle")}
          <ChevronDown
            aria-hidden
            className="size-4 transition-transform group-data-[state=open]:rotate-180 motion-reduce:transition-none"
          />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="space-y-3 border-t px-5 py-4 text-sm leading-7">
            {children}
          </div>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
