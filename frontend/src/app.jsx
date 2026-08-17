import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { LandingPage } from "./pages/LandingPage";
import { AuthPage } from "./pages/AuthPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ChatbotPage } from "./pages/ChatbotPage";
import { SCTPage } from "./pages/SCTPage";
import { ImagesPage } from "./pages/ImagesPage";
import { ConfigPage } from "./pages/ConfigPage";
import { CasesPage } from "./pages/CasesPage";
import { SurveysPage } from "./pages/SurveysPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { ThemeToggle } from "./components/ThemeToggle";

function PublicThemeToggle() {
  const location = useLocation();
  if (location.pathname.startsWith("/dashboard")) return null;
  return <ThemeToggle variant="floating" />;
}

export default function App() {
  return (
    <BrowserRouter>
      <PublicThemeToggle />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/auth/reset-password" element={<ResetPasswordPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/dashboard/chat" element={<ChatbotPage />} />
        <Route path="/dashboard/sct" element={<SCTPage />} />
        <Route path="/dashboard/images" element={<ImagesPage />} />
        <Route path="/dashboard/cases" element={<CasesPage />} />
        <Route path="/dashboard/surveys" element={<SurveysPage />} />
        <Route path="/dashboard/reports" element={<ReportsPage />} />
        <Route path="/dashboard/config" element={<ConfigPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
