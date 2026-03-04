import { useState, useCallback, useRef } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend } from "recharts";

const COLORS = {
  bg: "#0a0e1a",
  surface: "#111827",
  border: "#1e2d45",
  accent: "#00d4ff",
  accent2: "#7c3aed",
  accent3: "#10b981",
  warn: "#f59e0b",
  danger: "#ef4444",
  text: "#e2e8f0",
  muted: "#64748b",
};

const WordCloud = ({ words }) => {
  const max = Math.max(...words.map((w) => w.peso));
  const sizes = [12, 14, 16, 18, 22, 26, 30, 36, 42, 52];
  const opacities = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.85, 0.9, 0.95, 1];
  const palette = ["#00d4ff", "#7c3aed", "#10b981", "#f59e0b", "#ec4899", "#60a5fa", "#a78bfa", "#34d399", "#fbbf24", "#f87171"];

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center", justifyContent: "center", padding: "16px", minHeight: "140px" }}>
      {words.map((w, i) => {
        const ratio = w.peso / max;
        const sizeIdx = Math.round(ratio * (sizes.length - 1));
        return (
          <span
            key={w.palabra}
            style={{
              fontSize: sizes[sizeIdx],
              fontFamily: "'Space Mono', monospace",
              color: palette[i % palette.length],
              opacity: opacities[sizeIdx],
              fontWeight: sizeIdx > 5 ? 700 : 500,
              cursor: "default",
              transition: "transform 0.2s, opacity 0.2s",
              display: "inline-block",
            }}
            onMouseEnter={(e) => { e.target.style.transform = "scale(1.15)"; e.target.style.opacity = 1; }}
            onMouseLeave={(e) => { e.target.style.transform = "scale(1)"; e.target.style.opacity = opacities[sizeIdx]; }}
          >
            {w.palabra}
          </span>
        );
      })}
    </div>
  );
};

const Card = ({ children, style = {}, glow }) => (
  <div style={{
    background: COLORS.surface,
    border: `1px solid ${glow ? glow : COLORS.border}`,
    borderRadius: "12px",
    padding: "20px",
    boxShadow: glow ? `0 0 20px ${glow}22` : "0 4px 24px #00000044",
    ...style
  }}>
    {children}
  </div>
);

const Label = ({ children, color }) => (
  <p style={{ fontSize: 11, fontFamily: "'Space Mono', monospace", letterSpacing: "2px", textTransform: "uppercase", color: color || COLORS.muted, marginBottom: 6, margin: "0 0 6px 0" }}>
    {children}
  </p>
);

const BigNum = ({ value, color }) => (
  <p style={{ fontSize: 42, fontWeight: 800, fontFamily: "'DM Serif Display', serif", color: color || COLORS.accent, margin: 0, lineHeight: 1 }}>
    {value}
  </p>
);

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div style={{ background: "#1e2d45", border: `1px solid ${COLORS.border}`, borderRadius: 8, padding: "8px 14px" }}>
        <p style={{ color: COLORS.text, margin: 0, fontSize: 13, fontFamily: "'Space Mono', monospace" }}>{label}: <strong style={{ color: COLORS.accent }}>{payload[0].value}</strong></p>
      </div>
    );
  }
  return null;
};

const BACKEND_URL = "http://localhost:8000/process-conversations";

const Spinner = () => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 20 }}>
    <div style={{
      width: 56, height: 56,
      border: `3px solid ${COLORS.border}`,
      borderTop: `3px solid ${COLORS.accent}`,
      borderRadius: "50%",
      animation: "spin 0.9s linear infinite",
    }} />
    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    <p style={{ color: COLORS.muted, fontFamily: "'Space Mono', monospace", fontSize: 12, letterSpacing: "2px", margin: 0 }}>
      ANALIZANDO CONVERSACIONES...
    </p>
    <p style={{ color: COLORS.muted, fontFamily: "'DM Sans', sans-serif", fontSize: 12, margin: 0, opacity: 0.6 }}>
      El agente IA está procesando los chats, puede tardar un momento
    </p>
  </div>
);

