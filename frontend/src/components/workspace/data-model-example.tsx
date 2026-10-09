import { useId } from "react";
import { translate as tr, useLanguage } from "@/lib/i18n";

export function DataModelExample() {
  useLanguage();
  const title = useId();
  return (
    <figure
      aria-labelledby={title}
      className="@container space-y-3 rounded-lg bg-muted/30 p-3"
    >
      <figcaption id={title} className="text-sm font-medium">
        {tr("Ejemplo: varias ventas de un mismo producto")}
      </figcaption>
      <div className="flex flex-col items-stretch @md:flex-row @md:items-center">
        <div className="min-w-0 flex-1 overflow-hidden rounded-lg border bg-background">
          <div className="border-b px-3 py-2">
            <p className="font-medium">{tr("Ventas")}</p>
            <p className="text-xs text-muted-foreground">
              {tr("Varias filas")}
            </p>
          </div>
          <table className="w-full text-left text-xs">
            <thead className="text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 font-normal">
                  venta_id
                </th>
                <th scope="col" className="px-3 py-2 font-normal">
                  producto_id
                </th>
              </tr>
            </thead>
            <tbody>
              {["V-01", "V-02", "V-03"].map((sale) => (
                <tr key={sale} className="border-t">
                  <td className="px-3 py-2">{sale}</td>
                  <td className="px-3 py-2 font-medium text-primary">P-01</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <svg
          aria-hidden="true"
          viewBox="0 0 100 24"
          className="hidden h-9 w-24 shrink-0 text-primary @md:block"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="M0,12 H100 M0,4 L16,12 L0,20 M92,4 V20" />
          <circle cx="28" cy="12" r="4" className="fill-background" />
          <circle cx="76" cy="12" r="4" className="fill-background" />
        </svg>
        <svg
          aria-hidden="true"
          viewBox="0 0 24 72"
          className="h-16 w-6 self-center text-primary @md:hidden"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="M12,0 V72 M4,0 L12,16 L20,0 M4,64 H20" />
          <circle cx="12" cy="28" r="4" className="fill-background" />
          <circle cx="12" cy="48" r="4" className="fill-background" />
        </svg>
        <div className="min-w-0 flex-1 overflow-hidden rounded-lg border bg-background">
          <div className="border-b px-3 py-2">
            <p className="font-medium">{tr("Productos")}</p>
            <p className="text-xs text-muted-foreground">{tr("Una fila")}</p>
          </div>
          <table className="w-full text-left text-xs">
            <thead className="text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 font-normal">
                  producto_id
                </th>
                <th scope="col" className="px-3 py-2 font-normal">
                  {tr("Nombre")}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t">
                <td className="px-3 py-2 font-medium text-primary">P-01</td>
                <td className="px-3 py-2">{tr("Cuaderno")}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <p className="text-xs leading-5 text-muted-foreground">
        {tr(
          "Las tres ventas comparten P-01: se conectan con el mismo cuaderno. Las tres puntas quedan junto a Ventas y la raya junto a Productos.",
        )}
      </p>
    </figure>
  );
}
