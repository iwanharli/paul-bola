import { Outlet, Link, NavLink, useLocation } from "react-router-dom";
import { Suspense } from "react";
import { AppLogo, FullPageLoader } from "./components.jsx";
import ErrorBoundary from "./ErrorBoundary.jsx";

export default function App() {
  const location = useLocation();
  const backendRoutes = [
    "/data-quality",
    "/sources",
    "/source-gaps",
    "/model-lab",
    "/narratives",
    "/data-dictionary",
    "/changelog",
    "/settings",
  ];
  const backendActive = backendRoutes.some((route) => location.pathname.startsWith(route));

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark"><AppLogo /></span>
          <span className="brand-text">
            Paul <span className="brand-sub">WC 2026 Forecast</span>
          </span>
        </Link>
        <nav className="topnav" aria-label="Main navigation">
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/forecast">Forecast</NavLink>
          <NavLink to="/history">History</NavLink>
          <NavLink to="/bracket">Bracket</NavLink>
          <NavLink to="/compare">Compare</NavLink>
          <NavLink to="/teams">Teams</NavLink>
          <NavLink to="/players">Players</NavLink>
          <details className={`nav-dropdown ${backendActive ? "active" : ""}`}>
            <summary>Ops</summary>
            <div className="nav-dropdown-menu">
              <NavLink to="/data-quality">Quality</NavLink>
              <NavLink to="/source-gaps">Data Gaps</NavLink>
              <NavLink to="/sources">Sources</NavLink>
              <NavLink to="/model-lab">Model Lab</NavLink>
              <NavLink to="/narratives">Narratives</NavLink>
              <NavLink to="/data-dictionary">Dictionary</NavLink>
              <NavLink to="/changelog">Changelog</NavLink>
              <NavLink to="/settings">Settings</NavLink>
            </div>
          </details>
        </nav>
        <span className="topbar-tag">xG + market blend</span>
      </header>
      <main className="content">
        <div className="page-transition" key={location.pathname}>
          {/* key resets the boundary + suspense on navigation so a broken or
              loading page never sticks after you move away */}
          <ErrorBoundary key={location.pathname}>
            <Suspense fallback={<FullPageLoader text="Memuat halaman" />}>
              <Outlet />
            </Suspense>
          </ErrorBoundary>
        </div>
      </main>
      <footer className="footer">
        Forecast berbasis xG/goals Dixon-Coles, time decay, Elo, dan market blend.
      </footer>
    </div>
  );
}
