import type { ReactNode } from "react";
import {
  ArrowRight,
  BarChart3,
  Check,
  FileText,
  MessageCircle,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export function EntryFrame({
  children,
  action,
}: {
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="entry-page flex min-h-svh flex-col">
      <a
        className="skip-link"
        href="#entry-main"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("entry-main")?.focus();
        }}
      >
        Saltar al contenido
      </a>
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-5 py-6 sm:px-8">
        <a
          href="#welcome"
          className="flex shrink-0 items-center gap-2.5 text-base font-semibold tracking-tight"
          aria-label="Decision Room, bienvenida"
        >
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <BarChart3 className="size-5" />
          </span>
          Decision Room
        </a>
        {action}
      </header>
      <main id="entry-main" tabIndex={-1} className="flex-1 outline-none">
        {children}
      </main>
      <footer className="mx-auto flex w-full max-w-6xl flex-wrap justify-between gap-2 px-5 py-6 text-xs text-muted-foreground sm:px-8">
        <span>De tus datos a tu próxima decisión.</span>
        <span>Decision Room · Versión de pruebas</span>
      </footer>
    </div>
  );
}

export function Welcome({ signedIn }: { signedIn: boolean }) {
  const start = signedIn ? "#onboarding" : "#login/start";
  return (
    <EntryFrame
      action={
        <Button asChild variant="ghost" className="rounded-full">
          <a href={signedIn ? "#home" : "#login"}>
            {signedIn ? "Mi espacio" : "Iniciar sesión"}
            <ArrowRight className="size-4" />
          </a>
        </Button>
      }
    >
      <div className="mx-auto max-w-6xl px-5 pb-8 pt-10 sm:px-8 sm:pt-16 lg:pt-24">
        <section className="grid items-center gap-14 lg:grid-cols-[1.05fr_1fr] lg:gap-16">
          <div>
            <p className="mb-6 inline-flex items-center gap-2 rounded-full bg-primary/8 px-3.5 py-2 text-xs font-medium text-primary">
              <Sparkles className="size-3.5" />
              Un poco más de claridad para tu negocio
            </p>
            <h1 className="max-w-xl text-4xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
              Tus datos tienen mucho que contarte.
            </h1>
            <p className="mt-6 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg">
              Entiende qué está pasando en tu negocio y qué merece tu atención.
              Comparte tus datos y recibe un primer informe que puedas explorar
              y preguntar.
            </p>
            <Button
              asChild
              size="lg"
              className="mt-8 h-12 rounded-full px-7 text-base"
            >
              <a href={start}>
                Empezar
                <ArrowRight />
              </a>
            </Button>
            <p className="mt-4 text-xs text-muted-foreground">
              Te acompañamos paso a paso. Empieza con los datos que ya tienes.
            </p>
          </div>
          <div
            className="relative rounded-[2rem] bg-primary/5 p-4 sm:p-7"
            aria-label="Vista ilustrativa del informe"
          >
            <div className="rounded-2xl border border-border/70 bg-card p-5 shadow-xl shadow-primary/5 sm:p-7">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold">
                  Tu negocio, de un vistazo
                </span>
                <span className="rounded-full bg-muted px-2.5 py-1 text-[10px] text-muted-foreground">
                  Ejemplo
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Una visión clara, con datos detrás.
              </p>
              <div className="mt-6 rounded-xl bg-muted/50 p-4">
                <div className="flex items-center gap-2 text-xs font-medium">
                  <BarChart3 className="size-4 text-primary" />
                  Evolución de tus ventas
                </div>
                <div
                  className="mt-5 flex h-28 items-end gap-3 border-b border-border px-1"
                  aria-hidden="true"
                >
                  {[40, 58, 48, 75, 67, 88, 100].map((height, i) => (
                    <div
                      key={i}
                      className="flex-1 rounded-t-md bg-primary/65 last:bg-primary"
                      style={{ height: `${height}%` }}
                    />
                  ))}
                </div>
                <p className="mt-3 text-[10px] text-muted-foreground">
                  Gráfico ilustrativo · Tus resultados usarán tus datos
                </p>
              </div>
              <div className="mt-4 flex items-start gap-3 rounded-xl bg-primary/5 p-4">
                <span className="rounded-full bg-background p-1.5 text-primary">
                  <Check className="size-4" />
                </span>
                <div>
                  <p className="text-sm font-medium">
                    Descubre qué merece una mirada
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    Hallazgos explicados, con sus fuentes y límites.
                  </p>
                </div>
              </div>
              <div className="mt-5 flex items-center justify-between rounded-full border px-4 py-3 text-xs text-muted-foreground">
                <span>¿Qué debería revisar primero?</span>
                <ArrowRight className="size-4 text-primary" />
              </div>
            </div>
          </div>
        </section>
        <section
          aria-label="Cómo empezar"
          className="mt-16 grid gap-7 border-t pt-9 sm:grid-cols-3 lg:mt-24"
        >
          {[
            {
              icon: MessageCircle,
              title: "01 · Cuéntanos tu negocio",
              text: "Qué vendes, cómo trabajas y qué te gustaría entender.",
            },
            {
              icon: BarChart3,
              title: "02 · Comparte tus datos",
              text: "Comparte tus archivos de ventas o actividad. Revisaremos qué se puede analizar.",
            },
            {
              icon: FileText,
              title: "03 · Explora tu primer informe",
              text: "Aclara lo necesario y descubre resultados con cifras que puedes comprobar.",
            },
          ].map(({ icon: Icon, title, text }) => (
            <div key={title}>
              <Icon className="mb-4 size-5 text-primary" />
              <h2 className="text-sm font-semibold">{title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {text}
              </p>
            </div>
          ))}
        </section>
      </div>
    </EntryFrame>
  );
}
