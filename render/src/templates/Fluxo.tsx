import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { MidiaCena } from "../cenas/MidiaCena";
import { fontFamily } from "../fonte";
import { Estilo, Fluxo as Dados } from "../tipos";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) } as const;

// Etapas de um processo ou de uma cadeia (2 a 4), cada uma com foto e rótulo, ligadas por setas que se desenham.
export const Fluxo: React.FC<{ fluxo: Dados; id: number; estilo: Estilo; duracao: number }> = ({ fluxo, id, estilo, duracao }) => {
  const frame = useCurrentFrame();
  const n = fluxo.etapas.length;
  const espaco = 110; // entre caixas, onde fica a seta
  const largura = Math.min(440, (1640 - espaco * (n - 1)) / n);
  const altura = largura * 0.75;
  const total = largura * n + espaco * (n - 1);
  const x0 = (1920 - total) / 2;
  const topo = fluxo.titulo ? 400 : 330;
  const passo = Math.max(14, Math.min(26, (duracao - 30) / n));

  return (
    <AbsoluteFill
      style={{
        fontFamily,
        background: `radial-gradient(ellipse 80% 60% at 50% 50%, ${estilo.corDestaque}12 0%, ${estilo.corFundo}00 100%), ${estilo.corFundo}`,
      }}
    >
      {fluxo.titulo && (
        <div
          style={{
            position: "absolute",
            top: 140,
            width: "100%",
            textAlign: "center",
            color: estilo.corTexto,
            fontSize: 64,
            fontWeight: 900,
            textTransform: "uppercase",
            opacity: interpolate(frame, [0, 14], [0, 1], suave),
          }}
        >
          {fluxo.titulo}
        </div>
      )}
      {fluxo.etapas.map((etapa, i) => {
        const entra = 8 + i * passo;
        const x = x0 + i * (largura + espaco);
        return (
          <div key={i}>
            <div
              style={{
                position: "absolute",
                left: x,
                top: topo - 66,
                width: largura,
                textAlign: "center",
                color: estilo.corDestaque,
                fontSize: 34,
                fontWeight: 800,
                letterSpacing: 3,
                textTransform: "uppercase",
                opacity: interpolate(frame, [entra + 4, entra + 14], [0, 1], suave),
              }}
            >
              {etapa.rotulo}
            </div>
            <div
              style={{
                position: "absolute",
                left: x,
                top: topo,
                width: largura,
                height: altura,
                overflow: "hidden",
                border: `5px solid ${estilo.corDestaque}`,
                boxShadow: "0 20px 50px rgba(0,0,0,0.45)",
                opacity: interpolate(frame, [entra, entra + 10], [0, 1], suave),
                scale: interpolate(frame, [entra, entra + 18], [0.9, 1], suave),
              }}
            >
              <MidiaCena midia={etapa.midia} id={id + i} duracao={duracao} estilo={estilo} />
            </div>
            {i < n - 1 && (
              <svg
                width={espaco}
                height={60}
                style={{ position: "absolute", left: x + largura, top: topo + altura / 2 - 30 }}
              >
                <line
                  x1={14}
                  y1={30}
                  x2={14 + (espaco - 40) * interpolate(frame, [entra + 12, entra + passo], [0, 1], suave)}
                  y2={30}
                  stroke={estilo.corDestaque}
                  strokeWidth={8}
                  strokeLinecap="round"
                />
                <path
                  d={`M ${espaco - 34} 14 L ${espaco - 12} 30 L ${espaco - 34} 46`}
                  fill="none"
                  stroke={estilo.corDestaque}
                  strokeWidth={8}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity={interpolate(frame, [entra + passo - 4, entra + passo + 2], [0, 1], suave)}
                />
              </svg>
            )}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
