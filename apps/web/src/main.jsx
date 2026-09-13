import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { LiveStatusProvider } from "./context/LiveStatusContext";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <LiveStatusProvider>
        <App />
      </LiveStatusProvider>
    </BrowserRouter>
  </StrictMode>
);
