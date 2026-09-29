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
}: {
  url: string;
  disabled?: boolean;
}) {
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
        throw new Error(body.error || "No se ha podido descargar el informe.");
      }
      if (!response.headers.get("Content-Type")?.startsWith("application/pdf"))
        throw new Error("La descarga no contiene un PDF válido.");
      const blob = await response.blob();
      const href = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = "decision-room-informe.pdf";
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(href), 1000);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "No se ha podido descargar el informe.",
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
              aria-label="Descargar informe"
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
            {busy ? "Preparando descarga…" : "Descargar informe"}
          </TooltipContent>
        </Tooltip>
        {busy && (
          <span role="status" className="mt-2 text-xs text-muted-foreground">
            Preparando descarga…
          </span>
        )}
        <Notice error>{error}</Notice>
      </div>
    </TooltipProvider>
  );
}
