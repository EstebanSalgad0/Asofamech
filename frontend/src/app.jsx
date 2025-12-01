import React from "react";
import HeroSection from "./components/HeroSection";
import FeaturesSection from "./components/FeaturesSection";
import ChatSection from "./components/ChatSection";
import Footer from "./components/Footer";

export default function App() {
  return (
    <div className="app-root">
      <HeroSection />
      <FeaturesSection />
      <ChatSection />
      <Footer />
    </div>
  );
}
