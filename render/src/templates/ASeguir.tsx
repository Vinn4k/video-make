import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "../fonte";
import { Estilo } from "../tipos";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) } as const;

// Faixa "A SEGUIR" no canto inferior direito nos últimos segundos de um bloco, como antes do intervalo na TV.
export const ASeguir: React.FC<{ titulo: string; estilo: Estilo; duracao: number }> = ({ titulo, estilo, duracao }) => {
  const frame = useCurrentFrame();
  const visivel = interpolate(frame, [0, 16, duracao - 10, duracao], [0, 1, 1, 0], suave);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "flex-end", padding: "0 90px 110px 0", fontFamily }}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-end",
          opacity: visivel,
          translate: interpolate(frame, [0, 20], ["80px 0px", "0px 0px"], suave),
        }}
      >
        <div
          style={{
            backgroundColor: estilo.corDestaque,
            color: estilo.corFundo,
            fontSize: 30,
            fontWeight: 900,
            letterSpacing: 8,
            padding: "10px 22px",
          }}
        >
          A SEGUIR
        </div>
        <div
          style={{
            backgroundColor: "rgba(11, 15, 20, 0.9)",
            color: estilo.corTexto,
            fontSize: 48,
            fontWeight: 800,
            textTransform: "uppercase",
            maxWidth: 900,
            textAlign: "right",
            lineHeight: 1.1,
            padding: "18px 28px",
            borderRight: `10px solid ${estilo.corDestaque}`,
            clipPath: `inset(0 0 0 ${interpolate(frame, [6, 26], [100, 0], suave)}%)`,
          }}
        >
          {titulo}
        </div>
      </div>
    </AbsoluteFill>
  );
};
