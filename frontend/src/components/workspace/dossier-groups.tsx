import { translate as tr, useLanguage } from "@/lib/i18n";
import { useState } from "react";
import { ArrowUp, ArrowDown, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAction } from "@/lib/hooks";
import { api } from "@/lib/api";
import type { DossierLayout } from "@/lib/types";
import { Notice, Busy } from "./shared";

import { defaultDossierLayout } from "@/lib/dossier-layout";

export function GroupEditor({
  business,
  layout,
  onDone,
}: {
  business: string;
  layout: DossierLayout;
  onDone: () => void;
}) {
  useLanguage();
  const [draft, setDraft] = useState(() => structuredClone(layout));
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const action = useAction();
  const names = draft.groups.map((g) =>
    g.name.trim().replace(/\s+/g, " ").toLocaleLowerCase(),
  );
  const invalid =
    names.some(
      (n) => !n || n.length > 60 || ["por revisar", "sin grupo"].includes(n),
    ) || new Set(names).size !== names.length;
  const move = (index: number, offset: number) => {
    const groups = [...draft.groups];
    [groups[index], groups[index + offset]] = [
      groups[index + offset],
      groups[index],
    ];
    setDraft({ ...draft, groups });
  };
  return (
    <form
      className="flex min-h-0 flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (invalid || newName.trim() || newDescription.trim()) return;
        void action.run(async () => {
          await api("/api/business/dossier-layout", {
            business_id: business,
            ...draft,
          });
          onDone();
        });
      }}
    >
      <div className="min-h-0 space-y-4 overflow-y-auto px-1">
        <p className="text-sm text-muted-foreground">
          {tr(
            "Por revisar reúne siempre las propuestas y conflictos pendientes. Eliminar un grupo conserva su información. La descripción ayuda al agente a clasificar nuevas memorias; puedes moverlas después.",
          )}
        </p>
        <ul className="space-y-3">
          {draft.groups.map((group, index) => (
            <li
              key={group.id}
              className="flex flex-wrap items-center gap-1 rounded-lg border p-2"
            >
              <Input
                aria-label={tr("Nombre del grupo {0}", { 0: index + 1 })}
                maxLength={60}
                required
                value={group.name}
                disabled={action.busy}
                className="min-w-0 flex-1 basis-40"
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    groups: draft.groups.map((g) =>
                      g.id === group.id
                        ? { ...g, name: event.target.value }
                        : g,
                    ),
                  })
                }
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={tr("Subir grupo {0}", { 0: index + 1 })}
                disabled={action.busy || index === 0}
                onClick={() => move(index, -1)}
              >
                <ArrowUp />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={tr("Bajar grupo {0}", { 0: index + 1 })}
                disabled={action.busy || index === draft.groups.length - 1}
                onClick={() => move(index, 1)}
              >
                <ArrowDown />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={tr("Eliminar grupo {0}", { 0: index + 1 })}
                disabled={action.busy}
                onClick={() =>
                  setDraft({
                    ...draft,
                    groups: draft.groups.filter((g) => g.id !== group.id),
                    assignments: Object.fromEntries(
                      Object.entries(draft.assignments).filter(
                        ([, id]) => id !== group.id,
                      ),
                    ),
                  })
                }
              >
                <X />
              </Button>
              <Textarea
                aria-label={tr("Descripción del grupo {0}", { 0: index + 1 })}
                placeholder={tr("Qué información debe guardar el agente aquí")}
                maxLength={500}
                value={group.description || ""}
                disabled={action.busy}
                className="min-h-20 w-full text-sm"
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    groups: draft.groups.map((g) =>
                      g.id === group.id
                        ? { ...g, description: event.target.value }
                        : g,
                    ),
                  })
                }
              />
            </li>
          ))}
        </ul>
        <div className="space-y-2 rounded-lg border p-3">
          <Input
            aria-label={tr("Nombre del nuevo grupo")}
            placeholder={tr("Nombre del nuevo grupo")}
            maxLength={60}
            value={newName}
            disabled={action.busy || draft.groups.length >= 20}
            onChange={(event) => setNewName(event.target.value)}
          />
          <Textarea
            aria-label={tr("Descripción del nuevo grupo")}
            placeholder={tr("Describe qué información debe ir en este grupo")}
            maxLength={500}
            value={newDescription}
            disabled={action.busy || draft.groups.length >= 20}
            onChange={(event) => setNewDescription(event.target.value)}
            className="min-h-20"
          />
          <p className="text-xs text-muted-foreground">
            {tr("Nombre y descripción son necesarios para añadir un grupo.")}
          </p>
          <Button
            type="button"
            variant="outline"
            disabled={
              action.busy ||
              draft.groups.length >= 20 ||
              !newName.trim() ||
              !newDescription.trim()
            }
            onClick={() => {
              setDraft({
                ...draft,
                groups: [
                  ...draft.groups,
                  {
                    id: crypto.randomUUID(),
                    name: newName.trim(),
                    description: newDescription.trim(),
                  },
                ],
              });
              setNewName("");
              setNewDescription("");
            }}
          >
            <Plus />
            {tr("Añadir grupo")}
          </Button>
        </div>
        {invalid && (
          <p role="alert" className="text-sm text-destructive">
            {tr(
              "Usa nombres distintos de entre 1 y 60 caracteres. Por revisar y Sin grupo están reservados.",
            )}
          </p>
        )}
        <Button
          type="button"
          variant="ghost"
          disabled={action.busy}
          onClick={() =>
            setDraft({
              ...draft,
              groups: structuredClone(defaultDossierLayout.groups),
              assignments: {},
            })
          }
        >
          {tr("Restablecer grupos iniciales")}
        </Button>
        <Notice error>{action.error}</Notice>
      </div>
      <div className="shrink-0 border-t pt-3">
        {(newName.trim() || newDescription.trim()) && (
          <p className="text-sm text-muted-foreground">
            {tr(
              "Pulsa Añadir grupo para incorporarlo a la lista antes de guardar.",
            )}
          </p>
        )}
        <Button
          type="submit"
          disabled={
            action.busy ||
            invalid ||
            Boolean(newName.trim() || newDescription.trim())
          }
        >
          {action.busy && <Busy />}
          {tr("Guardar grupos")}
        </Button>
      </div>
    </form>
  );
}
