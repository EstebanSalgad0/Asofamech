import React from "react";

export default function HeroSection() {
  return (
    <section className="hero">
      <div className="hero-inner">
        <div className="hero-text">
          <span className="hero-pill">Educación Médica Innovadora</span>
          <h1 className="hero-title">
            Aprende <span>Medicina</span>
          </h1>
          <p className="hero-subtitle">
            Tu asistente educativo inteligente para explorar enfermedades,
            diagnósticos y tratamientos médicos. Información actualizada, casos
            de estudio y respuestas inmediatas.
          </p>

          <div className="hero-actions">
            <a href="#chat" className="btn btn-primary">
              Comenzar Chat
            </a>
            <a href="#features" className="btn btn-outline">
              Conocer Más
            </a>
          </div>

          <div className="hero-stats">
            <div className="stat">
              <span className="stat-number">1M+</span>
              <span className="stat-label">Consultas resueltas</span>
            </div>
            <div className="stat">
              <span className="stat-number">24/7</span>
              <span className="stat-label">Disponibilidad</span>
            </div>
            <div className="stat">
              <span className="stat-number">98%</span>
              <span className="stat-label">Precisión</span>
            </div>
          </div>
        </div>

        <div className="hero-image-card">
          {/* Imagen ilustrativa: coloca tu propia imagen en /public o /src/assets */}
          <div className="hero-image-placeholder">
            <div className="hero-status-badge">
              <span className="status-icon">✓</span>
              <div>
                <div className="status-label">Tasa de éxito</div>
                <div className="status-value">95%</div>
              </div>
            </div>
            {/* Si tienes una imagen, por ejemplo /hero-medicina.png:
                <img src="/hero-medicina.png" alt="Médicos revisando radiografía" />
            */}
            <div className="hero-docs-illustration">
              <div className="hero-xray" />
              <div className="hero-doctor hero-doctor-left" />
              <div className="hero-doctor hero-doctor-right" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
