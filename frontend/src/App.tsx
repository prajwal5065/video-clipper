import { Link, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { buttonClass } from "./components/ui/Button";
import CreatePage from "./pages/CreatePage";
import JobPage from "./pages/JobPage";
import LibraryPage from "./pages/LibraryPage";
import SettingsPage from "./pages/SettingsPage";

function NotFound() {
  return (
    <div className="grid place-items-center gap-4 py-24 text-center">
      <p className="text-5xl font-semibold">404</p>
      <p className="text-muted">That page does not exist.</p>
      <Link to="/" className={buttonClass("primary")}>Back to start</Link>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<CreatePage />} />
        <Route path="jobs/:id" element={<JobPage />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