export default function App() {
  const [data, setData] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const fileRef = useRef();

  const sendFile = async (file) => {
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(BACKEND_URL, {
        method: "POST",
        body: formData,
      });

      const json = await res.json();

      if (!res.ok) {
        throw new Error(json.detail || "Error desconocido del servidor");
      }

      // El backend devuelve { content: "...json string..." }
      // Limpiamos posibles bloques de código que el agente pueda haber añadido
      let raw = json.content.trim();
      console.log(raw);
      raw = raw.replace(/^```json\s*/i, "").replace(/^```\s*/i, "").replace(/```\s*$/i, "").trim();
      const parsed = JSON.parse(raw);
      setData(parsed);
    } catch (e) {
      if (e instanceof SyntaxError) {
        setError("El agente no devolvió un JSON válido. Revisa el prompt del agente.");
        
      } else {
        setError(e.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) sendFile(file);
  }, []);

  const handleFile = (e) => {
    const file = e.target.files[0];
    if (file) sendFile(file);
  };

  if (!data) {
    return (
      <div style={{ minHeight: "100vh", background: COLORS.bg, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "sans-serif" }}>
        <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Space+Mono:wght@400;700&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet" />
        <div style={{ textAlign: "center", maxWidth: 520, padding: "0 24px" }}>
          <div style={{ marginBottom: 32 }}>
            <div style={{ width: 72, height: 72, borderRadius: "50%", background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.accent2})`, margin: "0 auto 20px", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 32 }}>
              📊
            </div>
            <h1 style={{ color: COLORS.text, fontFamily: "'DM Serif Display', serif", fontSize: 40, margin: "0 0 8px 0", fontWeight: 400 }}>
              LLM Analytics
            </h1>
            <p style={{ color: COLORS.muted, fontFamily: "'DM Sans', sans-serif", fontSize: 15, margin: 0 }}>
              Dashboard de análisis pedagógico para agentes LLM
            </p>
          </div>

          {loading ? (
            <Spinner />
          ) : (
            <>
              <div
                onClick={() => fileRef.current.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                style={{
                  border: `2px dashed ${dragOver ? COLORS.accent : COLORS.border}`,
                  borderRadius: 16,
                  padding: "48px 32px",
                  cursor: "pointer",
                  transition: "all 0.2s",
                  background: dragOver ? `${COLORS.accent}08` : "transparent",
                  boxShadow: dragOver ? `0 0 30px ${COLORS.accent}22` : "none",
                }}
              >
                <div style={{ fontSize: 52, marginBottom: 16 }}>📁</div>
                <p style={{ color: COLORS.text, fontFamily: "'DM Sans', sans-serif", fontSize: 16, margin: "0 0 8px 0", fontWeight: 600 }}>
                  Arrastra tu JSON de chats aquí
                </p>
                <p style={{ color: COLORS.muted, fontSize: 13, fontFamily: "'DM Sans', sans-serif", margin: 0 }}>
                  o haz clic para seleccionarlo
                </p>
                <input ref={fileRef} type="file" accept=".json" onChange={handleFile} style={{ display: "none" }} />
              </div>

              {error && (
                <p style={{ color: COLORS.danger, fontFamily: "'Space Mono', monospace", fontSize: 12, marginTop: 16 }}>
                  ⚠ {error}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    );
  }

  const { metricas_generales, temas_frecuentes, nivel_dificultad, satisfaccion_alumno, nube_de_palabras, alertas_pedagogicas } = data;

  const dificultadData = [
    { name: "Básico", value: nivel_dificultad.basico, color: COLORS.accent3 },
    { name: "Intermedio", value: nivel_dificultad.intermedio, color: COLORS.accent },
    { name: "Avanzado", value: nivel_dificultad.avanzado, color: COLORS.accent2 },
  ];

  const satisfaccionData = [
    { name: "Satisfecho", value: satisfaccion_alumno.satisfecho, color: COLORS.accent3 },
    { name: "Neutral", value: satisfaccion_alumno.neutral, color: COLORS.warn },
    { name: "Frustrado", value: satisfaccion_alumno.frustrado_o_confundido, color: COLORS.danger },
  ];

  const totalSat = satisfaccionData.reduce((s, d) => s + d.value, 0);

  return (
    <div style={{ minHeight: "100vh", background: COLORS.bg, color: COLORS.text, fontFamily: "'DM Sans', sans-serif", padding: "24px" }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Space+Mono:wght@400;700&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet" />

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 28, flexWrap: "wrap", gap: 16 }}>
        <div>
          <h1 style={{ fontFamily: "'DM Serif Display', serif", fontSize: 30, margin: 0, fontWeight: 400, background: `linear-gradient(90deg, ${COLORS.accent}, ${COLORS.accent2})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            LLM Analytics Dashboard
          </h1>
          <p style={{ color: COLORS.muted, margin: "4px 0 0", fontSize: 12, fontFamily: "'Space Mono', monospace" }}>
            Análisis pedagógico de conversaciones
          </p>
        </div>
        <button
          onClick={() => setData(null)}
          style={{ background: "transparent", border: `1px solid ${COLORS.border}`, color: COLORS.muted, borderRadius: 8, padding: "8px 16px", cursor: "pointer", fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: "1px" }}
        >
          ← CARGAR OTRO
        </button>
      </div>

      {/* KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 14, marginBottom: 16 }}>
        <Card glow={COLORS.accent}>
          <Label color={COLORS.accent}>Conversaciones</Label>
          <BigNum value={metricas_generales.total_conversaciones_analizadas} color={COLORS.accent} />
          <p style={{ color: COLORS.muted, fontSize: 11, margin: "6px 0 0", fontFamily: "'Space Mono', monospace" }}>total analizadas</p>
        </Card>
        <Card glow={COLORS.accent2}>
          <Label color={COLORS.accent2}>Interacciones / chat</Label>
          <BigNum value={metricas_generales.promedio_interacciones_por_chat} color={COLORS.accent2} />
          <p style={{ color: COLORS.muted, fontSize: 11, margin: "6px 0 0", fontFamily: "'Space Mono', monospace" }}>promedio</p>
        </Card>
        <Card glow={COLORS.accent3}>
          <Label color={COLORS.accent3}>Satisfacción</Label>
          <BigNum
            value={totalSat > 0 ? `${Math.round((satisfaccion_alumno.satisfecho / totalSat) * 100)}%` : "—"}
            color={COLORS.accent3}
          />
          <p style={{ color: COLORS.muted, fontSize: 11, margin: "6px 0 0", fontFamily: "'Space Mono', monospace" }}>alumnos satisfechos</p>
        </Card>
        <Card glow={COLORS.warn}>
          <Label color={COLORS.warn}>Alertas</Label>
          <BigNum value={alertas_pedagogicas?.length || 0} color={COLORS.warn} />
          <p style={{ color: COLORS.muted, fontSize: 11, margin: "6px 0 0", fontFamily: "'Space Mono', monospace" }}>pedagógicas activas</p>
        </Card>
      </div>

      {/* Row 2 */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,2fr) minmax(0,1fr) minmax(0,1fr)", gap: 14, marginBottom: 16 }}>
        <Card>
          <Label>Temas más frecuentes</Label>
          <div style={{ marginTop: 12 }}>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={temas_frecuentes} layout="vertical" margin={{ left: 0, right: 16, top: 4, bottom: 4 }}>
                <XAxis type="number" tick={{ fill: COLORS.muted, fontSize: 11, fontFamily: "'Space Mono', monospace" }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="tema" tick={{ fill: COLORS.text, fontSize: 11, fontFamily: "'DM Sans', sans-serif" }} axisLine={false} tickLine={false} width={140} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="menciones" radius={[0, 6, 6, 0]}>
                  {temas_frecuentes.map((_, i) => (
                    <Cell key={i} fill={`hsl(${190 + i * 22}, 75%, ${55 - i * 2}%)`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <Label>Nivel de dificultad</Label>
          <ResponsiveContainer width="100%" height={210}>
            <PieChart>
              <Pie data={dificultadData} dataKey="value" cx="50%" cy="45%" innerRadius={48} outerRadius={72} paddingAngle={3}>
                {dificultadData.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Pie>
              <Tooltip formatter={(v, n) => [v, n]} contentStyle={{ background: "#1e2d45", border: "none", borderRadius: 8, fontFamily: "'Space Mono', monospace", fontSize: 11 }} />
              <Legend formatter={(v) => <span style={{ color: COLORS.text, fontSize: 11, fontFamily: "'DM Sans', sans-serif" }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <Label>Satisfacción alumno</Label>
          <div style={{ marginTop: 20 }}>
            {satisfaccionData.map((s) => {
              const pct = totalSat > 0 ? (s.value / totalSat) * 100 : 0;
              return (
                <div key={s.name} style={{ marginBottom: 18 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 12, color: COLORS.text, fontFamily: "'DM Sans', sans-serif" }}>{s.name}</span>
                    <span style={{ fontSize: 12, color: s.color, fontFamily: "'Space Mono', monospace", fontWeight: 700 }}>{s.value}</span>
                  </div>
                  <div style={{ height: 7, background: COLORS.border, borderRadius: 99, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${pct}%`, background: s.color, borderRadius: 99, transition: "width 1s ease" }} />
                  </div>
                  <p style={{ color: COLORS.muted, fontSize: 10, fontFamily: "'Space Mono', monospace", margin: "3px 0 0", textAlign: "right" }}>
                    {totalSat > 0 ? `${Math.round(pct)}%` : "—"}
                  </p>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Row 3 */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <Card>
          <Label>Nube de palabras clave</Label>
          <WordCloud words={nube_de_palabras || []} />
        </Card>

        <Card glow={COLORS.warn}>
          <Label color={COLORS.warn}>⚠ Alertas pedagógicas</Label>
          <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10, maxHeight: 220, overflowY: "auto" }}>
            {(alertas_pedagogicas || []).map((alerta, i) => (
              <div key={i} style={{ background: `${COLORS.warn}0a`, border: `1px solid ${COLORS.warn}33`, borderRadius: 8, padding: "12px 14px", borderLeft: `3px solid ${COLORS.warn}` }}>
                <p style={{ color: COLORS.text, fontSize: 12, margin: 0, lineHeight: 1.65, fontFamily: "'DM Sans', sans-serif" }}>
                  {alerta}
                </p>
              </div>
            ))}
            {(!alertas_pedagogicas || alertas_pedagogicas.length === 0) && (
              <p style={{ color: COLORS.muted, fontSize: 13, fontFamily: "'Space Mono', monospace" }}>Sin alertas activas ✓</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
