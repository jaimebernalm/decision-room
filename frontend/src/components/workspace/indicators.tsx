import { useRef, useState } from "react";
import { translate as tr, useLanguage } from "@/lib/i18n";
import { useAction, useResource } from "@/lib/hooks";
import { useWorkspace } from "@/lib/workspace";
import { api } from "@/lib/api";
import type {
  FollowUp,
  IndicatorComparison,
  IndicatorsOverview,
  SavedIndicator,
} from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Disclosure, Notice } from "./shared";

// One request key per intended action, reused on a double click.
function useKeys() {
  const keys = useRef(new Map<string, string>());
  return (action: string) => {
    if (!keys.current.has(action))
      keys.current.set(action, crypto.randomUUID());
    return keys.current.get(action)!;
  };
}

const comparisonText: Record<IndicatorComparison["state"], string> = {
  pending: "Comparando con los datos anteriores…",
  match: "Da lo mismo que la fórmula anterior con los datos anteriores.",
  mismatch:
    "Da un resultado distinto que la fórmula anterior con los datos anteriores.",
  unavailable: "No se ha podido comparar con los datos anteriores.",
};

function Indicator({
  item,
  business,
  onChange,
}: {
  item: SavedIndicator;
  business: string;
  onChange: () => void;
}) {
  useLanguage();
  const action = useAction();
  const key = useKeys();
  const latest = item.values[0];
  const post = (path: string, body: object, name: string) =>
    action.run(async () => {
      await api(path, {
        business_id: business,
        request_key: key(name),
        ...body,
      });
      if (action.isMounted()) onChange();
    });
  return (
    <section
      className="min-w-0 space-y-3 rounded-lg border p-4"
      aria-label={item.name}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium break-words">{item.name}</p>
        <Badge variant="outline" className="whitespace-normal text-left">
          {tr(item.label)}
        </Badge>
      </div>
      {latest ? (
        <div className="space-y-1 text-sm">
          {latest.status === "completed" ? (
            <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1">
              {Object.entries(latest.display).map(([metric, value]) => (
                <div key={metric} className="contents">
                  <dt className="break-words text-muted-foreground">
                    {metric}
                  </dt>
                  <dd className="text-right font-medium tabular-nums">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          ) : latest.status === "unavailable" ? (
            <p>
              <span className="font-medium">{tr("No disponible:")}</span>{" "}
              {latest.reason}
            </p>
          ) : (
            <p className="text-muted-foreground">
              {tr("Pendiente de recalcular.")}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            {tr("Versión {0} de los datos · fórmula versión {1}", {
              "0": latest.dataset_version,
              "1": item.version?.version ?? "—",
            })}
          </p>
          {latest.meanings && (
            <p className="rounded-md bg-amber-500/10 px-2 py-1 text-xs text-amber-900 dark:text-amber-200">
              {latest.meanings}
            </p>
          )}
          {latest.status === "unavailable" && (
            <p className="text-xs text-muted-foreground">
              {tr(
                "Para repararlo, pide al chat que lo recalcule con los datos actuales y guarda ese cálculo como nueva versión.",
              )}
            </p>
          )}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          {tr("Sin valor todavía.")}
        </p>
      )}
      {item.version && (
        <Disclosure subtle title={tr("Ver la fórmula")}>
          <pre className="max-h-80 max-w-full overflow-auto rounded-md bg-muted p-3 font-mono text-xs leading-5">
            <code>{item.version.code}</code>
          </pre>
        </Disclosure>
      )}
      {item.proposals.map((proposal) => (
        <div
          key={proposal.id}
          className="space-y-2 rounded-md bg-muted/50 p-3 text-sm"
        >
          <p className="font-medium">
            {tr("Versión propuesta {0}", { "0": proposal.version })}
          </p>
          <p>{tr(comparisonText[proposal.comparison.state])}</p>
          {proposal.comparison.metrics?.map((row) => (
            <p key={row.metric} className="text-xs text-muted-foreground">
              {row.metric}: {String(row.before)} →{" "}
              {row.present ? String(row.after) : "—"}
            </p>
          ))}
          {proposal.comparison.state !== "pending" && item.version && (
            <>
              <p className="text-xs text-muted-foreground">
                {tr(
                  "Al confirmar se fijan esta fórmula y los significados actuales de los datos para los próximos recálculos. Las versiones nuevas de los datos pueden no tener esos significados declarados.",
                )}
              </p>
              <Button
                size="sm"
                disabled={action.busy}
                onClick={() =>
                  void post(
                    `/api/indicators/${item.id}/versions/${proposal.id}/confirm`,
                    {
                      expected_active_version_id: item.version!.id,
                      comparison_sha: proposal.comparison.sha256,
                    },
                    `confirm:${proposal.id}:${proposal.comparison.sha256}`,
                  )
                }
              >
                {tr("Confirmar esta versión")}
              </Button>
            </>
          )}
        </div>
      ))}
      {item.status === "active" && (
        <Button
          variant="ghost"
          size="sm"
          disabled={action.busy}
          onClick={() =>
            void post(
              `/api/indicators/${item.id}/retire`,
              { expected_revision: item.revision },
              `retire:${item.revision}`,
            )
          }
        >
          {tr("Retirar indicador")}
        </Button>
      )}
      <Notice error>{action.error}</Notice>
    </section>
  );
}

const stateText: Record<FollowUp["state"], string> = {
  proposed: "Propuesto",
  checked: "Comprobado con datos (lo has marcado tú)",
  closed: "Cerrado",
};

function Topic({
  item,
  business,
  onChange,
}: {
  item: FollowUp;
  business: string;
  onChange: () => void;
}) {
  useLanguage();
  const action = useAction();
  const key = useKeys();
  const move = (state: FollowUp["state"]) =>
    action.run(async () => {
      await api(`/api/follow-ups/${item.id}/state`, {
        business_id: business,
        request_key: key(`${state}:${item.revision}`),
        state,
        expected_revision: item.revision,
      });
      if (action.isMounted()) onChange();
    });
  const branches = (["check", "if_confirmed", "if_not"] as const).filter(
    (branch) => item.content[branch],
  );
  return (
    <section
      className="min-w-0 space-y-2 rounded-lg border p-4 text-sm"
      aria-label={item.priority_title}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground break-words">
          {item.headline} · {item.report_date.slice(0, 10)}
        </p>
        <Badge variant="outline">{tr(stateText[item.state])}</Badge>
      </div>
      <p className="font-medium break-words">{item.priority_title}</p>
      {branches.map((branch) => (
        <div key={branch}>
          <p className="text-xs font-medium text-muted-foreground">
            {item.content.labels[branch]}
          </p>
          {item.content[branch]!.map((line, index) => (
            <p key={index} className="whitespace-pre-wrap break-words">
              {line}
            </p>
          ))}
        </div>
      ))}
      <div className="flex flex-wrap gap-2 pt-1">
        {item.state !== "checked" && (
          <Button
            size="sm"
            variant="outline"
            disabled={action.busy}
            onClick={() => void move("checked")}
          >
            {tr("Marcar como comprobado")}
          </Button>
        )}
        {item.state !== "closed" && (
          <Button
            size="sm"
            variant="outline"
            disabled={action.busy}
            onClick={() => void move("closed")}
          >
            {tr("Cerrar")}
          </Button>
        )}
        {item.state !== "proposed" && (
          <Button
            size="sm"
            variant="ghost"
            disabled={action.busy}
            onClick={() => void move("proposed")}
          >
            {tr("Reabrir")}
          </Button>
        )}
      </div>
      <Notice error>{action.error}</Notice>
    </section>
  );
}

export function IndicatorsPanel() {
  useLanguage();
  const { workspace } = useWorkspace();
  const resource = useResource<IndicatorsOverview>("/api/indicators", 15000);
  const business = workspace.business?.id;
  const [showRetired, setShowRetired] = useState(false);
  const data = resource.data;
  // Hidden until the overview loads (or if the endpoint returns something else).
  if (!business || !Array.isArray(data?.indicators) || !data.follow_ups)
    return null;
  const indicators = data.indicators.filter(
    (i) => showRetired || i.status === "active",
  );
  if (!data.indicators.length && !data.follow_ups.items.length) return null;
  return (
    <section
      id="indicators"
      className="mt-8 space-y-4"
      aria-label={tr("Indicadores y seguimiento")}
    >
      <h2 className="text-base font-semibold">
        {tr("Indicadores y seguimiento")}
      </h2>
      {data.indicators.length > 0 && (
        <div className="space-y-3">
          <div className="grid gap-3 lg:grid-cols-2">
            {indicators.map((item) => (
              <Indicator
                key={item.id}
                item={item}
                business={business}
                onChange={resource.refresh}
              />
            ))}
          </div>
          {data.indicators.some((i) => i.status === "retired") && (
            <Button
              variant="link"
              size="sm"
              onClick={() => setShowRetired(!showRetired)}
            >
              {showRetired ? tr("Ocultar retirados") : tr("Ver retirados")}
            </Button>
          )}
        </div>
      )}
      {data.follow_ups.items.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold">
            {tr("Temas abiertos de informes anteriores")}
          </h3>
          <div className="grid gap-3 lg:grid-cols-2">
            {data.follow_ups.items.map((item) => (
              <Topic
                key={item.id}
                item={item}
                business={business}
                onChange={resource.refresh}
              />
            ))}
          </div>
          {data.follow_ups.counts.closed > 0 && (
            <p className="text-xs text-muted-foreground">
              {tr("{0} tema(s) cerrado(s).", {
                "0": data.follow_ups.counts.closed,
              })}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
