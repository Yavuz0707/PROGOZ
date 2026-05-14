import { Camera, Gauge, LayoutDashboard, LogOut, Settings, Upload, Video } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/live", label: "Canli Kamera", icon: Video },
  { to: "/upload", label: "Video Analiz", icon: Upload },
  { to: "/events", label: "Olaylar", icon: Gauge },
  { to: "/cameras", label: "Kameralar", icon: Camera },
  { to: "/settings", label: "Ayarlar", icon: Settings }
];

export function Layout() {
  const navigate = useNavigate();
  const logout = () => {
    localStorage.removeItem("progoz_token");
    navigate("/login");
  };

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      <aside className="border-b border-line bg-slate-950/70 p-4 backdrop-blur lg:min-h-screen lg:border-b-0 lg:border-r">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-lg bg-cyan-400 text-slate-950">
            <Gauge size={24} />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">PROGOZ</h1>
            <p className="text-xs text-slate-400">Proaktif Gozetim</p>
          </div>
        </div>
        <nav className="grid grid-cols-2 gap-2 lg:grid-cols-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${isActive ? "bg-cyan-400/16 text-cyan-100" : "text-slate-300 hover:bg-slate-800"}`
              }
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button onClick={logout} className="focus-ring mt-5 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-300 hover:bg-slate-800">
          <LogOut size={18} /> Cikis
        </button>
      </aside>
      <main className="p-4 md:p-6">
        <Outlet />
      </main>
    </div>
  );
}

