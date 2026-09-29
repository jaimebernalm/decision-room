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
}: {
  title: string;
  preview?: string;
  number?: string;
  id?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card id={id} className="gap-0 py-0 shadow-none">
        <CollapsibleTrigger className="group flex w-full cursor-pointer items-start gap-3 rounded-xl p-5 text-left transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring motion-reduce:transition-none">
          {number && (
            <span
              aria-hidden
              className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs text-muted-foreground"
            >
              {number}
            </span>
          )}
          <span className="min-w-0 flex-1 space-y-2">
            <span className="block text-base font-medium leading-snug">
              {title}
            </span>
            {preview && (
              <span className="block text-sm leading-6 text-muted-foreground">
                {preview}
              </span>
            )}
            <span className="flex items-center gap-1 text-xs font-medium text-primary">
              {open ? "Ocultar detalle" : "Ver detalle"}
              <ChevronDown
                aria-hidden
                className="size-3.5 transition-transform group-data-[state=open]:rotate-180 motion-reduce:transition-none"
              />
            </span>
          </span>
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
