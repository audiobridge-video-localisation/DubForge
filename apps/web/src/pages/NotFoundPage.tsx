import { Link } from "react-router-dom";

import { AppShell } from "../components/app/AppShell";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

export function NotFoundPage() {
  useDocumentTitle("Page not found · DubForge");
  return (
    <AppShell>
      <section className="card empty">
        <h1>That page doesn&apos;t exist</h1>
        <p>The link may be old or mistyped.</p>
        <div className="empty-actions">
          <Link className="btn btn-primary" to="/app">
            Go to projects
          </Link>
          <Link className="btn" to="/">
            Back to the site
          </Link>
        </div>
      </section>
    </AppShell>
  );
}
