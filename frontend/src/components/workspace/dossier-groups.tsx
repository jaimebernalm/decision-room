import { translate as tr, useLanguage } from "@/lib/i18n";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import {
  ArrowUp,
  ArrowDown,
  GripVertical,
  Plus,
  X,
  Pencil,
} from "lucide-react";
import { MotionConfig, Reorder, motion, useDragControls } from "motion/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAction } from "@/lib/hooks";
import { api } from "@/lib/api";
import type { DossierLayout } from "@/lib/types";
import { Notice, Busy } from "./shared";

import { DossierExplorerLink, type ExplorerGroup } from "./dossier-explorer";
import { defaultDossierLayout } from "@/lib/dossier-layout";

export function GroupEditor({
  business,
  layout,
  onDone,
  onCancel,
  groups,
  active,
  onSelect,
}: {
  business: string;
  layout: DossierLayout;
  onDone: () => void;
  onCancel: () => void;
  groups: ExplorerGroup[];
  active: string;
  onSelect: (id: string) => void;
}) {
  useLanguage();
  const [draft, setDraft] = useState(() => structuredClone(layout));
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const dragHelp = useId();
  const [editing, setEditing] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const action = useAction();
  const form = useRef<HTMLFormElement>(null);
  useEffect(() => {
    (
      form.current?.querySelector<HTMLButtonElement>(
        "button[aria-describedby]",
      ) || form.current?.querySelector<HTMLButtonElement>("button")
    )?.focus();
  }, []);
  const names = draft.groups.map((g) =>
    g.name.trim().replace(/\s+/g, " ").toLocaleLowerCase(),
  );
  const invalid =
    names.some(
      (n) => !n || n.length > 60 || ["por revisar", "sin grupo"].includes(n),
    ) || new Set(names).size !== names.length;
  const move = (index: number, offset: number) => {
    if (
      action.busy ||
      index + offset < 0 ||
      index + offset >= draft.groups.length
    )
      return;
    const groups = [...draft.groups];
    [groups[index], groups[index + offset]] = [
      groups[index + offset],
      groups[index],
    ];
    setDraft({ ...draft, groups });
    setAnnouncement(
      tr("{0}: posición {1} de {2}.", {
        0: draft.groups[index].name,
        1: index + offset + 1,
        2: groups.length,
      }),
    );
  };
  return (
    <form
      ref={form}
      className="dossier-group-editor flex min-h-0 w-full flex-col gap-3"
      aria-label={tr("Personalizar grupos")}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !action.busy) {
          event.preventDefault();
          event.stopPropagation();
          onCancel();
        }
      }}
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
      <p className="sr-only">
        {tr("Eliminar un grupo conserva su información.")}
      </p>
      <motion.div layoutScroll className="min-h-0 space-y-3">
        {groups
          .filter((group) => group.id === "review")
          .map((group) => (
            <DossierExplorerLink
              key={group.id}
              group={group}
              onSelect={() => onSelect(group.id)}
            />
          ))}
        <p id={dragHelp} className="sr-only">
          {tr(
            "Arrastra el asa para ordenar los grupos. También puedes usar las flechas o las teclas ↑ y ↓ sobre el asa. Guarda para aplicar el orden.",
          )}
        </p>
        <p role="status" aria-live="polite" className="sr-only">
          {announcement}
        </p>
        <MotionConfig reducedMotion="user">
          <Reorder.Group
            axis="y"
            values={draft.groups.map((g) => g.id)}
            aria-label={tr("Orden de grupos")}
            onReorder={(ids) => {
              if (action.busy) return;
              setDraft((current) => ({
                ...current,
                groups: ids.map((id) =>
                  current.groups.find((g) => g.id === id)!,
                ),
              }));
            }}
            className="space-y-3"
          >
            {draft.groups.map((group, index) => (
              <SortableGroup
                key={group.id}
                id={group.id}
                name={group.name}
                disabled={action.busy}
                help={dragHelp}
                onMove={(offset) => move(index, offset)}
                onDrop={() =>
                  setAnnouncement(
                    tr("{0}: posición {1} de {2}.", {
                      0: group.name,
                      1: index + 1,
                      2: draft.groups.length,
                    }),
                  )
                }
              >
                <div className="dossier-group-edit-row flex min-w-0 flex-1 items-center">
                  <DossierExplorerLink
                    group={{
                      ...groups.find((g) => g.id === group.id),
                      id: group.id,
                      title: group.name,
                      description: group.description,
                      pending: !layout.groups.some((g) => g.id === group.id),
                    }}
                    onSelect={() => {
                      if (layout.groups.some((g) => g.id === group.id))
                        onSelect(group.id);
                      else setEditing(group.id);
                    }}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="shrink-0 size-7 [@media(pointer:coarse)]:size-11"
                    aria-label={tr("Editar grupo {0}", { 0: index + 1 })}
                    aria-expanded={editing === group.id}
                    disabled={action.busy}
                    onClick={() =>
                      setEditing(editing === group.id ? null : group.id)
                    }
                  >
                    <Pencil className="size-3.5" />
                  </Button>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  size="icon"
                  className="dossier-group-remove"
                  aria-label={tr("Eliminar grupo {0}", { 0: index + 1 })}
                  disabled={action.busy}
                  onClick={() => {
                    if (active === group.id) onSelect("ungrouped");
                    setDraft({
                      ...draft,
                      groups: draft.groups.filter((g) => g.id !== group.id),
                      assignments: Object.fromEntries(
                        Object.entries(draft.assignments).filter(
                          ([, id]) => id !== group.id,
                        ),
                      ),
                    });
                  }}
                >
                  <X className="size-3" />
                </Button>
                {editing === group.id && (
                  <>
                    <Input
                      aria-label={tr("Nombre del grupo {0}", { 0: index + 1 })}
                      maxLength={60}
                      required
                      value={group.name}
                      disabled={action.busy}
                      className="min-w-0 flex-1 basis-24 sm:basis-40"
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
                      disabled={
                        action.busy || index === draft.groups.length - 1
                      }
                      onClick={() => move(index, 1)}
                    >
                      <ArrowDown />
                    </Button>
                    <Textarea
                      aria-label={tr("Descripción del grupo {0}", {
                        0: index + 1,
                      })}
                      placeholder={tr(
                        "Qué información debe guardar el agente aquí",
                      )}
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
                  </>
                )}
              </SortableGroup>
            ))}
          </Reorder.Group>
        </MotionConfig>
        {groups
          .filter((group) => group.id === "ungrouped")
          .map((group) => (
            <DossierExplorerLink
              key={group.id}
              group={group}
              onSelect={() => onSelect(group.id)}
            />
          ))}
        {!adding && (
          <Button
            type="button"
            variant="ghost"
            className="w-full justify-start text-muted-foreground"
            disabled={action.busy || draft.groups.length >= 20}
            onClick={() => setAdding(true)}
          >
            <Plus />
            {tr("Nuevo grupo")}
          </Button>
        )}
        {adding && (
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
                setAdding(false);
              }}
            >
              <Plus />
              {tr("Añadir grupo")}
            </Button>
          </div>
        )}
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
      </motion.div>
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
        <Button
          type="button"
          variant="ghost"
          disabled={action.busy}
          onClick={onCancel}
        >
          {tr("Cancelar")}
        </Button>
      </div>
    </form>
  );
}

