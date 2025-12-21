import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { LandingPage } from "./pages/LandingPage";
import { AuthPage } from "./pages/AuthPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ChatbotPage } from "./pages/ChatbotPage";
import { SCTPage } from "./pages/SCTPage";
import { ImagesPage } from "./pages/ImagesPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/dashboard/chat" element={<ChatbotPage />} />
        <Route path="/dashboard/sct" element={<SCTPage />} />
        <Route path="/dashboard/images" element={<ImagesPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
