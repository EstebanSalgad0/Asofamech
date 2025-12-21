import React from "react";
import { Link } from "react-router-dom";

export function LandingPage() {
  return (
    <div className="landing-page">
      {/* Navigation */}
      <nav className="landing-nav">
        <div className="landing-nav-inner">
          <div className="landing-logo">
            <div className="logo-icon">A</div>
            <span>ASOFAMECH</span>
          </div>
          <div className="landing-nav-links">
            <a href="#inicio">Inicio</a>
            <a href="#quienes-somos">Quiénes Somos</a>
            <a href="#recursos">Recursos</a>
            <a href="#faq">FAQ</a>
            <a href="#contacto">Contacto</a>
          </div>
          <div className="landing-nav-actions">
            <Link to="/auth" className="btn-nav-login">Iniciar Sesión</Link>
            <Link to="/auth?register=true" className="btn-nav-register">Registrarse</Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="landing-hero" id="inicio">
        <div className="landing-hero-inner">
          <div className="landing-hero-content">
            <div className="hero-badge">
              <span>🚀 Educación Médica Innovadora</span>
            </div>
            <h1 className="landing-hero-title">
              Aprende <span className="gradient-text">Medicina</span><br />
              con Inteligencia<br />
              Artificial
            </h1>
            <p className="landing-hero-subtitle">
              Tu asistente educativo inteligente para explorar enfermedades, diagnósticos y tratamientos médicos. Información actualizada, casos de estudio y respuestas inmediatas.
            </p>
            <div className="landing-hero-actions">
              <Link to="/auth?register=true" className="btn-primary-lg">
                Comenzar Ahora →
              </Link>
              <a href="#quienes-somos" className="btn-secondary-lg">
                Conocer Más
              </a>
            </div>
            <div className="landing-hero-stats">
              <div className="hero-stat">
                <div className="hero-stat-value">1M+</div>
                <div className="hero-stat-label">Consultas resueltas</div>
              </div>
              <div className="hero-stat">
                <div className="hero-stat-value">24/7</div>
                <div className="hero-stat-label">Disponibilidad</div>
              </div>
              <div className="hero-stat">
                <div className="hero-stat-value">98%</div>
                <div className="hero-stat-label">Precisión</div>
              </div>
            </div>
          </div>
          <div className="landing-hero-preview">
            <div className="chat-preview-card">
              <div className="chat-preview-header">
                <div className="chat-preview-icon">💬</div>
                <div>
                  <div className="chat-preview-title">MediChat</div>
                  <div className="chat-preview-subtitle">Asistente Educativo Médico</div>
                </div>
              </div>
              <div className="chat-preview-badge">
                <span className="success-dot"></span>
                Tasa de éxito 95%
              </div>
              <div className="chat-preview-message">
                ¡Hola! Soy tu asistente educativo médico. Puedo ayudarte con preguntas sobre enfermedades, síntomas, diagnósticos y tratamientos. ¿En qué puedo ayudarte hoy?
              </div>
              <input 
                type="text" 
                className="chat-preview-input" 
                placeholder="Escribe tu pregunta médica..."
                readOnly
              />
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="landing-features" id="quienes-somos">
        <div className="landing-section-inner">
          <div className="landing-section-header">
            <h2 className="landing-section-title">
              ¿Por qué elegir <span className="gradient-text">ASOFAMECH</span>?
            </h2>
            <p className="landing-section-subtitle">
              Una plataforma diseñada para la educación médica moderna, combinando inteligencia artificial y contenido clínico estructurado.
            </p>
          </div>
          
          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon blue">💬</div>
              <h3 className="feature-title">IA Avanzado</h3>
              <p className="feature-description">
                Respuestas precisas basadas en las últimas investigaciones médicas y guías clínicas actualizadas.
              </p>
            </div>
            
            <div className="feature-card">
              <div className="feature-icon green">📚</div>
              <h3 className="feature-title">Casos de Estudio</h3>
              <p className="feature-description">
                Aprende mediante casos reales y simulaciones que refuerzan tu comprensión clínica.
              </p>
            </div>
            
            <div className="feature-card">
              <div className="feature-icon cyan">📋</div>
              <h3 className="feature-title">Test SCT</h3>
              <p className="feature-description">
                Evalúa tu razonamiento clínico con Script Concordance Tests personalizados.
              </p>
            </div>
            
            <div className="feature-card">
              <div className="feature-icon purple">🌍</div>
              <h3 className="feature-title">Acceso Universal</h3>
              <p className="feature-description">
                Disponible 24/7 para estudiantes, profesionales y cualquier persona interesada en medicina.
              </p>
            </div>
            
            <div className="feature-card">
              <div className="feature-icon orange">🔍</div>
              <h3 className="feature-title">Diagnóstico Asistido</h3>
              <p className="feature-description">
                Guías paso a paso para procesos diagnósticos con fines exclusivamente educativos.
              </p>
            </div>
            
            <div className="feature-card">
              <div className="feature-icon teal">✅</div>
              <h3 className="feature-title">Contenido Verificado</h3>
              <p className="feature-description">
                Información revisada por especialistas en múltiples áreas de la salud.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Project Section */}
      <section className="landing-project">
        <div className="landing-section-inner">
          <h2 className="landing-section-title">
            Sobre el <span className="gradient-text">Proyecto ASOFAMECH</span>
          </h2>
          <p className="landing-project-description">
            ASOFAMECH nace de la visión de integrar la inteligencia artificial en la formación médica, ofreciendo herramientas innovadoras que potencian el aprendizaje y el razonamiento clínico.
          </p>
          <p className="landing-project-description">
            Nuestra plataforma combina tecnología de punta con contenido médico verificado, creando un ecosistema educativo accesible para estudiantes, residentes y profesionales de la salud en toda Latinoamérica.
          </p>
          
          <div className="project-stats">
            <div className="project-stat-card">
              <div className="project-stat-value">+5K</div>
              <div className="project-stat-label">Usuarios activos</div>
            </div>
            <div className="project-stat-card">
              <div className="project-stat-value">+100</div>
              <div className="project-stat-label">Casos de estudio</div>
            </div>
          </div>

          <div className="project-mission">
            <h3 className="project-mission-title">Nuestra Misión</h3>
            <ul className="project-mission-list">
              <li>• Democratizar el acceso a educación médica de calidad</li>
              <li>• Integrar IA de forma ética y responsable en la formación</li>
              <li>• Desarrollar el pensamiento clínico mediante casos prácticos</li>
              <li>• Crear una comunidad de aprendizaje colaborativo</li>
            </ul>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="landing-faq" id="faq">
        <div className="landing-section-inner">
          <h2 className="landing-section-title">Preguntas Frecuentes</h2>
          <p className="landing-section-subtitle">
            Encuentra respuestas a las dudas más comunes sobre nuestra plataforma.
          </p>
          
          <div className="faq-list">
            <details className="faq-item">
              <summary className="faq-question">¿Qué es el Proyecto ASOFAMECH?</summary>
              <div className="faq-answer">
                ASOFAMECH es una plataforma educativa que integra inteligencia artificial para ofrecer herramientas innovadoras de aprendizaje médico, incluyendo un chatbot educativo, generación de casos clínicos y tests de razonamiento.
              </div>
            </details>
            
            <details className="faq-item">
              <summary className="faq-question">¿El asistente puede reemplazar a un médico?</summary>
              <div className="faq-answer">
                No. Este asistente es exclusivamente para fines educativos y formativos. No proporciona diagnósticos ni reemplaza la consulta con un profesional de la salud. Siempre consulte a su médico para diagnóstico y tratamiento.
              </div>
            </details>
            
            <details className="faq-item">
              <summary className="faq-question">¿Qué es el Test SCT?</summary>
              <div className="faq-answer">
                El Script Concordance Test evalúa cómo los estudiantes modifican sus hipótesis clínicas cuando reciben nueva información, simulando el razonamiento de expertos. Cada ítem presenta un escenario clínico, una hipótesis y nueva información que puede fortalecer o debilitar dicha hipótesis.
              </div>
            </details>
            
            <details className="faq-item">
              <summary className="faq-question">¿Quién puede usar la plataforma?</summary>
              <div className="faq-answer">
                La plataforma está diseñada para estudiantes de medicina, residentes, profesionales de la salud y cualquier persona interesada en aprender sobre temas médicos con fines educativos.
              </div>
            </details>
            
            <details className="faq-item">
              <summary className="faq-question">¿La información está actualizada?</summary>
              <div className="faq-answer">
                Sí. Nuestro contenido se basa en las últimas investigaciones médicas, guías clínicas y es revisado periódicamente por especialistas para garantizar su actualización y precisión.
              </div>
            </details>
            
            <details className="faq-item">
              <summary className="faq-question">¿Es gratuito?</summary>
              <div className="faq-answer">
                Sí. ASOFAMECH es una plataforma educativa de acceso gratuito, diseñada para democratizar la educación médica de calidad.
              </div>
            </details>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="landing-cta">
        <div className="landing-cta-inner">
          <h2 className="landing-cta-title">Comienza tu consulta <span className="gradient-text">ahora</span></h2>
          <p className="landing-cta-subtitle">
            Haz tus preguntas médicas y obtén respuestas educativas inmediatas sobre temas de salud. Recuerda que este asistente es solo para fines formativos y no reemplaza la atención de un profesional.
          </p>
          
          <div className="cta-modules">
            <div className="cta-module-card">
              <div className="cta-module-icon">💬</div>
              <h3 className="cta-module-title">Chatbot Médico</h3>
              <p className="cta-module-subtitle">Consultas educativas 24/7</p>
              <p className="cta-module-description">
                Realiza preguntas sobre síntomas, enfermedades, tratamientos y más. Obtén explicaciones claras y referencias educativas.
              </p>
            </div>
            
            <div className="cta-module-card">
              <div className="cta-module-icon">📋</div>
              <h3 className="cta-module-title">Test SCT</h3>
              <p className="cta-module-subtitle">Razonamiento clínico</p>
              <p className="cta-module-description">
                Genera casos clínicos personalizados y evalúa tu capacidad de ajustar hipótesis diagnósticas ante nueva información.
              </p>
            </div>
          </div>
          
          <div className="cta-buttons">
            <Link to="/auth?register=true" className="btn-cta-primary">
              Crear Cuenta Gratis →
            </Link>
            <Link to="/auth" className="btn-cta-secondary">
              Iniciar Sesión
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer" id="contacto">
        <div className="landing-footer-inner">
          <div className="footer-grid">
            <div className="footer-brand">
              <div className="footer-logo">
                <div className="logo-icon">A</div>
                <span>ASOFAMECH</span>
              </div>
              <p className="footer-tagline">
                Plataforma de educación médica impulsada por inteligencia artificial. Formación innovadora para profesionales de la salud.
              </p>
            </div>
            
            <div className="footer-links">
              <h4 className="footer-links-title">Enlaces</h4>
              <a href="#inicio">Inicio</a>
              <a href="#quienes-somos">Quiénes Somos</a>
              <a href="#recursos">Recursos</a>
              <a href="#faq">Preguntas Frecuentes</a>
            </div>
            
            <div className="footer-links">
              <h4 className="footer-links-title">Módulos</h4>
              <Link to="/dashboard">Chatbot Médico IA</Link>
              <Link to="/dashboard">Test SCT</Link>
              <Link to="/dashboard">Análisis de Imágenes</Link>
            </div>
            
            <div className="footer-contact">
              <h4 className="footer-links-title">Contacto</h4>
              <p>✉️ contacto@asofamech.org</p>
              <p>📍 Santiago, Chile</p>
            </div>
          </div>
          
          <div className="footer-bottom">
            <p>© 2025 Proyecto ASOFAMECH. Todos los derechos reservados.</p>
            <p className="footer-disclaimer">
              <strong>Aviso importante:</strong> Esta plataforma es exclusivamente para fines educativos. La información proporcionada no reemplaza la consulta con un profesional de la salud. Siempre consulte a su médico para diagnóstico y tratamiento.
            </p>
            <p className="footer-love">Hecho con ❤️ para la educación médica</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
