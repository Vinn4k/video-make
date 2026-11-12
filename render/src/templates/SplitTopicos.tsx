import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { MidiaCena } from "../cenas/MidiaCena";
import { fontFamily } from "../fonte";
import { Estilo, Midia, SplitTopicos as Dados } from "../tipos";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) } as const;

// Mídia à esquerda e painel escuro à direita com título e tópicos entrando um a um.
export const SplitTopicos: React.FC<{ split: Dados; midia: Midia | null; id: number; estilo: Estilo; duracao: number }> = ({
  split,
  midia,
  id,
  estilo,
  duracao,
}) => {
  const frame = useCurrentFrame();
  const intervalo = Math.max(10, Math.min(24, (duracao - 40) / Math.max(1, split.topicos.length)));
  return (
    <AbsoluteFill style={{ backgroundColor: estilo.corFundo, fontFamily, flexDirection: "row" }}>
      <div
        style={{
          position: "relative",
          width: "54%",
          height: "100%",
          overflow: "hidden",
          clipPath: `inset(0 ${interpolate(frame, [0, 18], [100, 0], suave)}% 0 0)`,
        }}
      >
        <MidiaCena midia={midia} id={id} duracao={duracao} estilo={estilo} />
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 110px 0 90px" }}>
        <div
          style={{
            color: estilo.corTexto,
            fontSize: 72,
            fontWeight: 900,
            lineHeight: 1.05,
            textTransform: "uppercase",
            opacity: interpolate(frame, [8, 20], [0, 1], suave),
            translate: interpolate(frame, [8, 26], ["30px 0px", "0px 0px"], suave),
          }}
        >
          {split.titulo}
        </div>
        <div style={{ height: 6, width: interpolate(frame, [14, 32], [0, 110], suave), backgroundColor: estilo.corDestaque, margin: "28px 0 44px" }} />
        {split.topicos.map((topico, i) => {
          const entra = 24 + i * intervalo;
          return (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 26,
                marginBottom: 34,
                color: estilo.corTexto,
                fontSize: 44,
                fontWeight: 600,
                lineHeight: 1.25,
                opacity: interpolate(frame, [entra, entra + 12], [0, 1], suave),
                translate: interpolate(frame, [entra, entra + 16], ["40px 0px", "0px 0px"], suave),
              }}
            >
              <div style={{ width: 18, height: 18, marginTop: 16, flexShrink: 0, backgroundColor: estilo.corDestaque }} />
              {topico}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
