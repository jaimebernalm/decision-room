import { createContext, useContext } from "react";
import type { Workspace, ChatListing, Chat } from "./types";
export type WorkspaceContext = {
  workspace: Workspace;
  listing: ChatListing;
  route: string;
  refresh: () => void;
  removeChat: (chat: Chat) => void;
};
export const WorkspaceState = createContext<WorkspaceContext | null>(null);
export function useWorkspace() {
  const context = useContext(WorkspaceState);
  if (!context) throw new Error("Workspace missing");
  return context;
}
