import React from "react";
import HeroSection from "./components/HeroSection";
import FeaturesSection from "./components/FeaturesSection";
import ChatSection from "./components/ChatSection";
import SCTSection from "./components/SCTSection";
import Footer from "./components/Footer";

export default function App() {
  return (
    <div className="app-root">
      <HeroSection />
      <FeaturesSection />
      <ChatSection />
      <SCTSection />
      <Footer />
    </div>
  );
}
