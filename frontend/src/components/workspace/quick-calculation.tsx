import { Fragment } from "react";
import { translate as tr, useLanguage } from "@/lib/i18n";
import type { QuickCalculation } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Disclosure } from "./shared";

// Server-owned record of a chat calculation. The label stays visible with the code
// collapsed; the code is plain escaped text, never executed or rendered as markup.
export function QuickCalculations({ items }: { items: QuickCalculation[] }) {
  useLanguage();
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <section
          key={item.calculation_id}
          className="min-w-0 space-y-3 rounded-lg border p-4"
          aria-label={tr(item.label)}
        >
          <Badge variant="outline" className="whitespace-normal text-left">
            {tr(item.label)}
          </Badge>
          <p className="text-sm font-medium break-words">{item.purpose}</p>
          <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 text-sm">
            {Object.entries(item.metrics).map(([name, value]) => (
              <Fragment key={name}>
                <dt className="break-words text-muted-foreground">{name}</dt>
                <dd className="break-all text-right font-medium tabular-nums">
                  {String(value)}
                </dd>
              </Fragment>
            ))}
          </dl>
          <Disclosure subtle title={tr("Ver el código y las tablas")}>
            <p className="text-xs text-muted-foreground break-words">
              {tr("Tablas:")}{" "}
              {item.tables
                .map((t) => `${t.alias} (${t.names.join(", ")})`)
                .join(" · ")}
            </p>
            <pre className="max-h-80 max-w-full overflow-auto rounded-md bg-muted p-3 font-mono text-xs leading-5">
              <code>{item.code}</code>
            </pre>
            {item.notes.length > 0 && (
              <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
                {item.notes.map((note, i) => (
                  <li key={i}>{note}</li>
                ))}
              </ul>
            )}
          </Disclosure>
        </section>
      ))}
    </div>
  );
}
