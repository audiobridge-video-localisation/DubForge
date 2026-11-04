import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

// Header + page frame shared by every app screen, so navigation is the same everywhere:
// the wordmark goes to the marketing page, "Projects" always goes to /app.
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app">
      <header className="app-header">
        <Link className="app-wordmark" to="/" aria-label="DubForge home">
          DubForge
        </Link>
        <nav className="app-nav" aria-label="Workspace">
          <NavLink to="/app" end className="app-nav-link">
            Projects
          </NavLink>
        </nav>
        <Link className="app-home-link" to="/">
          Back to site
        </Link>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}

export function PageHeading({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}
