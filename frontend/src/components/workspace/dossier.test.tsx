import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorkspaceState } from "@/lib/workspace";
import { AssistantProvider } from "@/lib/assistant";
import { contextKey, store } from "@/lib/api";
import type { Dossier as DossierData, Fact } from "@/lib/types";
import { SelectionTool } from "./context-selection";
import { Dossier } from "./dossier";

const business = {
  id: "business",
  name: "Tienda de ejemplo",
  description:
    "Texto original del propietario, conservado para consultar su presentación completa.",
  profile_revision: 4,
};
function fact(
  id: string,
  statement: string,
  overrides: Partial<Fact> = {},
): Fact {
  return {
    fact_id: id,
    revision: 3,
    status: "declared",
    created_at: "2026-09-30T12:00:00Z",
    content: {
      kind: "context",
      statement,
      topic: id,
      scope: "business",
      scope_id: null,
      valid_from: null,
      valid_until: null,
      temporal_scope: "unspecified",
    },
    ...overrides,
  };
}
const shop = fact("shop", "Vendemos material escolar y regalos.");
const hours = fact("horario", "Abrimos de lunes a sábado.");
const preference = fact(
  "report_preferences",
  "Preferimos explicaciones breves.",
);
const goal = fact("goal", "Queremos reducir las roturas de stock.", {
  content: {
    ...shop.content,
    topic: "goal",
    kind: "priority",
    statement: "Queremos reducir las roturas de stock.",
  },
});
const proposed = fact("proposal", "El coste incluye el transporte.", {
  status: "proposed",
});
const conflict = fact(
  "conflict",
  "El margen objetivo necesita una corrección.",
  {
    status: "conflicted",
    quote: "Antes dije un margen diferente.",
    conversation_id: "chat-origin",
    alternatives: [{ statement: "Margen objetivo del 30 %." }],
  },
);
const dated = fact("dated", "Los importes de septiembre incluyen impuestos.", {
  content: {
    ...shop.content,
    statement: "Los importes de septiembre incluyen impuestos.",
    kind: "definition",
    scope: "analysis",
    scope_id: "sales",
    valid_from: "2026-09-01",
    valid_until: "2026-09-30",
    temporal_scope: "dated",
  },
});
const unresolved = fact(
  "unresolved",
  "El nuevo horario empieza en septiembre.",
  {
    status: "proposed",
    content: {
      ...hours.content,
      statement: "El nuevo horario empieza en septiembre.",
      temporal_scope: "unresolved",
    },
  },
);
const retired = fact("retired", "Antigua información retirada.", {
  status: "withdrawn",
});
const replaced = fact("replaced", "Información sustituida.", {
  status: "superseded",
});
function dossier(
  facts = [
    shop,
    hours,
    goal,
    preference,
    proposed,
    conflict,
    dated,
    unresolved,
    retired,
    replaced,
  ],
): DossierData {
  return {
    business_id: business.id,
    business,
    memory: {},
    facts,
    history: [retired, replaced],
    datasets: [
      {
        id: "sales",
        title: "Ventas de septiembre",
        version: 2,
        status: "ready",
        files: [],
      },
    ],
  };
}
function setup(
  data = dossier(),
  options: { files?: boolean; error?: string } = {},
) {
  let current = structuredClone(data);
  const writes: Record<string, unknown>[] = [];
  const refresh = vi.fn();
  const fetch = vi.fn(async (_url: string, init: RequestInit) => {
    if (init.method === "POST") {
      const body = JSON.parse(init.body as string);
      writes.push(body);
      if (options.error)
        return {
          ok: false,
          status: 409,
          json: async () => ({ error: options.error }),
        };
      if (_url === "/api/business/dossier-layout") {
        current.layout = {
          revision: body.revision + 1,
          groups: body.groups,
          assignments: body.assignments,
        };
        return { ok: true, json: async () => structuredClone(current.layout) };
      }
      const existing = current.facts.find((f) => f.fact_id === body.fact_id);
      if (existing) {
        current.history.push(structuredClone(existing));
        existing.revision += 1;
        existing.status = body.action === "withdraw" ? "withdrawn" : "declared";
        if (body.content) existing.content = body.content;
      } else if (body.action === "declare") {
        current.facts.push(
          fact("added", body.content.statement, { content: body.content }),
        );
      }
      return { ok: true, json: async () => ({ saved: true }) };
    }
    return { ok: true, json: async () => structuredClone(current) };
  });
  vi.stubGlobal("fetch", fetch);
  render(
    <WorkspaceState.Provider
      value={{
        workspace: {
          business,
          businesses: [business],
          analyses: [],
          configured: true,
          memory: {},
        },
        listing: {
          business_id: business.id,
          conversations: [],
          datasets: { items: [], more: false },
        },
        route: "my-business",
        refresh,
        removeChat: vi.fn(),
      }}
    >
      <AssistantProvider>
        <SelectionTool />
        <Dossier files={options.files} />
      </AssistantProvider>
    </WorkspaceState.Provider>,
  );
  return {
    user: userEvent.setup(),
    writes,
    refresh,
    fetch,
    replace: (next: DossierData) => {
      current = next;
    },
  };
}
async function ready() {
  await screen.findByRole("tab", { name: "Información" });
}
async function menu(user: ReturnType<typeof userEvent.setup>, f: Fact) {
  await user.click(
    screen.getByRole("button", { name: `Acciones: ${f.content.statement}` }),
  );
}

