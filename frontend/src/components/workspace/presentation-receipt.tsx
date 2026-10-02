import { translate as tr, useLanguage } from "@/lib/i18n";
import { useEffect, useRef, useState } from "react";
import { RotateCcw, ArrowUpRight } from "lucide-react";
import { toast } from "sonner";
import { useWorkspace } from "@/lib/workspace";
import { useAction } from "@/lib/hooks";
import { api } from "@/lib/api";
import type { PresentationReceipt } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Notice } from "./shared";
export function PresentationChangeReceipt({
  receipt,
}: {
  receipt: PresentationReceipt;
}) {
  useLanguage();
  const { workspace } = useWorkspace(),
    action = useAction();
  const previous =
    receipt.current_revision != null &&
    receipt.current_revision !== receipt.revision;
  const unavailable = receipt.available === false;
  const [undone, setUndone] = useState(false);
  const request = useRef<string | null>(null);
  useEffect(() => {
    dispatchEvent(new Event("dr-presentation"));
  }, [receipt.report_id, receipt.revision]);
  return (
    <div className="space-y-3 rounded-lg border p-4">
      <p className="text-xs text-muted-foreground">
        {tr("Presentación guardada · Versión ")}
        {receipt.revision}
      </p>
      <p className="text-sm font-medium">{receipt.title}</p>
      <div className="flex flex-wrap gap-2">
        {receipt.href && (
          <Button size="sm" variant="outline" asChild>
            <a href={receipt.href}>
              {tr("Ver informe")}
              <ArrowUpRight />
            </a>
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          disabled={action.busy || undone || previous || unavailable}
          onClick={() =>
            void action.run(async () => {
              request.current ??= crypto.randomUUID();
              await api(`/api/presentation/${receipt.report_id}`, {
                business_id: workspace.business?.id,
                base_version: receipt.base_version,
                revision: receipt.revision,
                request_key: request.current,
                restore_revision: receipt.previous_revision,
              });
              setUndone(true);
              dispatchEvent(new Event("dr-presentation"));
              toast.success(tr("Cambio deshecho en Inicio, informe y PDF"));
            })
          }
        >
          <RotateCcw />
          {undone
            ? tr("Deshecho")
            : unavailable
              ? tr("Informe no disponible")
              : previous
                ? tr("Versión anterior")
                : tr("Deshacer este cambio")}
        </Button>
      </div>
      <Notice error>{action.error}</Notice>
    </div>
  );
}
