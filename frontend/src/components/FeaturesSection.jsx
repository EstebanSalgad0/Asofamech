import React from "react";

const features = [
  {
    title: "IA Avanzada",
    desc: "Respuestas precisas basadas en las últimas investigaciones médicas y guías clínicas actualizadas.",
    icon: "🧠",
  },
  {
    title: "Casos de Estudio",
    desc: "Aprende mediante casos reales y simulaciones que refuerzan tu comprensión clínica.",
    icon: "📚",
  },
  {
    title: "Información Científica",
    desc: "Contenido verificado por especialistas en múltiples áreas de la salud.",
    icon: "📊",
  },
  {
    title: "Acceso Universal",
    desc: "Disponible 24/7 para estudiantes, profesionales y cualquier persona interesada en medicina.",
    icon: "🌍",
  },
  {
    title: "Diagnóstico Asistido",
    desc: "Guías paso a paso para procesos diagnósticos con fines exclusivamente educativos.",
    icon: "📋",
  },
  {
    title: "Prevención",
    desc: "Información sobre medidas preventivas, control de enfermedades y promoción de la salud.",
    icon: "🛡️",
  },
];

export default function FeaturesSection() {
  return (
    <section id="features" className="features">
      <div className="features-inner">
        <div className="features-header">
          <h2>
            ¿Por qué elegir <span>MediChat</span>?
          </h2>
          <p>
            Una plataforma diseñada para la educación médica moderna, combinando
            inteligencia artificial y contenido clínico estructurado.
          </p>
        </div>

        <div className="features-grid">
          {features.map((f) => (
            <div key={f.title} className="feature-card">
              <div className="feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
