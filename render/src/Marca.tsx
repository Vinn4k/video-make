import { AbsoluteFill } from "remotion";
import { fontFamily } from "./fonte";

// Identidade do canal "Seu Canal": engenharia (grade, ponte) e natureza (folha, curvas de nível).
const AMARELO = "#F5C518";
const FUNDO = "#0B0F14";

// Globo: metade esquerda em grade geométrica (obras), metade direita uma folha (biodiversidade).
export const Globo: React.FC<{ tamanho: number }> = ({ tamanho }) => (
  <svg width={tamanho} height={tamanho} viewBox="0 0 600 600">
    <defs>
      <clipPath id="metadeEsquerda">
        <rect x="0" y="0" width="300" height="600" />
      </clipPath>
      <clipPath id="dentro">
        <circle cx="300" cy="300" r="236" />
      </clipPath>
    </defs>
    <g clipPath="url(#dentro)" stroke={AMARELO} strokeWidth="18" fill="none" strokeLinecap="round">
      <g clipPath="url(#metadeEsquerda)">
        <ellipse cx="300" cy="300" rx="118" ry="250" />
        <line x1="40" y1="300" x2="300" y2="300" />
        <path d="M 60 190 Q 180 170 300 170" />
        <path d="M 60 410 Q 180 430 300 430" />
      </g>
      <line x1="300" y1="40" x2="300" y2="560" strokeWidth="14" />
    </g>
    {/* folha ocupando a metade direita */}
    <path d="M 318 512 C 300 380 330 210 470 120 C 520 250 500 420 318 512 Z" fill={AMARELO} />
    <path d="M 330 492 C 370 380 410 270 462 150" stroke={FUNDO} strokeWidth="12" fill="none" strokeLinecap="round" />
    <path d="M 372 400 L 440 360 M 398 320 L 470 290 M 352 450 L 408 432" stroke={FUNDO} strokeWidth="9" fill="none" strokeLinecap="round" />
    <circle cx="300" cy="300" r="250" stroke={AMARELO} strokeWidth="28" fill="none" />
  </svg>
);

export const Avatar: React.FC = () => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(circle at 50% 42%, #1a2230 0%, ${FUNDO} 70%)`,
      justifyContent: "center",
      alignItems: "center",
    }}
  >
    <Globo tamanho={560} />
  </AbsoluteFill>
);

// Ponte estaiada em traço de planta técnica.
const Ponte: React.FC = () => {
  const torres = [260, 640];
  const deck = 560;
  return (
    // fica à esquerda da área segura (que começa em x = 507), sem encostar no globo
    <svg width={560} height={436} viewBox="0 0 900 700" style={{ position: "absolute", left: -10, top: 520, opacity: 0.55 }}>
      <g stroke={AMARELO} fill="none" strokeLinecap="round">
        <line x1="0" y1={deck} x2="900" y2={deck} strokeWidth="6" />
        <line x1="0" y1={deck + 22} x2="900" y2={deck + 22} strokeWidth="2" opacity="0.6" />
        {torres.map((x) => (
          <g key={x}>
            <path d={`M ${x - 22} ${deck + 120} L ${x} 140 L ${x + 22} ${deck + 120}`} strokeWidth="6" />
            {[0, 1, 2, 3, 4, 5, 6].map((i) => (
              <g key={i} strokeWidth="2">
                <line x1={x} y1={170 + i * 22} x2={x - 40 - i * 32} y2={deck} />
                <line x1={x} y1={170 + i * 22} x2={x + 40 + i * 32} y2={deck} />
              </g>
            ))}
          </g>
        ))}
        {[80, 450, 820].map((x) => (
          <line key={x} x1={x} y1={deck + 22} x2={x} y2={deck + 140} strokeWidth="3" opacity="0.6" />
        ))}
      </g>
      <g fill={AMARELO} opacity="0.7" fontFamily={fontFamily} fontSize="18" fontWeight="600">
        <text x="250" y="120">H = 138 m</text>
        <text x="370" y={deck + 64}>vão central 380 m</text>
      </g>
    </svg>
  );
};

