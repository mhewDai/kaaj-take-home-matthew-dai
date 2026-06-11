import { NavLink, Outlet } from "react-router-dom";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-md text-sm font-medium transition ${
    isActive ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
  }`;

export default function Layout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <NavLink to="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-600 text-white">
              ₭
            </span>
            <span className="text-lg font-semibold text-slate-800">
              Lender Matching
            </span>
          </NavLink>
          <nav className="flex items-center gap-1">
            <NavLink to="/applications" className={linkClass}>
              Applications
            </NavLink>
            <NavLink to="/lenders" className={linkClass}>
              Lenders
            </NavLink>
            <NavLink to="/applications/new" className="btn-primary ml-2">
              + New application
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
