import { useRef, useState } from "react";
import { Check, Pencil, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAssistant } from "@/lib/assistant";
import { useAction } from "@/lib/hooks";
import { translate as tr, useLanguage } from "@/lib/i18n";
import type { Business } from "@/lib/types";
import { Selectable } from "./context-selection";
import { Busy, Field, Notice } from "./shared";

export function DossierPresentation({
  business,
  onSaved,
}: {
  business: Business;
  onSaved: () => void;
}) {
  useLanguage();
  const assistant = useAssistant();
  const action = useAction();
  const editButton = useRef<HTMLButtonElement>(null);
  const [draft, setDraft] = useState<Business | null>(null);
  const [saved, setSaved] = useState<Business | null>(null);
  // Show the accepted response while the dossier refresh is still in flight.
  const current =
    saved && saved.profile_revision > business.profile_revision
      ? saved
      : business;
  const close = () => {
    setDraft(null);
    action.setError("");
    requestAnimationFrame(() => editButton.current?.focus());
  };
  if (draft)
    return (
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          void action.run(async () => {
            const response = await api<{ business: Business }>(
              "/api/business",
              {
                business_id: draft.id,
                name: draft.name,
                description: draft.description,
                profile_revision: draft.profile_revision,
              },
            );
            if (action.isMounted()) {
              setSaved(response.business);
              close();
              onSaved();
            }
          });
        }}
      >
        <Field label={tr("Presentación del negocio")} id="dossier-presentation">
          <Textarea
            id="dossier-presentation"
            autoFocus
            required
            maxLength={6000}
            className="min-h-40"
            value={draft.description}
            disabled={action.busy}
            onChange={(event) =>
              setDraft({ ...draft, description: event.target.value })
            }
          />
        </Field>
        <Notice error>{action.error}</Notice>
        <div className="flex flex-wrap gap-2">
          <Button
            type="submit"
            size="sm"
            disabled={action.busy || !draft.description.trim()}
          >
            {action.busy ? <Busy /> : <Check />}
            {tr("Guardar cambios")}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={action.busy}
            onClick={close}
          >
            <X />
            {tr("Cancelar")}
          </Button>
        </div>
      </form>
    );
  return (
    <>
      <Selectable
        item={{
          kind: "business",
          source_id: current.id,
          source_version: String(current.profile_revision),
          element_key: "profile",
          title: tr("Presentación de {0}", { 0: current.name }),
          href: "#my-business",
          report_title: tr("Mi negocio"),
          content: {
            key: "profile",
            title: current.name,
            statement: current.description,
          },
        }}
      >
        <p className="whitespace-pre-wrap break-words leading-6 text-muted-foreground">
          {current.description}
        </p>
      </Selectable>
      <Button
        ref={editButton}
        type="button"
        variant="ghost"
        size="sm"
        disabled={assistant?.selecting}
        onClick={() => setDraft({ ...current })}
      >
        <Pencil />
        {tr("Editar presentación")}
      </Button>
    </>
  );
}
