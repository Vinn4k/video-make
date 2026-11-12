import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../fonte";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.34, 1.56, 0.64, 1) } as const;

const SINO =
  "M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6V11a7 7 0 0 0-5.5-6.84V3.5a1.5 1.5 0 0 0-3 0v.66A7 7 0 0 0 5 11v5l-2 2v1h18v-1l-2-2Z";
const BALAO = "M4 3h16a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H9l-5 4v-4H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm3 6.5a1.5 1.5 0 1 0 0 .01Zm5 0a1.5 1.5 0 1 0 0 .01Zm5 0a1.5 1.5 0 1 0 0 .01Z";

// Selo "inscreva-se" no canto superior esquerdo, com o sino balançando a cada 2 segundos,
// e logo abaixo o "comente", que entra um pouco depois e balança o balão.
export const SeloInscricao: React.FC<{ duracao: number }> = ({ duracao }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ciclo = frame % (2 * fps);
  const balanco = (c: number) => interpolate(c, [0, 4, 8, 12, 16], [0, 18, -14, 8, 0], { extrapolateRight: "clamp" });
  const pilula = {
    display: "flex",
    alignItems: "center",
    gap: 14,
    alignSelf: "flex-start",
    borderRadius: 999,
    fontSize: 30,
    fontWeight: 800,
    boxShadow: "0 8px 30px rgba(0,0,0,0.35)",
    transformOrigin: "left center",
  } as const;
  return (
    <AbsoluteFill style={{ padding: "50px 0 0 60px", fontFamily, gap: 14 }}>
      <div
        style={{
          ...pilula,
          backgroundColor: "#E5262A",
          color: "white",
          padding: "12px 30px 12px 18px",
          scale: interpolate(frame, [0, 14, duracao - 10, duracao], [0, 1, 1, 0], suave),
        }}
      >
        <svg width="38" height="38" viewBox="0 0 24 24" fill="white" style={{ transformOrigin: "50% 10%", rotate: `${balanco(ciclo)}deg` }}>
          <path d={SINO} />
        </svg>
        INSCREVA-SE NO CANAL
      </div>
      <div
        style={{
          ...pilula,
          backgroundColor: "white",
          color: "#111",
          padding: "10px 28px 10px 18px",
          scale: interpolate(frame, [12, 26, duracao - 10, duracao], [0, 1, 1, 0], suave),
        }}
      >
        <svg width="34" height="34" viewBox="0 0 24 24" fill="#111" style={{ transformOrigin: "20% 90%", rotate: `${balanco((frame + fps) % (2 * fps))}deg` }}>
          <path d={BALAO} fillRule="evenodd" />
        </svg>
        COMENTE O QUE ACHOU
      </div>
    </AbsoluteFill>
  );
};
