import { useId, useRef, useState } from "react";
import { ArrowUpRight, FileText } from "lucide-react";
import { translate as tr, useLanguage } from "@/lib/i18n";
import { useAction } from "@/lib/hooks";
import { api } from "@/lib/api";
import type { ReportOffer } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Notice } from "./shared";

// The chat only offers a report. It starts when the owner presses the button,
// with the objective they can edit; a typed reply never starts it.
export function ReportOfferCard({
  offer,
  chatId,
  businessId,
  onAccepted,
}: {
  offer: ReportOffer;
  chatId: string;
  businessId: string;
  onAccepted: () => void;
}) {
  useLanguage();
  const field = useId();
  const action = useAction();
  const [objective, setObjective] = useState(offer.objective);
  // One request key per objective: a double click reuses it, an edit gets a new one.
  const request = useRef<{ key: string; objective: string } | null>(null);
  if (offer.status === "accepted")
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-lg border p-4 text-sm">
        <span>{tr("Informe pedido.")}</span>
        {offer.job_id && (
          <Button asChild variant="ghost" size="sm">
            <a href={`#analysis/${offer.job_id}`}>
              {tr("Ver informe")}
              <ArrowUpRight />
            </a>
          </Button>
        )}
      </div>
    );
  if (offer.status !== "open") return null;
  const text = objective.trim();
  return (
    <div className="min-w-0 space-y-3 rounded-lg border p-4">
      <Label htmlFor={field}>{tr("Objetivo del informe")}</Label>
      <Textarea
        id={field}
        value={objective}
        maxLength={600}
        onChange={(event) => setObjective(event.target.value)}
      />
      <p className="text-xs text-muted-foreground">
        {tr(
          "Tarda unos cinco minutos y una comprobación independiente revisa sus cifras.",
        )}
      </p>
      <Button
        size="sm"
        disabled={action.busy || !text}
        onClick={() =>
          void action.run(async () => {
            if (request.current?.objective !== text)
              request.current = { key: crypto.randomUUID(), objective: text };
            await api(`/api/chats/${chatId}/accept-offer`, {
              business_id: businessId,
              offer_id: offer.id,
              objective: text,
              request_key: request.current.key,
            });
            if (action.isMounted()) onAccepted();
          })
        }
      >
        <FileText />
        {tr("Preparar informe")}
      </Button>
      <Notice error>{action.error}</Notice>
    </div>
  );
}
