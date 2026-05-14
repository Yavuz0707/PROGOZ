import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import CamerasPage from "./pages/CamerasPage";
import DashboardPage from "./pages/DashboardPage";
import EventDetailPage from "./pages/EventDetailPage";
import EventsPage from "./pages/EventsPage";
import LiveCameraPage from "./pages/LiveCameraPage";
import LoginPage from "./pages/LoginPage";
import SettingsPage from "./pages/SettingsPage";
import VideoUploadPage from "./pages/VideoUploadPage";

function Protected() {
  return localStorage.getItem("progoz_token") ? <Layout /> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Protected />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/live" element={<LiveCameraPage />} />
        <Route path="/upload" element={<VideoUploadPage />} />
        <Route path="/events" element={<EventsPage />} />
        <Route path="/events/:id" element={<EventDetailPage />} />
        <Route path="/cameras" element={<CamerasPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}

