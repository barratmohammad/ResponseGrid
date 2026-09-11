import React from "react";
import { createRoot } from "react-dom/client";
import Platform from "./Platform";
import "./style.css";
import "./control-tower.css";
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Platform />
  </React.StrictMode>,
);
