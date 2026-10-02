import type { DossierLayout } from "./types";

export const defaultDossierLayout: DossierLayout = {
  revision: 0,
  groups: [
    {
      id: "business",
      name: "Sobre el negocio",
      description:
        "Actividad del negocio, productos, clientes y características generales.",
    },
    {
      id: "operations",
      name: "Operativa",
      description:
        "Horarios, procesos, recursos disponibles y significado de los datos.",
    },
    {
      id: "goals",
      name: "Objetivos y preferencias",
      description:
        "Prioridades, metas y preferencias para orientar las recomendaciones.",
    },
  ],
  assignments: {},
};
