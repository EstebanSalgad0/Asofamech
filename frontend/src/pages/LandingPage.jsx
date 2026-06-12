import React from "react";
import { Link } from "react-router-dom";
import { FontSizeControl } from "../components/FontSizeControl";

const MARQUEE = [
  ["Razonamiento", "clínico"],
  ["Práctica", "deliberada"],
  ["Asistente", "educativo"],
  ["Test de", "concordancia"],
  ["Histopatología", "asistida"],
];

export function LandingPage() {
  return (
    <div>
      {/* ── Nav ── */}
      <nav className="top-nav">
        <div className="nav-inner">
          <div className="logo">
            <div className="logo-mark">A</div>
            <span>ASOFAMECH</span>
          </div>
          <div className="nav-links">
            <a href="#modulos">Módulos</a>
            <a href="#proceso">Cómo funciona</a>
            <a href="#aval">Fundamento SCT</a>
            <a href="#contacto">Contacto</a>
          </div>
          <div className="nav-actions">
            <FontSizeControl />
            <Link to="/auth" className="btn btn-ghost">Ingresar</Link>
            <Link to="/auth?register=true" className="btn btn-primary">Crear cuenta →</Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="hero-section">
        <div className="container hero-grid">
          <div>
            <span className="pill">
              <span className="pill-dot"></span>
              Plataforma activa · Pregrado de Medicina
            </span>
            <h1 className="display-heading">
              Razonamiento clínico,<br />
              entrenado con<br />
              <span className="display-it">precisión.</span>
            </h1>
            <p className="hero-sub">
              Tres herramientas integradas para que estudiantes de medicina afinen su criterio diagnóstico antes de pisar una sala. Asistente IA conversacional, Tests de Concordancia de Scripts y análisis histopatológico con visión computacional.
            </p>
            <div className="hero-actions">
              <Link to="/auth?register=true" className="btn btn-primary btn-lg">Comenzar ahora →</Link>
              <a href="#proceso" className="arrow-link">Ver cómo funciona ↓</a>
            </div>
            <div className="hero-stats">
              <div className="hero-stat-item">
                <span className="stat-num">3</span>
                <span className="stat-lbl">Módulos<br />integrados</span>
              </div>
              <div className="hero-stat-item">
                <span className="stat-num">DZI</span>
                <span className="stat-lbl">Visor<br />histológico</span>
              </div>
              <div className="hero-stat-item">
                <span className="stat-num">IA</span>
                <span className="stat-lbl">Casos SCT<br />generables</span>
              </div>
            </div>
          </div>

          <div className="hero-visual">
            {/* Chat card */}
            <div className="float-card fc-chat">
              <div className="fc-head">
                <div className="fc-avatar">M</div>
                <div>
                  <div className="fc-name">MediChat</div>
                  <div className="fc-role">Asistente educativo</div>
                </div>
                <div className="fc-online">● Online</div>
              </div>
              <div className="chat-msg chat-msg-user">
                ¿Cómo se diferencia una IC con FE preservada de una con FE reducida?
              </div>
              <div className="chat-msg chat-msg-bot">
                <strong>Diferencia clave:</strong> la <strong>FEp</strong> mantiene FEVI ≥ 50% con disfunción diastólica predominante; la <strong>FEr</strong> presenta FEVI &lt; 40% por disfunción sistólica…
              </div>
              <div className="chat-msg chat-msg-bot">
                <div className="typing-dots"><span></span><span></span><span></span></div>
              </div>
            </div>

            {/* SCT card */}
            <div className="float-card fc-sct">
              <div className="fc-tag">Test SCT · Ítem 04 / 10</div>
              <h4 className="fc-sct-q">Si además aparece troponina T elevada, su hipótesis de SCASEST…</h4>
              <div className="sct-scale">
                <div className="scale-opt">−2</div>
                <div className="scale-opt">−1</div>
                <div className="scale-opt">0</div>
                <div className="scale-opt scale-sel">+1</div>
                <div className="scale-opt">+2</div>
              </div>
              <div className="sct-bar-row">
                <span className="sct-pct">72%</span>
                <div className="sct-bar"><div className="sct-fill"></div></div>
                <span className="sct-panel">referencia</span>
              </div>
            </div>

            {/* Histo card */}
            <div className="float-card fc-histo">
              <div className="histo-mock"></div>
              <div className="histo-tags">
                <span className="htag htag-hi">Metastásico</span>
                <span className="htag">Estroma</span>
                <span className="htag">ROI</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Marquee ── */}
      <div className="marquee-strip">
        <div className="marquee-inner">
          {[...MARQUEE, ...MARQUEE].map(([prefix, it], i) => (
            <React.Fragment key={i}>
              <span className="marquee-item">{prefix} <em>{it}</em></span>
              <span className="marquee-star">✦</span>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* ── Módulos ── */}
      <section className="content-block" id="modulos">
        <div className="container">
          <div className="section-head">
            <span className="section-num">/ 01 — MÓDULOS</span>
            <h2 className="block-title">
              Tres herramientas, un mismo <em className="block-it">objetivo.</em>
            </h2>
            <span className="section-meta">Diseñadas para entrenar criterio, no para reemplazar la clínica.</span>
          </div>

          <div className="bento-grid">
            {/* Chatbot — tall dark card */}
            <article className="bento-card bc-dark">
              <div>
                <div className="bento-num">/ MÓDULO 01</div>
                <h3 className="bento-title" style={{ marginTop: "12px" }}>
                  Asistente IA<br />conversacional.
                </h3>
                <p className="bento-desc">
                  Resuelve dudas sobre fisiopatología, farmacología y manejo clínico con respuestas justificadas y organizadas por especialidad.
                </p>
                <div className="bento-tags">
                  <span>Historial por tema</span>
                  <span>Citas verificables</span>
                  <span>24/7</span>
                </div>
              </div>
              <div className="bento-chat-preview">
                <div className="bcp-msg bcp-bot">¿Qué patrón en una placa carotídea sugiere mayor riesgo embólico?</div>
                <div className="bcp-msg bcp-user">Placas hipoecoicas con núcleo lipídico y cápsula fibrosa fina presentan mayor inestabilidad…</div>
                <div className="bcp-input">
                  <span>Pregunta lo que necesites…</span>
                  <span className="bcp-send">↑</span>
                </div>
              </div>
              <span className="bento-arrow">→</span>
            </article>

            {/* SCT */}
            <article className="bento-card bc-coral">
              <div>
                <div className="bento-num">/ MÓDULO 02</div>
                <h3 className="bento-title" style={{ marginTop: "12px" }}>
                  Test de<br />Concordancia.
                </h3>
                <p className="bento-desc">
                  Contrasta tu razonamiento con una respuesta de referencia. Generación con IA, escala Likert y explicación post-ítem.
                </p>
                <div className="mini-scale">
                  <div className="ms-opt">−2</div>
                  <div className="ms-opt">−1</div>
                  <div className="ms-opt">0</div>
                  <div className="ms-opt ms-sel">+1</div>
                  <div className="ms-opt">+2</div>
                </div>
              </div>
              <span className="bento-arrow">→</span>
            </article>

            {/* Histo */}
            <article className="bento-card bc-mint">
              <div>
                <div className="bento-num">/ MÓDULO 03</div>
                <h3 className="bento-title" style={{ marginTop: "12px" }}>
                  Histopatología<br />asistida.
                </h3>
                <p className="bento-desc">
                  Visor DZI con selección de ROI y clasificación educativa de tejido ganglionar asistida por IA.
                </p>
              </div>
              <div className="histo-thumb"></div>
              <span className="bento-arrow">→</span>
            </article>

            {/* Stats */}
            <article className="bento-card bc-light">
              <div className="stat-col">
                <div className="bento-num">/ ALCANCE</div>
                <div className="stat-big"><em className="serif">1</em> plataforma</div>
                <div className="stat-sub">para formación médica de pregrado</div>
              </div>
              <div className="stat-col stat-col-border">
                <div className="bento-num">/ COBERTURA</div>
                <div className="stat-big">3 <em className="serif">módulos</em></div>
                <div className="stat-sub">chat · SCT · histopatología</div>
              </div>
            </article>
          </div>
        </div>
      </section>

      {/* ── Cómo funciona ── */}
      <section className="how-section" id="proceso">
        <div className="container">
          <div className="section-head">
            <span className="section-num">/ 02 — PROCESO</span>
            <h2 className="block-title">
              Del aula al<br /><em className="block-it">criterio clínico.</em>
            </h2>
            <span className="section-meta">El estudiante avanza a su ritmo, con feedback inmediato.</span>
          </div>

          <div className="steps-grid">
            <div className="step-card">
              <span className="step-number">01</span>
              <span className="step-tag">Inicia</span>
              <div>
                <h4 className="step-title">Eliges un área y un nivel.</h4>
                <p className="step-desc">Cardiología, hepatología, neurología, lo que estés cursando. Pregrado o internado. La plataforma calibra dificultad.</p>
              </div>
            </div>
            <div className="step-card">
              <span className="step-number">02</span>
              <span className="step-tag">Práctica</span>
              <div>
                <h4 className="step-title">Combinas los tres módulos.</h4>
                <p className="step-desc">Resuelve dudas con MediChat, calibra tu juicio con SCT, observa anatomía con el visor histopatológico — todo en una sesión.</p>
              </div>
            </div>
            <div className="step-card">
              <span className="step-number">03</span>
              <span className="step-tag">Avanza</span>
              <div>
                <h4 className="step-title">Recibes feedback razonado.</h4>
                <p className="step-desc">Cada ítem trae explicación post-test, comparación con una respuesta de referencia y una ruta sugerida para reforzar áreas débiles.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Quote ── */}
      <section className="quote-section" id="aval">
        <div className="container">
          <div className="quote-card">
            <span className="quote-mark">"</span>
            <blockquote className="quote-text">
              El SCT permite evaluar de forma objetiva la capacidad del estudiante para integrar información clínica nueva sobre una{" "}
              <em className="quote-it">hipótesis previa</em> — algo central en el ejercicio diagnóstico real.
            </blockquote>
            <div className="quote-source">
              <div className="quote-av"></div>
              <div>
                <div className="quote-name">Fundamento pedagógico del módulo</div>
                <div className="quote-role">Test de Concordancia de Scripts · ASOFAMECH</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="cta-section">
        <div className="container">
          <div className="cta-grid">
            <h2 className="cta-heading">
              ¿Listo para entrenar tu<br />
              <em className="cta-it">criterio?</em>
            </h2>
            <div>
              <p className="cta-desc">
                Acceso para estudiantes de pregrado de Medicina mediante una cuenta aprobada por la administración de la plataforma.
              </p>
              <div className="cta-buttons">
                <Link to="/auth?register=true" className="btn btn-primary btn-lg">Crear cuenta →</Link>
                <Link to="/auth" className="btn btn-outline btn-lg">Ya tengo cuenta</Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="site-footer" id="contacto">
        <div className="container">
          <div className="footer-grid">
            <div>
              <div className="logo" style={{ marginBottom: "12px" }}>
                <div className="logo-mark">A</div>
                <span>ASOFAMECH</span>
              </div>
              <p className="footer-brand-title">Plataforma educativa para el razonamiento clínico.</p>
              <p className="footer-brand-desc">Trabajo de Título · Esteban Salgado · Universidad Autónoma de Chile · 2026.</p>
            </div>
            <div>
              <h5 className="footer-col-title">Plataforma</h5>
              <ul className="footer-links">
                <li>Módulos</li>
                <li>Cómo funciona</li>
                <li>Fundamento SCT</li>
                <li>Acceso por roles</li>
              </ul>
            </div>
            <div>
              <h5 className="footer-col-title">Recursos</h5>
              <ul className="footer-links">
                <li>Asistente IA</li>
                <li>Tests SCT</li>
                <li>Visor histopatológico</li>
                <li>Casos clínicos</li>
              </ul>
            </div>
            <div>
              <h5 className="footer-col-title">Institucional</h5>
              <ul className="footer-links">
                <li>Trabajo de título</li>
                <li>Uso educativo</li>
                <li>Universidad Autónoma de Chile</li>
                <li>Edición 2026</li>
              </ul>
            </div>
          </div>
          <div className="footer-bottom">
            <span>© 2026 ASOFAMECH · Universidad Autónoma de Chile</span>
            <span className="mono">VOL.I — EDICIÓN 2026</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