function SortableGroup({
  id,
  name,
  disabled,
  help,
  onMove,
  onDrop,
  children,
}: {
  id: string;
  name: string;
  disabled: boolean;
  help: string;
  onMove: (offset: number) => void;
  onDrop: () => void;
  children: ReactNode;
}) {
  const controls = useDragControls();
  return (
    <Reorder.Item
      value={id}
      dragListener={false}
      dragControls={controls}
      dragMomentum={false}
      className="dossier-group-edit-item relative flex flex-wrap items-center gap-1 rounded-lg bg-foreground/10 p-1"
      whileDrag={{ boxShadow: "0 12px 24px rgb(0 0 0 / 0.16)" }}
      onDragEnd={onDrop}
    >
      <Button
        type="button"
        variant="ghost"
        size="icon"
        disabled={disabled}
        aria-label={tr("Arrastrar grupo {0}", { 0: name })}
        aria-describedby={help}
        className="size-6 shrink-0 touch-none cursor-grab text-muted-foreground active:cursor-grabbing [@media(pointer:coarse)]:size-11"
        onPointerDown={(event) => {
          if (!disabled && event.button === 0) controls.start(event);
        }}
        onKeyDown={(event) => {
          if (event.key === "ArrowUp" || event.key === "ArrowDown") {
            event.preventDefault();
            onMove(event.key === "ArrowUp" ? -1 : 1);
          }
        }}
      >
        <GripVertical />
      </Button>
      {children}
    </Reorder.Item>
  );
}
