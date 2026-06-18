import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, unwrap } from "../api/client";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (password.length < 4) {
      setError("Şifre en az 4 karakter olmalı.");
      return;
    }
    setIsLoading(true);
    try {
      const data = await unwrap<{ access_token: string }>(
        api.post("/auth/register", { username, email, password })
      );
      localStorage.setItem("progoz_token", data.access_token);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kayıt başarısız.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-form-wrapper" style={{ transform: "translateY(0)", opacity: 1 }}>
        <form onSubmit={submit} className="login-form">
          <div className="login-form-header">
            <h1 className="login-form-title">PROGÖZ</h1>
            <p className="login-form-subtitle">Yeni Hesap Oluştur</p>
          </div>

          <label className="login-label">
            <span className="login-label-text">Kullanıcı adı</span>
            <input
              className="login-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </label>

          <label className="login-label">
            <span className="login-label-text">E-posta</span>
            <input
              className="login-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </label>

          <label className="login-label">
            <span className="login-label-text">Şifre</span>
            <input
              className="login-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </label>

          {error && <div className="login-error">{error}</div>}

          <button type="submit" disabled={isLoading} className="login-submit-button">
            {isLoading ? <span className="login-spinner" /> : "Kayıt Ol"}
          </button>

          <p className="login-version" style={{ marginTop: 14 }}>
            Zaten hesabın var mı?{" "}
            <Link to="/login" style={{ color: "#818cf8", textDecoration: "none" }}>
              Giriş yap
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
