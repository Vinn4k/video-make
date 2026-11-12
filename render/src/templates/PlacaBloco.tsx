import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "../fonte";
import { Globo } from "../Marca";
import { Estilo } from "../tipos";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) } as const;

// Placa em tela cheia entre os blocos do programa ("BLOCO 02" e o nome do bloco): é a volta do intervalo.
export const PlacaBloco: React.FC<{ numero: number; titulo: string; estilo: Estilo; duracao: number }> = ({
  numero,
  titulo,
  estilo,
  duracao,
}) => {
  const frame = useCurrentFrame();
  // uma faixa amarela varre a tela e revela o fundo, como a troca de bloco na TV
  const varrida = interpolate(frame, [0, 14], [0, 100], suave);
  const saida = interpolate(frame, [duracao - 8, duracao], [1, 0], suave);
  return (
    <AbsoluteFill style={{ backgroundColor: estilo.corFundo, fontFamily }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at 30% 50%, #1a2230 0%, ${estilo.corFundo} 70%)`,
          clipPath: `inset(0 ${100 - varrida}% 0 0)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          width: 40,
          left: `calc(${varrida}% - 40px)`,
          backgroundColor: estilo.corDestaque,
          opacity: interpolate(frame, [12, 18], [1, 0], suave),
        }}
      />
      <AbsoluteFill style={{ justifyContent: "center", padding: "0 0 0 170px", opacity: saida }}>
        <div
          style={{
            color: estilo.corDestaque,
            fontSize: 46,
            fontWeight: 800,
            letterSpacing: 14,
            opacity: interpolate(frame, [10, 22], [0, 1], suave),
            translate: interpolate(frame, [10, 26], ["0px 24px", "0px 0px"], suave),
          }}
        >
          BLOCO {String(numero).padStart(2, "0")}
        </div>
        <div
          style={{
            color: estilo.corTexto,
            fontSize: 132,
            fontWeight: 900,
            lineHeight: 1.02,
            maxWidth: 1450,
            marginTop: 18,
            textTransform: "uppercase",
            opacity: interpolate(frame, [16, 30], [0, 1], suave),
            translate: interpolate(frame, [16, 36], ["0px 40px", "0px 0px"], suave),
          }}
        >
          {titulo}
        </div>
        <div
          style={{
            height: 10,
            marginTop: 40,
            backgroundColor: estilo.corDestaque,
            width: interpolate(frame, [26, 50], [0, 320], suave),
          }}
        />
      </AbsoluteFill>
      <div
        style={{
          position: "absolute",
          right: 90,
          bottom: 70,
          display: "flex",
          alignItems: "center",
          gap: 18,
          color: "#ffffffaa",
          fontSize: 28,
          fontWeight: 800,
          letterSpacing: 6,
          opacity: interpolate(frame, [20, 34], [0, 1], suave) * saida,
        }}
      >
        <Globo tamanho={64} />
        SEU CANAL
      </div>
    </AbsoluteFill>
  );
};
