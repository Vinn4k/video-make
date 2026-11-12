import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { MidiaCena } from "../cenas/MidiaCena";
import { fontFamily } from "../fonte";
import { Estilo, Midia, NumeroDestaque as Dados } from "../tipos";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) } as const;

// Número enorme que conta do zero até o valor, com a explicação embaixo, sobre a mídia escurecida.
export const NumeroDestaque: React.FC<{ numero: Dados; midia: Midia | null; id: number; estilo: Estilo; duracao: number }> = ({
  numero,
  midia,
  id,
  estilo,
  duracao,
}) => {
  const frame = useCurrentFrame();
  const conta = interpolate(frame, [6, 50], [0, 1], { ...suave, easing: Easing.out(Easing.cubic) });
  return (
    <AbsoluteFill style={{ fontFamily }}>
      <MidiaCena midia={midia} id={id} duracao={duracao} estilo={estilo} />
      <AbsoluteFill style={{ backgroundColor: estilo.corFundo, opacity: midia ? 0.72 : 1 }} />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", textAlign: "center", padding: "0 200px" }}>
        <div
          style={{
            color: estilo.corDestaque,
            fontSize: 250,
            fontWeight: 900,
            lineHeight: 1,
            fontVariantNumeric: "tabular-nums",
            scale: interpolate(frame, [0, 20], [0.85, 1], suave),
            opacity: interpolate(frame, [0, 10], [0, 1], suave),
          }}
        >
          {contar(numero.numero, conta)}
        </div>
        <div
          style={{
            color: estilo.corTexto,
            fontSize: 64,
            fontWeight: 800,
            lineHeight: 1.2,
            marginTop: 30,
            maxWidth: 1400,
            textTransform: "uppercase",
            opacity: interpolate(frame, [22, 36], [0, 1], suave),
            translate: interpolate(frame, [22, 40], ["0px 30px", "0px 0px"], suave),
          }}
        >
          {numero.texto}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// "1.000.000" → conta com separador de milhar; "3,5 bi" → mantém a vírgula e o sufixo; texto sem número fica igual.
function contar(texto: string, progresso: number): string {
  const m = /^(\D*)([\d.,]+)(.*)$/.exec(texto);
  if (!m) return texto;
  const [, antes, corpo, depois] = m;
  const decimais = corpo.includes(",") ? corpo.split(",")[1].length : 0;
  const valor = Number(corpo.replace(/\./g, "").replace(",", "."));
  if (!Number.isFinite(valor)) return texto;
  const atual = (valor * progresso).toLocaleString("pt-BR", { minimumFractionDigits: decimais, maximumFractionDigits: decimais });
  return `${antes}${atual}${depois}`;
}
