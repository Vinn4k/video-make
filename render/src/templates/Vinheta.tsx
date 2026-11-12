import { AbsoluteFill, Easing, interpolate, Sequence, useCurrentFrame } from "remotion";
import { fontFamily } from "../fonte";
import { Globo } from "../Marca";
import { Estilo } from "../tipos";
import { PlacaBloco } from "./PlacaBloco";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) } as const;
const elastico = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.34, 1.56, 0.64, 1) } as const;

// Vinheta do canal depois da abertura: o globo entra, o nome do programa aparece, e ela termina na placa do bloco 1.
export const Vinheta: React.FC<{ numero: number; titulo: string; estilo: Estilo; duracao: number }> = ({
  numero,
  titulo,
  estilo,
  duracao,
}) => {
  const frame = useCurrentFrame();
  const placa = Math.round(duracao * 0.45); // o fim da vinheta já é a placa do primeiro bloco
  const inicioPlaca = duracao - placa;
  const sai = interpolate(frame, [inicioPlaca - 10, inicioPlaca + 4], [1, 0], suave);
  const nome = "SEU CANAL";
  return (
    <AbsoluteFill style={{ backgroundColor: estilo.corFundo, fontFamily }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 50% 45%, #1d2736 0%, ${estilo.corFundo} 65%)`,
          opacity: interpolate(frame, [0, 12], [0, 1], suave),
        }}
      />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", opacity: sai }}>
        <div
          style={{
            scale: interpolate(frame, [0, 26], [0.4, 1], elastico),
            rotate: `${interpolate(frame, [0, 30], [-40, 0], suave)}deg`,
            opacity: interpolate(frame, [0, 10], [0, 1], suave),
            filter: `drop-shadow(0 0 ${interpolate(frame, [20, 40], [0, 40], suave)}px ${estilo.corDestaque}66)`,
          }}
        >
          <Globo tamanho={300} />
        </div>
        <div style={{ display: "flex", marginTop: 36, color: estilo.corTexto, fontSize: 92, fontWeight: 900, letterSpacing: 8 }}>
          {nome.split("").map((letra, i) => (
            <span
              key={i}
              style={{
                display: "inline-block",
                whiteSpace: "pre",
                opacity: interpolate(frame, [18 + i * 1.2, 26 + i * 1.2], [0, 1], suave),
                translate: interpolate(frame, [18 + i * 1.2, 30 + i * 1.2], ["0px 30px", "0px 0px"], suave),
              }}
            >
              {letra}
            </span>
          ))}
        </div>
        <div
          style={{
            marginTop: 22,
            color: estilo.corDestaque,
            fontSize: 34,
            fontWeight: 800,
            letterSpacing: 12,
            opacity: interpolate(frame, [38, 52], [0, 1], suave),
          }}
        >
          ENGENHARIA · NATUREZA · CIÊNCIA
        </div>
      </AbsoluteFill>
      <Sequence from={inicioPlaca} durationInFrames={placa}>
        <PlacaBloco numero={numero} titulo={titulo} estilo={estilo} duracao={placa} />
      </Sequence>
    </AbsoluteFill>
  );
};
