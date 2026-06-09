import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, unwrap } from "../api/client";

type Phase = "splash" | "transitioning" | "form";

const SCROLL_TR = "PROGÖZ • GÜVENLİK • PROGÖZ • GÜVENLİK • PROGÖZ • GÜVENLİK • PROGÖZ • GÜVENLİK • PROGÖZ • GÜVENLİK • ";
const SCROLL_EN = "SECURITY • SYSTEM • SECURITY • SYSTEM • SECURITY • SYSTEM • SECURITY • SYSTEM • SECURITY • SYSTEM • ";

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [phase, setPhase] = useState<Phase>("splash");

  function handleStart() {
    setPhase("transitioning");
    setTimeout(() => setPhase("form"), 650);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      const data = await unwrap<{ access_token: string }>(
        api.post("/auth/login", { username, password })
      );
      localStorage.setItem("progoz_token", data.access_token);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Giriş başarısız.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="login-page">
      {/* Splash Screen */}
      {phase !== "form" && (
        <div
          className="login-splash"
          style={{
            transform: phase === "transitioning" ? "translateY(-100%)" : "translateY(0)",
            transition: phase === "transitioning"
              ? "transform 0.65s cubic-bezier(0.76, 0, 0.24, 1)"
              : "none",
          }}
        >
          {/* Scrolling background text */}
          <div className="login-scroll-container">
            <div className="login-scroll-row">
              <div className="login-scroll-track-left">
                <span className="login-scroll-text">{SCROLL_TR}</span>
                <span className="login-scroll-text">{SCROLL_TR}</span>
              </div>
            </div>
            <div className="login-scroll-row">
              <div className="login-scroll-track-right">
                <span className="login-scroll-text">{SCROLL_EN}</span>
                <span className="login-scroll-text">{SCROLL_EN}</span>
              </div>
            </div>
          </div>

          {/* Foreground content */}
          <div className="login-splash-content">
            <p className="login-splash-label">PROGÖZ</p>
            <button className="login-start-button" onClick={handleStart}>
              Başlayın →
            </button>
            <p className="login-splash-sub">Güvenlik sisteminize erişin</p>
          </div>
        </div>
      )}

      {/* Login Form */}
      <div
        className="login-form-wrapper"
        style={{
          transform: phase === "splash" ? "translateY(60px)" : "translateY(0)",
          opacity: phase === "splash" ? 0 : 1,
          transition: phase !== "splash"
            ? "transform 0.65s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.5s ease"
            : "none",
          pointerEvents: phase === "splash" ? "none" : "auto",
        }}
      >
        <form onSubmit={submit} className="login-form">
          <div className="login-form-header">
            <h1 className="login-form-title">PROGÖZ</h1>
            <p className="login-form-subtitle">Güvenlik Sistemine Giriş</p>
          </div>

          <label className="login-label">
            <span className="login-label-text">Kullanıcı adı veya e-posta</span>
            <input
              className="login-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
          </label>

          <label className="login-label">
            <span className="login-label-text">Şifre</span>
            <input
              className="login-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>

          {error && <div className="login-error">{error}</div>}

          <button
            type="submit"
            disabled={isLoading}
            className="login-submit-button"
          >
            {isLoading ? <span className="login-spinner" /> : "Giriş Yap"}
          </button>

          <p className="login-version">v1.0.0</p>
        </form>
      </div>
    </div>
  );
}
