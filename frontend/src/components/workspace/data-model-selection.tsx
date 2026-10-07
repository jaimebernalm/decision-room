import type { ReactNode } from "react";
import { Check, MousePointer2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { blockId, referenceId, useAssistant } from "@/lib/assistant";
import { translate as tr, useLanguage } from "@/lib/i18n";
import type { ContextAttachment } from "@/lib/types";
import type { DataModel, Relation } from "./data-model";
import { useBlockSelection } from "./context-selection";

function modelAttachment(
  model: DataModel,
  relation?: Relation,
): ContextAttachment {
  const names = Object.fromEntries(
    model.body.tables.map((table) => [table.id, table.name]),
  );
  const key = relation ? `relation:${relation.id}` : "model";
  const title = relation
    ? tr("Relación: {0} → {1}", {
        "0": names[relation.source],
        "1": names[relation.target],
      })
    : tr("Mapa de relaciones");
  const semanticLabels: Record<string, string> = {
    proposed: "Por confirmar",
    confirmed: "Significado confirmado",
    rejected: "Descartada",
  };
  const meaning = relation
    ? tr(semanticLabels[relation.semantic_status] || relation.semantic_status)
    : "";
  const statement = relation
    ? `${names[relation.source]} (${relation.source_columns.join(", ")}) → ${names[relation.target]} (${relation.target_columns.join(", ")}): ${relation.description ? relation.description + " · " : ""}${meaning}`
    : tr("{0} tablas · {1} relaciones", {
        "0": model.body.tables.length,
        "1": model.body.relations.length,
      });
  return {
    kind: "data_model",
    source_id: model.analysis_id,
    source_version: String(model.revision),
    element_key: key,
    title,
    report_title: tr("Datos"),
    href: "#my-business",
    content: { key, title, statement },
  };
}

function RelationshipSelection({
  item,
  disabled,
}: {
  item: ContextAttachment;
  disabled: boolean;
}) {
  const { assistant, active, selected } = useBlockSelection(
    disabled ? undefined : item,
  );
  return (
    <div id={blockId(item)} className="min-w-0 max-w-full">
      {active && (
        <Button
          variant={selected ? "secondary" : "outline"}
          size="sm"
          className="h-auto min-h-9 max-w-full whitespace-normal text-left [overflow-wrap:anywhere] [@media(pointer:coarse)]:min-h-11"
          aria-label={`${selected ? tr("Quitar") : tr("Seleccionar")}: ${item.title}`}
          aria-pressed={Boolean(selected)}
          onClick={() => assistant!.toggle(item)}
        >
          {selected ? (
            <Check className="shrink-0" />
          ) : (
            <MousePointer2 className="shrink-0" />
          )}
          {item.title}
        </Button>
      )}
    </div>
  );
}

export function DataModelSelection({
  model,
  disabled = false,
  children,
}: {
  model: DataModel;
  disabled?: boolean;
  children: (selection: {
    selecting: boolean;
    pickedEdges: string[];
    pick: (id: string) => void;
  }) => ReactNode;
}) {
  useLanguage();
  const item = modelAttachment(model);
  const { active, selected } = useBlockSelection(disabled ? undefined : item);
  const assistant = useAssistant();
  const attachments = model.body.relations.map((relation) =>
    modelAttachment(model, relation),
  );
  const pickedEdges = model.body.relations
    .filter(
      (_relation, index) =>
        assistant?.selected.some(
          (ref) => referenceId(ref) === referenceId(attachments[index]),
        ) ||
        (!active && assistant?.dock?.block === blockId(attachments[index])),
    )
    .map((relation) => relation.id);
  return (
    <div
      id={blockId(item)}
      className={`data-model-context min-w-0 space-y-3 ${selected ? "rounded-xl ring-2 ring-primary/40 ring-offset-4" : ""}`}
    >
      {active && (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant={selected ? "secondary" : "outline"}
            size="sm"
            className="min-h-9 [@media(pointer:coarse)]:min-h-11"
            data-select-map
            aria-pressed={Boolean(selected)}
            aria-label={`${selected ? tr("Quitar") : tr("Seleccionar")}: ${item.title}`}
            onClick={() => assistant!.toggle(item)}
          >
            {selected ? <Check /> : <MousePointer2 />}
            {tr("Todo el mapa")}
          </Button>
          <span className="text-xs text-muted-foreground">
            {tr("Selecciona una conexión o todo el mapa.")}
          </span>
        </div>
      )}
      {children({
        selecting: active,
        pickedEdges,
        pick: (id) => {
          const chosen = attachments.find(
            (ref) => ref.element_key === `relation:${id}`,
          );
          if (chosen) assistant?.toggle(chosen);
        },
      })}
      <div className={active ? "flex flex-wrap gap-2" : ""}>
        {attachments.map((attachment) => (
          <RelationshipSelection
            key={referenceId(attachment)}
            item={attachment}
            disabled={disabled}
          />
        ))}
      </div>
    </div>
  );
}
