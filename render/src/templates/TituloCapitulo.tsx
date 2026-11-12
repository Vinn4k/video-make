import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "../fonte";
import { Estilo } from "../tipos";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) } as const;

// Título grande centralizado sobre a mídia da primeira cena do capítulo.
export const TituloCapitulo: React.FC<{ titulo: string; numero?: number; estilo: Estilo; duracao: number }> = ({
  titulo,
  numero,
  estilo,
  duracao,
}) => {
  const frame = useCurrentFrame();
  const saida = Math.max(45, duracao - 15);
  const visivel = interpolate(frame, [saida, saida + 12], [1, 0], suave);
  return (
    <AbsoluteFill style={{ fontFamily, opacity: visivel }}>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0.7) 100%)" }} />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", textAlign: "center", padding: "0 160px" }}>
        {numero !== undefined && (
          <div
            style={{
              color: estilo.corDestaque,
              fontSize: 36,
              fontWeight: 800,
              letterSpacing: 10,
              marginBottom: 24,
              opacity: interpolate(frame, [4, 18], [0, 1], suave),
            }}
          >
            CAPÍTULO {String(numero).padStart(2, "0")}
          </div>
        )}
        <div
          style={{
            color: estilo.corTexto,
            fontSize: 124,
            fontWeight: 900,
            lineHeight: 1.05,
            textTransform: "uppercase",
            textShadow: "0 6px 40px rgba(0,0,0,0.5)",
            opacity: interpolate(frame, [8, 24], [0, 1], suave),
            scale: interpolate(frame, [8, 40], [1.08, 1], suave),
          }}
        >
          {titulo}
        </div>
        <div
          style={{
            height: 8,
            marginTop: 36,
            backgroundColor: estilo.corDestaque,
            width: interpolate(frame, [18, 40], [0, 260], suave),
          }}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
