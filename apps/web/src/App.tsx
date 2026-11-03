import { BrowserRouter, Route, Routes } from "react-router-dom";

import { ProjectDetailPage } from "./pages/ProjectDetailPage";
import { ProjectListPage } from "./pages/ProjectListPage";
import ReferenceLanding from "./ReferenceLanding.jsx";
import "./styles/global.css";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ReferenceLanding />} />
        <Route path="/app" element={<ProjectListPage />} />
        <Route path="/projects/:id" element={<ProjectDetailPage />} />
      </Routes>
    </BrowserRouter>
  );
}
