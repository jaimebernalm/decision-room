import { translate as tr, useLanguage } from "@/lib/i18n";
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
import { Brand } from "@/components/brand";

export function EntryFrame({
  children,
  action,
}: {
  children: ReactNode;
  action?: ReactNode;
}) {
  useLanguage();
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
        {tr("Saltar al contenido")}
      </a>
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-5 py-6 sm:px-8">
        <a
          href="#welcome"
          className="flex shrink-0 items-center gap-2.5 text-base font-semibold tracking-tight"
          aria-label={tr("Decision Room, bienvenida")}
        >
          <Brand />
        </a>
        {action}
      </header>
      <main id="entry-main" tabIndex={-1} className="flex-1 outline-none">
        {children}
      </main>
      <footer className="mx-auto flex w-full max-w-6xl flex-wrap justify-between gap-2 px-5 py-6 text-xs text-muted-foreground sm:px-8">
        <span>{tr("De tus datos a tu próxima decisión.")}</span>
        <span>{tr("Decision Room · Versión de pruebas")}</span>
      </footer>
    </div>
  );
}

export function Welcome({ signedIn }: { signedIn: boolean }) {
  useLanguage();
  const start = signedIn ? "#onboarding" : "#login/start";
  return (
    <EntryFrame
      action={
        <Button asChild variant="ghost" className="rounded-full">
          <a href={signedIn ? "#home" : "#login"}>
            {signedIn ? tr("Mi espacio") : tr("Iniciar sesión")}
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
              {tr("Un poco más de claridad para tu negocio")}
            </p>
            <h1 className="max-w-xl text-4xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
              {tr("Tus datos tienen mucho que contarte.")}
            </h1>
            <p className="mt-6 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg">
              {tr(
                "Entiende qué está pasando en tu negocio y qué merece tu atención. Comparte tus datos y recibe un primer informe que puedas explorar y preguntar.",
              )}
            </p>
            <Button
              asChild
              size="lg"
              className="mt-8 h-12 rounded-full px-7 text-base"
            >
              <a href={start}>
                {tr("Empezar")}
                <ArrowRight />
              </a>
            </Button>
            <p className="mt-4 text-xs text-muted-foreground">
              {tr(
                "Te acompañamos paso a paso. Empieza con los datos que ya tienes.",
              )}
            </p>
          </div>
          <div
            className="relative rounded-[2rem] bg-primary/5 p-4 sm:p-7"
            aria-label={tr("Vista ilustrativa del informe")}
          >
            <div className="rounded-2xl border border-border/70 bg-card p-5 shadow-xl shadow-primary/5 sm:p-7">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold">
                  {tr("Tu negocio, de un vistazo")}
                </span>
                <span className="rounded-full bg-muted px-2.5 py-1 text-[10px] text-muted-foreground">
                  {tr("Ejemplo")}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {tr("Una visión clara, con datos detrás.")}
              </p>
              <div className="mt-6 rounded-xl bg-muted/50 p-4">
                <div className="flex items-center gap-2 text-xs font-medium">
                  <BarChart3 className="size-4 text-primary" />
                  {tr("Evolución de tus ventas")}
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
                  {tr("Gráfico ilustrativo · Tus resultados usarán tus datos")}
                </p>
              </div>
              <div className="mt-4 flex items-start gap-3 rounded-xl bg-primary/5 p-4">
                <span className="rounded-full bg-background p-1.5 text-primary">
                  <Check className="size-4" />
                </span>
                <div>
                  <p className="text-sm font-medium">
                    {tr("Descubre qué merece una mirada")}
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    {tr("Hallazgos explicados, con sus fuentes y límites.")}
                  </p>
                </div>
              </div>
              <div className="mt-5 flex items-center justify-between rounded-full border px-4 py-3 text-xs text-muted-foreground">
                <span>{tr("¿Qué debería revisar primero?")}</span>
                <ArrowRight className="size-4 text-primary" />
              </div>
            </div>
          </div>
        </section>
        <section
          aria-label={tr("Cómo empezar")}
          className="mt-16 grid gap-7 border-t pt-9 sm:grid-cols-3 lg:mt-24"
        >
          {[
            {
              icon: MessageCircle,
              title: tr("01 · Cuéntanos tu negocio"),
              text: tr("Qué vendes, cómo trabajas y qué te gustaría entender."),
            },
            {
              icon: BarChart3,
              title: tr("02 · Comparte tus datos"),
              text: tr(
                "Comparte tus archivos de ventas o actividad. Revisaremos qué se puede analizar.",
              ),
            },
            {
              icon: FileText,
              title: tr("03 · Explora tu primer informe"),
              text: tr(
                "Aclara lo necesario y descubre resultados con cifras que puedes comprobar.",
              ),
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
