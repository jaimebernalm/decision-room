export const isChatStart = (route: string) =>
  route === "ask" || route === "ask/report" || route === "new";
export const reportStarter =
  "Quiero preparar un informe con los datos de mi negocio. ";
export const starterOptions = [
  {
    id: "analyze",
    label: "Analizar mis datos",
    question: "¿Qué te gustaría entender?",
    prompt: "Quiero analizar los datos de mi negocio. ",
  },
  {
    id: "question",
    label: "Resolver una pregunta",
    question: "¿Qué te gustaría saber?",
    prompt: "",
  },
  {
    id: "start",
    label: "Ayúdame a empezar",
    question: "¿Por dónde empezamos?",
    prompt: "Ayúdame a decidir qué debería revisar primero en mi negocio.",
  },
] as const;