// Curvas de nível irregulares, como num mapa topográfico.
const CurvasDeNivel: React.FC = () => {
  const curvas = Array.from({ length: 14 }, (_, k) => {
    const raio = 60 + k * 38;
    const pontos = Array.from({ length: 49 }, (_, i) => {
      const a = (i / 48) * Math.PI * 2;
      const r = raio * (1 + 0.12 * Math.sin(3 * a + k * 0.7) + 0.06 * Math.cos(5 * a - k));
      return `${i === 0 ? "M" : "L"} ${(Math.cos(a) * r).toFixed(1)} ${(Math.sin(a) * r * 0.8).toFixed(1)}`;
    });
    return pontos.join(" ") + " Z";
  });
  return (
    <svg width={1100} height={1440} viewBox="-550 -720 1100 1440" style={{ position: "absolute", right: -260, top: 0, opacity: 0.32 }}>
      {curvas.map((d, k) => (
        <path key={k} d={d} stroke={k % 4 === 0 ? AMARELO : "#ffffff"} strokeWidth={k % 4 === 0 ? 3 : 1.6} fill="none" />
      ))}
    </svg>
  );
};

const Folha: React.FC<{ x: number; y: number; tamanho: number; giro: number; opacidade: number }> = ({ x, y, tamanho, giro, opacidade }) => (
  <svg width={tamanho} height={tamanho} viewBox="0 0 200 200" style={{ position: "absolute", left: x, top: y, rotate: `${giro}deg`, opacity: opacidade }}>
    <path d="M 100 190 C 40 130 50 50 100 10 C 150 50 160 130 100 190 Z" fill={AMARELO} />
    <path d="M 100 182 L 100 30" stroke={FUNDO} strokeWidth="6" />
  </svg>
);

export const Banner: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: FUNDO, fontFamily, overflow: "hidden" }}>
    {/* grade de planta técnica à esquerda, sumindo para o centro */}
    <AbsoluteFill
      style={{
        backgroundImage:
          "linear-gradient(#ffffff10 2px, transparent 2px), linear-gradient(90deg, #ffffff10 2px, transparent 2px)",
        backgroundSize: "48px 48px",
        maskImage: "linear-gradient(90deg, black 0%, black 25%, transparent 45%)",
      }}
    />
    <Ponte />
    <CurvasDeNivel />
    <Folha x={2180} y={330} tamanho={150} giro={-25} opacidade={0.5} />
    <Folha x={2330} y={760} tamanho={110} giro={35} opacidade={0.35} />
    <Folha x={2060} y={980} tamanho={90} giro={-60} opacidade={0.3} />
    <AbsoluteFill style={{ background: `radial-gradient(ellipse 34% 30% at 50% 50%, ${FUNDO} 30%, ${FUNDO}00 100%)` }} />

    {/* área segura do YouTube: 1546x423 no centro */}
    <div
      style={{
        position: "absolute",
        left: 507,
        top: 508,
        width: 1546,
        height: 423,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 50,
      }}
    >
      <div style={{ flexShrink: 0, display: "flex" }}>
        <Globo tamanho={260} />
      </div>
      <div>
        <div style={{ color: "white", fontSize: 100, fontWeight: 900, lineHeight: 1, letterSpacing: -2, whiteSpace: "nowrap" }}>
          POR TRÁS DO <span style={{ color: AMARELO }}>MUNDO</span>
        </div>
        <div style={{ height: 8, width: 180, backgroundColor: AMARELO, margin: "26px 0 24px" }} />
        <div style={{ color: "#ffffffd9", fontSize: 40, fontWeight: 600, lineHeight: 1.3 }}>
          Engenharia, natureza e ciência:
          <br />o que existe por trás do que você vê
        </div>
      </div>
    </div>
  </AbsoluteFill>
);
