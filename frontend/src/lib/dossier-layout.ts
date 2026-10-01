import type { DossierLayout } from "./types";

export const defaultDossierLayout: DossierLayout = {
  revision: 0,
  groups: [
    { id: "business", name: "Sobre el negocio" },
    { id: "operations", name: "Operativa" },
    { id: "goals", name: "Objetivos y preferencias" },
  ],
  assignments: {},
};
