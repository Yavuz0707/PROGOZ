import { Camera, Gauge, Globe, LayoutDashboard, LogOut, RectangleEllipsis, Settings, Upload, Video } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/live", label: "Canli Kamera", icon: Video },
  { to: "/web-stream", label: "Web Yayini", icon: Globe },
  { to: "/upload", label: "Video Analiz", icon: Upload },
  { to: "/events", label: "Olaylar", icon: Gauge },
  { to: "/plates", label: "Plakalar", icon: RectangleEllipsis },
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
      <aside className="border-b border-[#1f1f1f] bg-[#080808] p-4 lg:min-h-screen lg:border-b-0 lg:border-r lg:border-r-[#1f1f1f]">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-lg bg-white text-black">
            <Gauge size={24} />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">PROGÖZ</h1>
            <p className="text-xs text-[#555]">Proaktif Gözetim</p>
          </div>
        </div>
        <nav className="grid grid-cols-2 gap-1 lg:grid-cols-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 py-2 pr-3 text-sm transition rounded-r-lg ${
                  isActive
                    ? "bg-white/8 text-white font-medium shadow-[inset_2px_0_0_#fff] pl-[10px]"
                    : "text-[#888] hover:bg-white/5 hover:text-white rounded-l-lg pl-3"
                }`
              }
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button
          onClick={logout}
          className="focus-ring mt-5 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-[#888] hover:bg-white/5 hover:text-white"
        >
          <LogOut size={18} /> Çıkış
        </button>
      </aside>
      <main className="p-4 md:p-6">
        <Outlet />
      </main>
    </div>
  );
}
