export const isChatStart = (route: string) =>
  route === "ask" || route === "ask/report" || route === "new";
export const reportStarter =
  "Quiero preparar un informe con los datos de mi negocio. ";
export const starterOptions = [
  {
    id: "question",
    label: "Resolver una pregunta",
    badge: "Chat",
    question: "¿Qué te gustaría saber?",
    placeholder: "Por ejemplo: ¿qué productos se venden más?",
    entryIntent: "question",
    upcoming: false,
  },
  {
    id: "analyze",
    label: "Analizar mis datos",
    badge: "Informe",
    question: "¿Qué quieres analizar?",
    placeholder: "Por ejemplo: ¿por qué bajaron mis ventas?",
    entryIntent: "analysis",
    upcoming: false,
  },
  {
    id: "predict",
    label: "Predecir lo que viene",
    badge: "Próximamente",
    question: "¿Qué te gustaría predecir?",
    placeholder: "Por ejemplo: las ventas de los próximos meses",
    entryIntent: undefined,
    upcoming: true,
  },
  {
    id: "ideas",
    label: "Ideas para crecer",
    badge: "Próximamente",
    question: "¿Qué te gustaría mejorar?",
    placeholder: "Por ejemplo: ideas para atraer más clientes",
    entryIntent: undefined,
    upcoming: true,
  },
] as const;
export type StarterChoice = (typeof starterOptions)[number]["id"];
