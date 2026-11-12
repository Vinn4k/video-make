import { Video } from "@remotion/media";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Estilo, Midia } from "../tipos";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.45, 0, 0.55, 1) } as const;

// Quatro movimentos de câmera alternados pelo id da cena, para as fotos não parecerem slides.
const MOVIMENTOS: { escala: [number, number]; x: [number, number] }[] = [
  { escala: [1.0, 1.14], x: [0, 0] },
  { escala: [1.14, 1.0], x: [0, 0] },
  { escala: [1.12, 1.12], x: [-3, 3] },
  { escala: [1.12, 1.12], x: [3, -3] },
];

export const MidiaCena: React.FC<{ midia: Midia | null; id: number; duracao: number; estilo: Estilo }> = ({
  midia,
  id,
  duracao,
  estilo,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!midia) {
    return <FundoAnimado estilo={estilo} duracao={duracao} />;
  }

  if (midia.tipo === "video") {
    const disponivel = (midia.duracaoSeg ?? 0) * fps;
    // pula o começo do clipe (costuma ter fade ou câmera parada) quando ele é longo o bastante
    const pulo = disponivel > duracao + fps ? Math.floor(Math.min((disponivel - duracao) / 2, 2 * fps)) : 0;
    return (
      <AbsoluteFill>
        <AbsoluteFill style={{ scale: interpolate(frame, [0, duracao], [1.0, 1.06], suave) }}>
          <Video
            src={staticFile(midia.src)}
            muted
            loop={disponivel < duracao + pulo}
            trimBefore={pulo}
            objectFit="cover"
            style={{ width: "100%", height: "100%" }}
          />
        </AbsoluteFill>
        {midia.credito && <Credito texto={midia.credito} />}
      </AbsoluteFill>
    );
  }

  const mov = MOVIMENTOS[id % MOVIMENTOS.length];
  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: estilo.corFundo }}>
      <Img
        src={staticFile(midia.src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          scale: interpolate(frame, [0, duracao], mov.escala, suave),
          translate: interpolate(frame, [0, duracao], [`${mov.x[0]}% 0%`, `${mov.x[1]}% 0%`], suave),
        }}
      />
      {midia.credito && <Credito texto={midia.credito} />}
    </AbsoluteFill>
  );
};

// Crédito pequeno no canto inferior direito, fora do movimento de câmera.
const Credito: React.FC<{ texto: string }> = ({ texto }) => (
  <div
    style={{
      position: "absolute",
      right: 28,
      bottom: 22,
      fontSize: 20,
      fontWeight: 600,
      color: "rgba(255,255,255,0.85)",
      textShadow: "0 1px 4px rgba(0,0,0,0.9)",
    }}
  >
    {texto}
  </div>
);

// Usado quando nenhum banco de imagens achou nada para a cena.
const FundoAnimado: React.FC<{ estilo: Estilo; duracao: number }> = ({ estilo, duracao }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: estilo.corFundo, overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 30% 40%, ${estilo.corDestaque}33 0%, transparent 45%),
                       radial-gradient(circle at 75% 65%, #2a6f9744 0%, transparent 50%)`,
          scale: interpolate(frame, [0, duracao], [1, 1.25], suave),
          rotate: interpolate(frame, [0, duracao], ["0deg", "8deg"], suave),
        }}
      />
    </AbsoluteFill>
  );
};
