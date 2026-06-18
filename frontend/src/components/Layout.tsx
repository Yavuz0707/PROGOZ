import { Camera, Gauge, Globe, LayoutDashboard, LogOut, RectangleEllipsis, Settings, Upload, Users, Video } from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/live", label: "Canli Kamera", icon: Video },
  { to: "/web-stream", label: "Web Yayini", icon: Globe },
  { to: "/persons", label: "Kisi Takibi", icon: Users },
  { to: "/upload", label: "Video Analiz", icon: Upload },
  { to: "/events", label: "Olaylar", icon: Gauge },
  { to: "/plates", label: "Plakalar", icon: RectangleEllipsis },
  { to: "/cameras", label: "Kameralar", icon: Camera },
  { to: "/settings", label: "Ayarlar", icon: Settings }
];

export function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const logout = () => {
    localStorage.removeItem("progoz_token");
    navigate("/login");
  };

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[260px_1fr]">
      {/* ===== Sidebar (glassmorphic stealth) ===== */}
      <aside className="border-b border-white/10 bg-surface/5 backdrop-blur-2xl p-4 lg:min-h-screen lg:border-b-0 lg:border-r lg:border-r-white/10 lg:py-6">
        {/* Brand */}
        <div className="mb-6 flex items-center gap-3 px-1">
          <div className="relative grid h-11 w-11 place-items-center rounded-lg border border-white/15 bg-white text-black">
            <Gauge size={22} />
            <span className="absolute -right-1 -top-1 h-3 w-3 rounded-full bg-status-green shadow-glow-green" />
          </div>
          <div>
            <h1 className="font-headline-sm text-lg font-bold uppercase tracking-hud text-white">PROGÖZ</h1>
            <p className="flex items-center gap-1.5 font-label-caps text-[10px] text-[#888]">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-status-green animate-ambient-pulse" />
              Proaktif Gözetim
            </p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="grid grid-cols-2 gap-1 lg:grid-cols-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `group relative flex items-center gap-3 py-2.5 pr-3 text-sm transition-all duration-200 active:scale-[0.98] ${
                  isActive
                    ? "bg-white/10 text-white font-medium shadow-[inset_2px_0_0_#fff] pl-[10px]"
                    : "text-[#888] hover:bg-white/5 hover:text-white rounded-l-lg pl-3"
                }`
              }
            >
              <item.icon size={18} className="shrink-0" />
              <span className="font-label-caps text-[11px] tracking-caps">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Logout */}
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
          onClick={logout}
          className="focus-ring mt-5 flex w-full items-center gap-3 rounded-lg border border-white/10 px-3 py-2.5 text-sm text-[#888] hover:bg-white/5 hover:text-white"
        >
          <LogOut size={18} />
          <span className="font-label-caps text-[11px] tracking-caps">Çıkış</span>
        </motion.button>
      </aside>

      {/* ===== Main content (animated route transitions) ===== */}
      <main className="relative p-4 md:p-6">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
