import type { ReactNode } from "react";
import { ScrollArea } from "radix-ui";
import { ScrollBar } from "@/components/ui/scroll-area";

export function MainContent({
  children,
  scrollable,
}: {
  children: ReactNode;
  scrollable: boolean;
}) {
  if (!scrollable)
    return (
      <div
        id="main-content"
        tabIndex={-1}
        className="flex min-h-0 flex-1 flex-col outline-none"
      >
        {children}
      </div>
    );

  return (
    <ScrollArea.Root
      type="scroll"
      scrollHideDelay={600}
      className="relative min-h-0 flex-1 overflow-hidden"
    >
      <ScrollArea.Viewport
        id="main-content"
        tabIndex={-1}
        className="size-full outline-none [&>div]:block! [&>div]:w-full"
      >
        {children}
        <div className="workspace-composer-clearance" aria-hidden="true" />
      </ScrollArea.Viewport>
      <ScrollBar className="border-0 bg-transparent data-vertical:w-2" />
    </ScrollArea.Root>
  );
}
