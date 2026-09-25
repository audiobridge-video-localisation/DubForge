import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

function App() {
  return <main><h1>DubForge</h1><p>Video localisation workspace</p></main>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode><App /></StrictMode>,
);
