import type { ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";
import { useWorkspace } from "@/lib/workspace";

// One active composer at a time. Shared layout carries its position across
// route changes without keeping outgoing forms interactive or delaying typing.
export function ComposerSurface({
  children,
  shared = true,
}: {
  children: ReactNode;
  shared?: boolean;
}) {
  const reduced = useReducedMotion();
  const { workspace } = useWorkspace();
  return (
    <motion.div
      className="w-full"
      layout="position"
      layoutId={
        shared ? `business-composer-${workspace.business?.id}` : undefined
      }
      initial={false}
      transition={{
        layout: { duration: reduced ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] },
      }}
    >
      {children}
    </motion.div>
  );
}
