import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { MidiaCena } from "../cenas/MidiaCena";
import { fontFamily } from "../fonte";
import { Estilo, Manchete as Dados, Midia } from "../tipos";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) } as const;

// Mídia em tela cheia com uma manchete à esquerda, como capa de reportagem.
export const Manchete: React.FC<{ manchete: Dados; midia: Midia | null; id: number; estilo: Estilo; duracao: number }> = ({
  manchete,
  midia,
  id,
  estilo,
  duracao,
}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <MidiaCena midia={midia} id={id} duracao={duracao} estilo={estilo} />
      <AbsoluteFill
        style={{
          background: `linear-gradient(90deg, ${estilo.corFundo}f2 0%, ${estilo.corFundo}cc 38%, ${estilo.corFundo}00 72%)`,
          opacity: interpolate(frame, [0, 14], [0, 1], suave),
        }}
      />
      <AbsoluteFill style={{ justifyContent: "center", padding: "0 0 0 140px" }}>
        <div style={{ display: "flex", gap: 34, maxWidth: 1050 }}>
          <div style={{ width: 10, backgroundColor: estilo.corDestaque, scale: `1 ${interpolate(frame, [4, 22], [0, 1], suave)}`, transformOrigin: "top" }} />
          <div>
            <div
              style={{
                color: estilo.corTexto,
                fontSize: 84,
                fontWeight: 800,
                lineHeight: 1.08,
                opacity: interpolate(frame, [8, 22], [0, 1], suave),
                translate: interpolate(frame, [8, 28], ["0px 34px", "0px 0px"], suave),
              }}
            >
              {manchete.titulo}
            </div>
            {manchete.subtitulo && (
              <div
                style={{
                  color: "#ffffffbb",
                  fontSize: 44,
                  fontWeight: 600,
                  lineHeight: 1.3,
                  marginTop: 28,
                  opacity: interpolate(frame, [20, 34], [0, 1], suave),
                }}
              >
                {manchete.subtitulo}
              </div>
            )}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
