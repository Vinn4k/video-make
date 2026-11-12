import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "../fonte";
import { Estilo } from "../tipos";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) } as const;

// Tarja no canto inferior esquerdo nomeando o lugar ou o conceito da cena.
export const LowerThird: React.FC<{ titulo: string; estilo: Estilo; duracao: number }> = ({ titulo, estilo, duracao }) => {
  const frame = useCurrentFrame();
  const saida = Math.max(30, duracao - 12);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", padding: "0 0 120px 100px", fontFamily }}>
      <div
        style={{
          display: "flex",
          alignItems: "stretch",
          opacity: interpolate(frame, [saida, saida + 10], [1, 0], suave),
          translate: interpolate(frame, [6, 24], ["-60px 0px", "0px 0px"], suave),
        }}
      >
        <div style={{ width: 12, backgroundColor: estilo.corDestaque, scale: `1 ${interpolate(frame, [4, 16], [0, 1], suave)}` }} />
        <div
          style={{
            backgroundColor: "rgba(11, 15, 20, 0.86)",
            color: estilo.corTexto,
            fontSize: 50,
            fontWeight: 800,
            letterSpacing: 2,
            textTransform: "uppercase",
            padding: "20px 34px",
            clipPath: `inset(0 ${interpolate(frame, [8, 26], [100, 0], suave)}% 0 0)`,
          }}
        >
          {titulo}
        </div>
      </div>
    </AbsoluteFill>
  );
};
