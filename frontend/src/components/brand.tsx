import { BarChart3 } from "lucide-react";

export function Brand() {
  return (
    <>
      <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground group-data-[collapsible=icon]:size-8">
        <BarChart3 className="size-5" aria-hidden="true" />
      </span>
      <span className="font-sans text-base font-semibold tracking-tight group-data-[collapsible=icon]:hidden">
        Decision Room
      </span>
    </>
  );
}
