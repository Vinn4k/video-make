import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "../fonte";
import { Estilo } from "../tipos";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) } as const;

// Item da escalada na abertura ("NESTE PROGRAMA" e a manchete numa faixa embaixo), como num telejornal.
export const Escalada: React.FC<{ titulo: string; estilo: Estilo; duracao: number }> = ({ titulo, estilo, duracao }) => {
  const frame = useCurrentFrame();
  const saida = interpolate(frame, [duracao - 10, duracao], [1, 0], suave);
  return (
    <AbsoluteFill style={{ fontFamily, opacity: saida }}>
      <AbsoluteFill style={{ background: "linear-gradient(0deg, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0) 45%)" }} />
      <div
        style={{
          position: "absolute",
          top: 60,
          left: 80,
          backgroundColor: estilo.corDestaque,
          color: estilo.corFundo,
          fontSize: 40,
          fontWeight: 900,
          letterSpacing: 8,
          padding: "14px 28px",
          opacity: interpolate(frame, [0, 10], [0, 1], suave),
          translate: interpolate(frame, [0, 16], ["-40px 0px", "0px 0px"], suave),
        }}
      >
        NESTE PROGRAMA
      </div>
      <AbsoluteFill style={{ justifyContent: "flex-end", padding: "0 120px 110px 80px" }}>
        <div style={{ display: "flex", gap: 28, alignItems: "stretch" }}>
          <div style={{ width: 12, backgroundColor: estilo.corDestaque, scale: `1 ${interpolate(frame, [4, 18], [0, 1], suave)}` }} />
          <div
            style={{
              color: estilo.corTexto,
              fontSize: 96,
              fontWeight: 900,
              lineHeight: 1.02,
              textTransform: "uppercase",
              textShadow: "0 6px 30px rgba(0,0,0,0.6)",
              clipPath: `inset(0 ${interpolate(frame, [8, 30], [100, 0], suave)}% 0 0)`,
            }}
          >
            {titulo}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
