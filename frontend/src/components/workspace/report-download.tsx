import { translate as tr, useLanguage } from "@/lib/i18n";
import { useState } from "react";
import { Download, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";
import { Notice } from "./shared";
export function ReportDownload({
  url,
  disabled = false,
  kind = "pdf",
}: {
  url: string;
  disabled?: boolean;
  kind?: "pdf" | "html";
}) {
  const expected =
    kind === "pdf" ? "application/pdf" : "application/octet-stream";
  const filename =
    kind === "pdf"
      ? "decision-room-informe.pdf"
      : "decision-room-informe-original.html";
  const label =
    kind === "pdf" ? tr("Descargar informe") : tr("Descargar HTML original");
  useLanguage();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function download() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(url, { credentials: "same-origin" });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(
          body.error || tr("No se ha podido descargar el informe."),
        );
      }
      if (!response.headers.get("Content-Type")?.startsWith(expected))
        throw new Error(
          kind === "pdf"
            ? tr("La descarga no contiene un PDF válido.")
            : tr("La descarga no contiene el archivo esperado."),
        );
      const blob = await response.blob();
      const href = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = filename;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(href), 1000);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : tr("No se ha podido descargar el informe."),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <TooltipProvider>
      <div className="flex flex-col items-end">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              aria-label={label}
              disabled={disabled || busy}
              onClick={download}
            >
              {busy ? (
                <LoaderCircle
                  aria-hidden
                  className="animate-spin motion-reduce:animate-none"
                />
              ) : (
                <Download aria-hidden />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {busy ? tr("Preparando descarga…") : label}
          </TooltipContent>
        </Tooltip>
        {busy && (
          <span role="status" className="mt-2 text-xs text-muted-foreground">
            {tr("Preparando descarga…")}
          </span>
        )}
        <Notice error>{error}</Notice>
      </div>
    </TooltipProvider>
  );
}
