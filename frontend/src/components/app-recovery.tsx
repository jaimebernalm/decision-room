import { translate as tr } from "@/lib/i18n";
import { Component, type ReactNode } from "react";

export class AppRecovery extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="flex min-h-screen items-center justify-center bg-background p-6 text-foreground">
        <div className="max-w-md space-y-4 rounded-xl border p-6" role="alert">
          <h1 className="text-xl font-semibold">
            {tr("No se ha podido cargar esta vista")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {tr(
              "Puede haber una versión nueva de la plataforma. Recarga para continuar; los mensajes y archivos guardados siguen disponibles.",
            )}
          </p>
          <button
            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground"
            onClick={() => location.reload()}
          >
            {tr("Recargar la página")}
          </button>
        </div>
      </main>
    );
  }
}
