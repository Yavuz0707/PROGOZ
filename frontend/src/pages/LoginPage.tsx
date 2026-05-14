import { FormEvent, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api, unwrap } from "../api/client";

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const data = await unwrap<{ access_token: string }>(api.post("/auth/login", { username, password }));
      localStorage.setItem("progoz_token", data.access_token);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Giris basarisiz.");
    }
  }

  return (
    <main className="grid min-h-screen place-items-center p-4">
      <form onSubmit={submit} className="panel w-full max-w-md p-6">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-lg bg-cyan-400 text-slate-950">
            <ShieldCheck size={26} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">PROGOZ</h1>
            <p className="text-sm text-slate-400">Guvenli oturum</p>
          </div>
        </div>
        <label className="mb-4 block">
          <span className="text-sm text-slate-300">Kullanici veya e-posta</span>
          <input className="focus-ring mt-2 w-full rounded-lg border border-line bg-slate-950 px-3 py-2" value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label className="mb-4 block">
          <span className="text-sm text-slate-300">Sifre</span>
          <input className="focus-ring mt-2 w-full rounded-lg border border-line bg-slate-950 px-3 py-2" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="mb-4 rounded-lg border border-red-400/40 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
        <button className="focus-ring w-full rounded-lg bg-cyan-400 px-4 py-2 font-semibold text-slate-950 hover:bg-cyan-300">Giris Yap</button>
      </form>
    </main>
  );
}

