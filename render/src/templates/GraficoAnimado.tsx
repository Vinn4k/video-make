import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "../fonte";
import { Estilo, Grafico } from "../tipos";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) } as const;

// Área do gráfico dentro do quadro de 1920x1080
const X0 = 180;
const X1 = 1740;
const Y0 = 330; // topo
const Y1 = 880; // linha de base

// Gráfico de linha (desenhada da esquerda para a direita) ou de barras (crescendo uma após a outra).
export const GraficoAnimado: React.FC<{ grafico: Grafico; estilo: Estilo }> = ({ grafico, estilo }) => {
  const frame = useCurrentFrame();
  const { pontos, unidade, formato } = grafico;
  const maximo = Math.max(...pontos.map(([, v]) => v)) * 1.15 || 1;
  const y = (v: number) => Y1 - (v / maximo) * (Y1 - Y0);
  const passo = pontos.length > 1 ? (X1 - X0) / (pontos.length - 1) : 0;
  const xLinha = (i: number) => (pontos.length > 1 ? X0 + i * passo : (X0 + X1) / 2);
  const larguraBarra = Math.min(220, ((X1 - X0) / pontos.length) * 0.6);
  const xBarra = (i: number) => X0 + ((i + 0.5) * (X1 - X0)) / pontos.length;
  const progresso = interpolate(frame, [12, 12 + 18 * pontos.length], [0, 1], { ...suave, easing: Easing.inOut(Easing.cubic) });
  const caminho = pontos.map(([, v], i) => `${i === 0 ? "M" : "L"} ${xLinha(i)} ${y(v)}`).join(" ");
  const formatar = (v: number) => `${v.toLocaleString("pt-BR")}${unidade ? ` ${unidade}` : ""}`;

  return (
    <AbsoluteFill
      style={{
        fontFamily,
        background: `radial-gradient(ellipse 70% 60% at 50% 100%, ${estilo.corDestaque}18 0%, ${estilo.corFundo}00 100%), ${estilo.corFundo}`,
      }}
    >
      <div
        style={{
          position: "absolute",
          left: X0 - 40,
          top: 110,
          color: estilo.corTexto,
          fontSize: 66,
          fontWeight: 900,
          textTransform: "uppercase",
          opacity: interpolate(frame, [0, 14], [0, 1], suave),
          translate: interpolate(frame, [0, 18], ["0px 30px", "0px 0px"], suave),
        }}
      >
        {grafico.titulo}
        <div style={{ height: 6, width: interpolate(frame, [6, 24], [0, 120], suave), backgroundColor: estilo.corDestaque, marginTop: 18 }} />
      </div>
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        <defs>
          <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={estilo.corDestaque} stopOpacity={0.35} />
            <stop offset="100%" stopColor={estilo.corDestaque} stopOpacity={0} />
          </linearGradient>
          <clipPath id="revela">
            <rect x={0} y={0} width={X0 + (X1 - X0 + 40) * progresso} height={1080} />
          </clipPath>
        </defs>
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line key={f} x1={X0 - 40} x2={X1 + 40} y1={Y1 - f * (Y1 - Y0)} y2={Y1 - f * (Y1 - Y0)} stroke="#ffffff14" strokeWidth={2} />
        ))}
        <line x1={X0 - 40} x2={X1 + 40} y1={Y1} y2={Y1} stroke="#ffffff55" strokeWidth={3} />

        {formato === "linha" ? (
          <g clipPath="url(#revela)">
            <path d={`${caminho} L ${xLinha(pontos.length - 1)} ${Y1} L ${xLinha(0)} ${Y1} Z`} fill="url(#area)" />
            <path d={caminho} fill="none" stroke={estilo.corDestaque} strokeWidth={8} strokeLinejoin="round" strokeLinecap="round" />
          </g>
        ) : (
          pontos.map(([, v], i) => {
            const cresce = interpolate(frame, [12 + i * 10, 34 + i * 10], [0, 1], suave);
            return (
              <rect
                key={i}
                x={xBarra(i) - larguraBarra / 2}
                width={larguraBarra}
                y={Y1 - (Y1 - y(v)) * cresce}
                height={(Y1 - y(v)) * cresce}
                fill={i === pontos.length - 1 ? estilo.corDestaque : "#ffffff33"}
                rx={6}
              />
            );
          })
        )}
      </svg>

      {pontos.map(([rotulo, v], i) => {
        const cx = formato === "linha" ? xLinha(i) : xBarra(i);
        const chega =
          formato === "linha"
            ? 12 + 18 * pontos.length * (pontos.length > 1 ? i / (pontos.length - 1) : 0)
            : 30 + i * 10;
        const aparece = interpolate(frame, [chega - 2, chega + 10], [0, 1], suave);
        // em um vale da linha o rótulo vai embaixo do ponto, para não encostar nas retas vizinhas
        const vale =
          formato === "linha" && i > 0 && i < pontos.length - 1 && v < pontos[i - 1][1] && v < pontos[i + 1][1];
        return (
          <div key={i}>
            {formato === "linha" && (
              <div
                style={{
                  position: "absolute",
                  left: cx - 13,
                  top: y(v) - 13,
                  width: 26,
                  height: 26,
                  borderRadius: 13,
                  backgroundColor: estilo.corFundo,
                  border: `6px solid ${estilo.corDestaque}`,
                  boxSizing: "border-box",
                  scale: aparece,
                }}
              />
            )}
            <div
              style={{
                position: "absolute",
                left: cx - 200,
                width: 400,
                top: vale ? Math.min(y(v) + 26, Y1 - 64) : y(v) - 84,
                textAlign: "center",
                color: estilo.corTexto,
                fontSize: 46,
                fontWeight: 800,
                opacity: aparece,
                translate: `0px ${(1 - aparece) * 20}px`,
              }}
            >
              {formatar(v)}
            </div>
            <div
              style={{
                position: "absolute",
                left: cx - 200,
                width: 400,
                top: Y1 + 26,
                textAlign: "center",
                color: "#ffffffaa",
                fontSize: 34,
                fontWeight: 600,
                opacity: interpolate(frame, [8, 20], [0, 1], suave),
              }}
            >
              {rotulo}
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
