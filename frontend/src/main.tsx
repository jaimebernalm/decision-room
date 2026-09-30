import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { AppRecovery } from "./components/app-recovery";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppRecovery><App /></AppRecovery>
  </StrictMode>,
);
