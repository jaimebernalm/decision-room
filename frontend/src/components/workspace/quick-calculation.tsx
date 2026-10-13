import { Fragment, useRef, useState } from "react";
import { translate as tr, useLanguage } from "@/lib/i18n";
import type { IndicatorsOverview, QuickCalculation } from "@/lib/types";
import { useAction, useResource } from "@/lib/hooks";
import { useWorkspace } from "@/lib/workspace";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Disclosure, Notice } from "./shared";

// Owner button: saves this published calculation as an indicator, or proposes it as a
// new version of one (the comparison and the confirmation happen in Inicio).
function SaveIndicator({
  item,
  turnId,
}: {
  item: QuickCalculation;
  turnId: string;
}) {
  useLanguage();
  const { workspace } = useWorkspace();
  const overview = useResource<IndicatorsOverview>("/api/indicators");
  const action = useAction();
  const metrics = Object.keys(item.metrics);
  const [name, setName] = useState(item.purpose.slice(0, 120));
  const [chosen, setChosen] = useState<string[]>(metrics.slice(0, 10));
  const [target, setTarget] = useState("");
  const [saved, setSaved] = useState("");
  const keys = useRef(new Map<string, string>());
  const key = (intent: string) => {
    if (!keys.current.has(intent))
      keys.current.set(intent, crypto.randomUUID());
    return keys.current.get(intent)!;
  };
  const indicator = overview.data?.indicators.find(
    (i) => i.id === target && i.version,
  );
  const submit = () =>
    action.run(async () => {
      const common = {
        business_id: workspace.business?.id,
        turn_id: turnId,
        calculation_id: item.calculation_id,
      };
      if (indicator) {
        await api(`/api/indicators/${indicator.id}/versions`, {
          ...common,
          request_key: key(`version:${indicator.id}:${indicator.version!.id}`),
          expected_active_version_id: indicator.version!.id,
        });
        setSaved(
          tr(
            "Versión propuesta. Revisa en Inicio la comparación con los datos anteriores antes de confirmarla.",
          ),
        );
      } else {
        await api("/api/indicators", {
          ...common,
          request_key: key(`create:${name}:${chosen.join("|")}`),
          name,
          metric_keys: chosen,
        });
        setSaved(tr("Indicador guardado. Lo verás en Inicio."));
      }
    });
  if (saved) return <p className="text-sm">{saved}</p>;
  const active = (overview.data?.indicators || []).filter(
    (i) => i.status === "active" && i.version,
  );
  return (
    <div className="space-y-3 text-sm">
      <p className="text-xs text-muted-foreground">
        {tr(
          "Se guardan la fórmula y los significados actuales de los datos para recalcularla sin modelo con cada versión nueva. No tiene comprobación independiente.",
        )}
      </p>
      {active.length > 0 && (
        <label className="block space-y-1">
          <span className="text-xs font-medium">{tr("Guardar como")}</span>
          <select
            className="w-full rounded-md border bg-background px-2 py-1"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
          >
            <option value="">{tr("Indicador nuevo")}</option>
            {active.map((i) => (
              <option key={i.id} value={i.id}>
                {tr("Nueva versión de «{0}»", { "0": i.name })}
              </option>
            ))}
          </select>
        </label>
      )}
      {!indicator && (
        <>
          <label className="block space-y-1">
            <span className="text-xs font-medium">
              {tr("Nombre del indicador")}
            </span>
            <Input
              value={name}
              maxLength={120}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <fieldset className="space-y-1">
            <legend className="text-xs font-medium">
              {tr("Cifras que se guardan")}
            </legend>
            {metrics.map((metric) => (
              <label key={metric} className="flex items-center gap-2 break-all">
                <input
                  type="checkbox"
                  checked={chosen.includes(metric)}
                  onChange={(event) =>
                    setChosen(
                      event.target.checked
                        ? [...chosen, metric].slice(0, 10)
                        : chosen.filter((m) => m !== metric),
                    )
                  }
                />
                {metric}
              </label>
            ))}
          </fieldset>
        </>
      )}
      <Button
        size="sm"
        disabled={
          action.busy || (!indicator && (!name.trim() || !chosen.length))
        }
        onClick={() => void submit()}
      >
        {indicator
          ? tr("Proponer nueva versión")
          : tr("Guardar como indicador")}
      </Button>
      <Notice error>{action.error}</Notice>
    </div>
  );
}

// Server-owned record of a chat calculation. The label stays visible with the code
// collapsed; the code is plain escaped text, never executed or rendered as markup.
export function QuickCalculations({
  items,
  turnId,
}: {
  items: QuickCalculation[];
  turnId?: string;
}) {
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
          {turnId && (
            <Disclosure subtle title={tr("Guardar este cálculo")}>
              <SaveIndicator item={item} turnId={turnId} />
            </Disclosure>
          )}
        </section>
      ))}
    </div>
  );
}
