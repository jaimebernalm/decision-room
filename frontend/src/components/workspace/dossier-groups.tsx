import { useState } from "react";
import { ArrowUp, ArrowDown, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  const [draft, setDraft] = useState(() => structuredClone(layout));
  const [newName, setNewName] = useState("");
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
        if (invalid || newName.trim()) return;
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
          Por revisar reúne siempre las propuestas y conflictos pendientes.
          Eliminar un grupo conserva su información.
        </p>
        <ul className="space-y-3">
          {draft.groups.map((group, index) => (
            <li
              key={group.id}
              className="flex flex-wrap items-center gap-1 rounded-lg border p-2"
            >
              <Input
                aria-label={`Nombre del grupo ${index + 1}`}
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
                aria-label={`Subir grupo ${index + 1}`}
                disabled={action.busy || index === 0}
                onClick={() => move(index, -1)}
              >
                <ArrowUp />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Bajar grupo ${index + 1}`}
                disabled={action.busy || index === draft.groups.length - 1}
                onClick={() => move(index, 1)}
              >
                <ArrowDown />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Eliminar grupo ${index + 1}`}
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
            </li>
          ))}
        </ul>
        <div className="flex gap-2">
          <Input
            aria-label="Nombre del nuevo grupo"
            placeholder="Nombre del nuevo grupo"
            maxLength={60}
            value={newName}
            disabled={action.busy || draft.groups.length >= 20}
            onChange={(event) => setNewName(event.target.value)}
          />
          <Button
            type="button"
            variant="outline"
            disabled={
              action.busy || draft.groups.length >= 20 || !newName.trim()
            }
            onClick={() => {
              setDraft({
                ...draft,
                groups: [
                  ...draft.groups,
                  { id: crypto.randomUUID(), name: newName.trim() },
                ],
              });
              setNewName("");
            }}
          >
            <Plus />
            Añadir grupo
          </Button>
        </div>
        {invalid && (
          <p role="alert" className="text-sm text-destructive">
            Usa nombres distintos de entre 1 y 60 caracteres. Por revisar y Sin
            grupo están reservados.
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
          Restablecer grupos iniciales
        </Button>
        <Notice error>{action.error}</Notice>
      </div>
      <div className="shrink-0 border-t pt-3">
        {newName.trim() && (
          <p className="text-sm text-muted-foreground">
            Pulsa Añadir grupo para incorporarlo a la lista antes de guardar.
          </p>
        )}
        <Button
          type="submit"
          disabled={action.busy || invalid || Boolean(newName.trim())}
        >
          {action.busy && <Busy />}Guardar grupos
        </Button>
      </div>
    </form>
  );
}