describe("compact business dossier", () => {
  it("groups every active fact and only shows material status, dates and scope", async () => {
    setup();
    await ready();
    expect(
      screen.getByRole("button", { name: "Sobre el negocio 1" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: "Operativa 2" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(
      screen.getByRole("button", { name: "Objetivos y preferencias 2" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("button", { name: "Por revisar 3" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByText("Ventas de septiembre · 2026-09-01 — 2026-09-30"),
    ).toBeVisible();
    expect(screen.getByText("Por confirmar")).toBeVisible();
    expect(screen.getByText("En conflicto")).toBeVisible();
    expect(screen.getByText("Fechas por aclarar")).toBeVisible();
    expect(screen.queryByText("Confirmado por ti")).not.toBeInTheDocument();
    expect(screen.queryByText("Todo el negocio")).not.toBeInTheDocument();
    expect(
      screen.queryByText(retired.content.statement),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(replaced.content.statement),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Origen y vigencia" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(business.description)).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem")).not.toBeInTheDocument();
  });
  it("folds groups without losing information", async () => {
    const { user } = setup();
    await ready();
    await user.click(
      screen.getByRole("button", { name: "Sobre el negocio 1" }),
    );
    expect(screen.queryByText(shop.content.statement)).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Sobre el negocio 1" }),
    );
    expect(screen.getByText(shop.content.statement)).toBeVisible();
  });
  it("keeps the original presentation and editing inside Information", async () => {
    const { user } = setup();
    await ready();
    await user.click(
      screen.getByRole("button", { name: "Ver presentación original" }),
    );
    expect(screen.getByText(business.description)).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Editar presentación" }),
    ).toHaveAttribute("href", "#business");
    await user.click(screen.getByRole("tab", { name: "Datos" }));
    expect(screen.queryByText(business.description)).not.toBeInTheDocument();
    expect(screen.getByText("Ventas de septiembre")).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "Historial" }));
    expect(screen.queryByText(business.description)).not.toBeInTheDocument();
    expect(screen.getByText(retired.content.statement)).toBeVisible();
    expect(screen.getByText(replaced.content.statement)).toBeVisible();
  });
  it("shows a brief presentation when there are no active facts", async () => {
    setup(dossier([retired]));
    await ready();
    expect(
      within(
        screen.getByRole("region", { name: "Presentación del negocio" }),
      ).getByText(business.description),
    ).toBeVisible();
    expect(screen.getByText("Un contexto que crece contigo")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /^Acciones:/ }),
    ).not.toBeInTheDocument();
  });
  it("opens provenance, alternatives and exact revision from the menu", async () => {
    const { user } = setup();
    await ready();
    await menu(user, conflict);
    expect(
      screen.queryByRole("menuitem", { name: "Confirmar" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("menuitem", { name: "Ver detalles" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(conflict.quote!)).toBeVisible();
    expect(
      within(dialog).getByText("Alternativa: Margen objetivo del 30 %."),
    ).toBeVisible();
    expect(within(dialog).getByText(/revisión 3/)).toBeVisible();
    expect(
      within(dialog).getByRole("link", { name: "Ver conversación de origen" }),
    ).toHaveAttribute("href", "#chat/chat-origin");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it("supports keyboard navigation from row actions to details", async () => {
    const { user } = setup();
    await ready();
    const trigger = screen.getByRole("button", {
      name: `Acciones: ${shop.content.statement}`,
    });
    trigger.focus();
    await user.keyboard("{Enter}{ArrowDown}{Enter}");
    expect(
      screen.getByRole("dialog", { name: "Detalles de la información" }),
    ).toBeVisible();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
  it("edits the selected fact with its exact revision and refreshes the row", async () => {
    const { user, writes, refresh } = setup();
    await ready();
    await menu(user, shop);
    await user.click(screen.getByRole("menuitem", { name: "Editar" }));
    const input = screen.getByRole("textbox", { name: "Información" });
    await user.clear(input);
    await user.type(input, "Vendemos material escolar.");
    await user.click(
      screen.getByRole("button", { name: "Guardar información" }),
    );
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({
      business_id: business.id,
      action: "correct",
      fact_id: shop.fact_id,
      expected_revision: 3,
      change_kind: "historical",
      content: { statement: "Vendemos material escolar." },
      request_key: expect.any(String),
    });
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(await screen.findByText("Vendemos material escolar.")).toBeVisible();
    expect(refresh).toHaveBeenCalledOnce();
  });
  it("preserves the editing draft and idempotency key when saving fails", async () => {
    const { user, writes } = setup(dossier(), {
      error: "El recuerdo ha cambiado. Consulta su última revisión.",
    });
    await ready();
    await menu(user, shop);
    await user.click(screen.getByRole("menuitem", { name: "Editar" }));
    const input = screen.getByRole("textbox", { name: "Información" });
    await user.clear(input);
    await user.type(input, "Corrección conservada.");
    await user.click(
      screen.getByRole("button", { name: "Guardar información" }),
    );
    expect(
      await screen.findByText(
        "El recuerdo ha cambiado. Consulta su última revisión.",
      ),
    ).toBeVisible();
    expect(input).toHaveValue("Corrección conservada.");
    await user.click(
      screen.getByRole("button", { name: "Guardar información" }),
    );
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[0].request_key).toBe(writes[1].request_key);
    expect(screen.getByRole("dialog")).toBeVisible();
  });
  it("withdraws only the chosen fact and removes it from the active list", async () => {
    const { user, writes } = setup();
    await ready();
    await menu(user, shop);
    await user.click(screen.getByRole("menuitem", { name: "Retirar" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({
      action: "withdraw",
      business_id: business.id,
      fact_id: shop.fact_id,
      expected_revision: 3,
    });
    await waitFor(() =>
      expect(
        screen.queryByText(shop.content.statement),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByText(hours.content.statement)).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "Historial" }));
    expect(screen.getByText(shop.content.statement)).toBeVisible();
  });
  it("keeps a fact visible and displays an error if withdrawal fails", async () => {
    const { user } = setup(dossier(), { error: "El recuerdo ha cambiado." });
    await ready();
    await menu(user, shop);
    await user.click(screen.getByRole("menuitem", { name: "Retirar" }));
    expect(await screen.findByText("El recuerdo ha cambiado.")).toBeVisible();
    expect(screen.getByText(shop.content.statement)).toBeVisible();
  });
  it("confirms proposals but requires editing to resolve ambiguous dates", async () => {
    const { user, writes } = setup();
    await ready();
    await menu(user, unresolved);
    expect(
      screen.queryByRole("menuitem", { name: "Confirmar" }),
    ).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    await menu(user, proposed);
    await user.click(screen.getByRole("menuitem", { name: "Confirmar" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({
      action: "confirm",
      fact_id: proposed.fact_id,
      expected_revision: 3,
    });
    await waitFor(() =>
      expect(screen.queryByText("Por confirmar")).not.toBeInTheDocument(),
    );
  });
  it("adds information through the existing declaration contract", async () => {
    const { user, writes } = setup();
    await ready();
    await user.click(
      screen.getByRole("button", { name: "Añadir información" }),
    );
    await user.type(
      screen.getByRole("textbox", { name: "Información" }),
      "También vendemos cuadernos.",
    );
    await user.click(
      screen.getByRole("button", { name: "Guardar información" }),
    );
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({
      action: "declare",
      business_id: business.id,
      content: { statement: "También vendemos cuadernos." },
    });
    expect(writes[0]).not.toHaveProperty("fact_id");
    expect(
      await screen.findByText("También vendemos cuadernos."),
    ).toBeVisible();
  });
  it("confirms a proposal directly with its revision, without opening a menu", async () => {
    const { user, writes } = setup();
    await ready();
    await user.click(
      screen.getByRole("button", {
        name: `Confirmar: ${proposed.content.statement}`,
      }),
    );
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({
      action: "confirm",
      business_id: business.id,
      fact_id: proposed.fact_id,
      expected_revision: 3,
      request_key: expect.any(String),
    });
    await waitFor(() =>
      expect(screen.queryByText("Por confirmar")).not.toBeInTheDocument(),
    );
    expect(screen.getByText(proposed.content.statement)).toBeVisible();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: `Confirmar: ${unresolved.content.statement}`,
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: `Confirmar: ${conflict.content.statement}`,
      }),
    ).not.toBeInTheDocument();
  });
  it("discards a proposal directly and preserves it in the history", async () => {
    const { user, writes } = setup();
    await ready();
    await user.click(
      screen.getByRole("button", {
        name: `Descartar: ${proposed.content.statement}`,
      }),
    );
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({
      action: "withdraw",
      fact_id: proposed.fact_id,
      expected_revision: 3,
    });
    await waitFor(() =>
      expect(
        screen.queryByText(proposed.content.statement),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByText(shop.content.statement)).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "Historial" }));
    expect(screen.getByText(proposed.content.statement)).toBeVisible();
  });
  it("keeps the proposal and direct actions when confirmation fails", async () => {
    const { user } = setup(dossier(), { error: "El recuerdo ha cambiado." });
    await ready();
    await user.click(
      screen.getByRole("button", {
        name: `Confirmar: ${proposed.content.statement}`,
      }),
    );
    expect(await screen.findByText("El recuerdo ha cambiado.")).toBeVisible();
    expect(screen.getByText(proposed.content.statement)).toBeVisible();
    expect(
      screen.getByRole("button", {
        name: `Confirmar: ${proposed.content.statement}`,
      }),
    ).toBeEnabled();
  });
  it("compares conflict versions, saves the selected scope and dates, and removes the conflict", async () => {
    const alternative = {
      ...dated.content,
      statement: "El margen objetivo de septiembre es del 30 %.",
    };
    const { user, writes } = setup(
      dossier([{ ...conflict, alternatives: [{ content: alternative }] }]),
    );
    await ready();
    await user.click(
      screen.getByRole("button", { name: "Resolver conflicto" }),
    );
    const versions = screen.getByRole("region", {
      name: "Versiones en conflicto",
    });
    expect(
      within(versions).getByText(conflict.content.statement),
    ).toBeVisible();
    expect(within(versions).getByText(alternative.statement)).toBeVisible();
    await user.click(screen.getByRole("radio", { name: "Usar alternativa 1" }));
    expect(screen.getByRole("textbox", { name: "Información" })).toHaveValue(
      alternative.statement,
    );
    expect(writes).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Guardar solución" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({
      action: "correct",
      fact_id: conflict.fact_id,
      expected_revision: 3,
      change_kind: "historical",
      content: alternative,
    });
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(screen.getByText(alternative.statement)).toBeVisible();
    expect(screen.queryByText("En conflicto")).not.toBeInTheDocument();
  });
  it("resolves a conflict without alternatives by writing a correction", async () => {
    const { user, writes } = setup(
      dossier([{ ...conflict, alternatives: [] }]),
    );
    await ready();
    await user.click(
      screen.getByRole("button", { name: "Resolver conflicto" }),
    );
    const input = screen.getByRole("textbox", { name: "Información" });
    await user.clear(input);
    await user.type(input, "El margen objetivo es del 25 %.");
    await user.click(screen.getByRole("button", { name: "Guardar solución" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({
      action: "correct",
      content: { statement: "El margen objetivo es del 25 %." },
    });
  });
  it("cancels conflict resolution without writing and restores focus to the direct button", async () => {
    const { user, writes } = setup();
    await ready();
    const trigger = screen.getByRole("button", {
      name: "Resolver conflicto",
    });
    await user.click(trigger);
    await user.click(screen.getByRole("radio", { name: "Usar alternativa 1" }));
    await user.keyboard("{Escape}");
    expect(writes).toHaveLength(0);
    expect(trigger).toHaveFocus();
    expect(screen.getByText("En conflicto")).toBeVisible();
  });
  it("preserves a conflict solution and retry key if saving fails", async () => {
    const { user, writes } = setup(dossier(), {
      error: "El recuerdo ha cambiado.",
    });
    await ready();
    await user.click(
      screen.getByRole("button", { name: "Resolver conflicto" }),
    );
    await user.click(screen.getByRole("radio", { name: "Usar alternativa 1" }));
    await user.click(screen.getByRole("button", { name: "Guardar solución" }));
    expect(await screen.findByText("El recuerdo ha cambiado.")).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Información" })).toHaveValue(
      "Margen objetivo del 30 %.",
    );
    await user.click(screen.getByRole("button", { name: "Guardar solución" }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[0].request_key).toBe(writes[1].request_key);
    expect(
      screen.getByRole("dialog", { name: "Resolver conflicto" }),
    ).toBeVisible();
  });
  it("preserves versioned context selection for compact rows and the original profile", async () => {
    const { user } = setup();
    await ready();
    await user.click(
      screen.getByRole("button", { name: "Ver presentación original" }),
    );
    await user.click(screen.getByRole("button", { name: "Seleccionar" }));
    await user.click(
      screen.getByRole("button", {
        name: `Seleccionar: ${shop.content.statement}`,
      }),
    );
    await user.click(
      screen.getByRole("button", {
        name: `Seleccionar: Presentación de ${business.name}`,
      }),
    );
    expect(store.get(contextKey(business.id), {})).toMatchObject({
      context_references: [
        {
          kind: "memory",
          source_id: shop.fact_id,
          source_version: "3",
          element_key: "fact",
        },
        {
          kind: "business",
          source_id: business.id,
          source_version: "4",
          element_key: "profile",
        },
      ],
    });
  });
  it("still opens the files route directly on data", async () => {
    setup(dossier(), { files: true });
    await ready();
    expect(screen.getByRole("tab", { name: "Datos" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByText("Ventas de septiembre")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Ver presentación original" }),
    ).not.toBeInTheDocument();
  });
  it("marks a conflict choice visibly, deduplicates the current version and requires a choice before saving", async () => {
    const { user, writes } = setup(
      dossier([
        {
          ...conflict,
          alternatives: [
            { content: conflict.content },
            ...conflict.alternatives!,
          ],
        },
      ]),
    );
    await ready();
    await user.click(
      screen.getByRole("button", { name: "Resolver conflicto" }),
    );
    expect(
      screen.getByRole("button", { name: "Guardar solución" }),
    ).toBeDisabled();
    const choices = screen.getAllByRole("radio");
    expect(choices).toHaveLength(3);
    const alternate = screen.getByRole("radio", { name: "Usar alternativa 2" });
    await user.click(alternate.closest("label")!);
    expect(alternate).toBeChecked();
    expect(screen.getByText("Seleccionada")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Solución elegida: Alternativa 2",
    );
    expect(writes).toHaveLength(0);
    await user.click(
      screen.getByRole("radio", { name: "Usar información actual" }),
    );
    expect(alternate).not.toBeChecked();
    expect(screen.getByRole("textbox", { name: "Información" })).toHaveValue(
      conflict.content.statement,
    );
  });
  it("creates, renames and reorders groups, then moves a fact without editing its memory", async () => {
    const { user, writes } = setup();
    await ready();
    await user.click(
      screen.getByRole("button", { name: "Personalizar grupos" }),
    );
    const first = screen.getByRole("textbox", { name: "Nombre del grupo 1" });
    await user.clear(first);
    await user.type(first, "Mi empresa");
    await user.type(
      screen.getByRole("textbox", { name: "Nombre del nuevo grupo" }),
      "Clientes",
    );
    expect(screen.getByRole("button", { name: "Añadir grupo" })).toBeDisabled();
    await user.type(
      screen.getByRole("textbox", { name: "Descripción del nuevo grupo" }),
      "Perfil y necesidades de nuestros clientes.",
    );
    await user.clear(
      screen.getByRole("textbox", { name: "Descripción del grupo 1" }),
    );
    await user.type(
      screen.getByRole("textbox", { name: "Descripción del grupo 1" }),
      "Características generales de la empresa.",
    );
    await user.click(screen.getByRole("button", { name: "Añadir grupo" }));
    await user.click(screen.getByRole("button", { name: "Subir grupo 4" }));
    await user.click(screen.getByRole("button", { name: "Guardar grupos" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(writes[0]).toMatchObject({
      business_id: business.id,
      revision: 0,
      groups: [
        {
          id: "business",
          name: "Mi empresa",
          description: "Características generales de la empresa.",
        },
        { id: "operations", name: "Operativa" },
        {
          id: expect.any(String),
          name: "Clientes",
          description: "Perfil y necesidades de nuestros clientes.",
        },
        { id: "goals", name: "Objetivos y preferencias" },
      ],
    });
    const custom = (writes[0].groups as { id: string; name: string }[])[2];
    expect(screen.getByRole("button", { name: "Mi empresa 1" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Clientes 0" })).toBeVisible();
    await menu(user, shop);
    await user.click(screen.getByRole("menuitem", { name: "Mover a grupo" }));
    const destination = await screen.findByRole("menuitemradio", {
      name: "Clientes",
    });
    destination.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[1]).toMatchObject({
      revision: 1,
      assignments: { [shop.fact_id]: custom.id },
    });
    expect(writes[1]).not.toHaveProperty("action");
    await user.keyboard("{Escape}");
    expect(
      await screen.findByRole("button", { name: "Clientes 1" }),
    ).toBeVisible();
  });
  it("keeps pending facts in review and preserves facts when their group is deleted", async () => {
    const { user, writes } = setup({
      ...dossier([shop, proposed]),
      layout: {
        revision: 2,
        groups: [{ id: "custom", name: "Clientes" }],
        assignments: { [shop.fact_id]: "custom", [proposed.fact_id]: "custom" },
      },
    });
    await ready();
    expect(screen.getByRole("button", { name: "Por revisar 1" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Clientes 1" })).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Personalizar grupos" }),
    );
    await user.click(screen.getByRole("button", { name: "Eliminar grupo 1" }));
    await user.click(screen.getByRole("button", { name: "Guardar grupos" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(writes[0]).toMatchObject({
      revision: 2,
      groups: [],
      assignments: {},
    });
    expect(screen.getByRole("button", { name: "Sin grupo 1" })).toBeVisible();
    expect(screen.getByText(shop.content.statement)).toBeVisible();
    expect(screen.getByText(proposed.content.statement)).toBeVisible();
  });
  it("validates names and preserves the group draft on a stale revision", async () => {
    const { user } = setup(dossier(), { error: "Los grupos han cambiado." });
    await ready();
    await user.click(
      screen.getByRole("button", { name: "Personalizar grupos" }),
    );
    const name = screen.getByRole("textbox", { name: "Nombre del grupo 1" });
    await user.clear(name);
    await user.type(name, "Operativa");
    expect(
      screen.getByRole("button", { name: "Guardar grupos" }),
    ).toBeDisabled();
    await user.clear(name);
    await user.type(name, "Clientes");
    await user.click(screen.getByRole("button", { name: "Guardar grupos" }));
    expect(await screen.findByText("Los grupos han cambiado.")).toBeVisible();
    expect(name).toHaveValue("Clientes");
  });
  it("cancels grouping without saving and restores its trigger focus", async () => {
    const { user, writes } = setup();
    await ready();
    const trigger = screen.getByRole("button", { name: "Personalizar grupos" });
    await user.click(trigger);
    await user.type(
      screen.getByRole("textbox", { name: "Nombre del nuevo grupo" }),
      "Draft",
    );
    await user.keyboard("{Escape}");
    expect(writes).toHaveLength(0);
    expect(trigger).toHaveFocus();
  });
  it("shows saved custom groups even before the business has any active information", async () => {
    setup({
      ...dossier([]),
      layout: {
        revision: 1,
        groups: [{ id: "clients", name: "Clientes" }],
        assignments: {},
      },
    });
    await ready();
    expect(screen.getByRole("button", { name: "Clientes 0" })).toBeVisible();
    expect(
      screen.getByText("Mueve información aquí desde el menú de una fila."),
    ).toBeVisible();
  });
  it("adds a description to an existing group without losing its manual assignments", async () => {
    const { user, writes } = setup({
      ...dossier([shop]),
      layout: {
        revision: 2,
        groups: [{ id: "clients", name: "Clientes" }],
        assignments: { [shop.fact_id]: "clients" },
      },
    });
    await ready();
    await user.click(
      screen.getByRole("button", { name: "Personalizar grupos" }),
    );
    const description = screen.getByRole("textbox", {
      name: "Descripción del grupo 1",
    });
    expect(description).toHaveValue("");
    await user.type(description, "Información sobre familias y estudiantes.");
    await user.click(screen.getByRole("button", { name: "Guardar grupos" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(writes[0]).toMatchObject({
      revision: 2,
      groups: [
        {
          id: "clients",
          name: "Clientes",
          description: "Información sobre familias y estudiantes.",
        },
      ],
      assignments: { [shop.fact_id]: "clients" },
    });
    expect(
      screen.getByText("Información sobre familias y estudiantes."),
    ).toBeVisible();
  });
});
