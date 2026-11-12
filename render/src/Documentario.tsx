import { AbsoluteFill, Easing, interpolate, Sequence, useCurrentFrame } from "remotion";
import { MidiaCena } from "./cenas/MidiaCena";
import { Fluxo } from "./templates/Fluxo";
import { FraseImpacto } from "./templates/FraseImpacto";
import { GraficoAnimado } from "./templates/GraficoAnimado";
import { LowerThird } from "./templates/LowerThird";
import { Manchete } from "./templates/Manchete";
import { NumeroDestaque } from "./templates/NumeroDestaque";
import { SplitTopicos } from "./templates/SplitTopicos";
import { SeloInscricao } from "./templates/SeloInscricao";
import { TituloCapitulo } from "./templates/TituloCapitulo";
import { ASeguir } from "./templates/ASeguir";
import { Escalada } from "./templates/Escalada";
import { PlacaBloco } from "./templates/PlacaBloco";
import { Vinheta } from "./templates/Vinheta";
import { Cena, DocumentarioProps, Estilo } from "./tipos";

// Cada cena se estende `transicao` quadros por baixo da seguinte, que entra com fade:
// o resultado é um crossfade sem mudar o tempo da narração.
export const Documentario: React.FC<DocumentarioProps> = (props) => {
  const { cenas, transicao, interludio, aSeguir } = props;
  return (
    <AbsoluteFill style={{ backgroundColor: props.corFundo }}>
      {cenas.map((cena, i) => {
        const ultima = i === cenas.length - 1;
        return (
          <Sequence
            key={cena.id}
            name={`Cena ${cena.id} · ${cena.tipo}`}
            from={cena.inicio}
            durationInFrames={cena.duracao + (ultima && !interludio ? 0 : transicao)}
          >
            <CenaVisual cena={cena} estilo={props} entrada={i === 0 ? 0 : transicao} />
          </Sequence>
        );
      })}
      {aSeguir && aSeguir.duracao > 0 && (
        <Sequence name="A seguir" from={aSeguir.inicio} durationInFrames={aSeguir.duracao}>
          <ASeguir titulo={aSeguir.titulo} estilo={props} duracao={aSeguir.duracao} />
        </Sequence>
      )}
      {interludio && (
        <Sequence name={interludio.tipo === "vinheta" ? "Vinheta" : `Placa bloco ${interludio.numero}`} from={interludio.inicio} durationInFrames={interludio.duracao}>
          {interludio.tipo === "vinheta" ? (
            <Vinheta numero={interludio.numero} titulo={interludio.titulo} estilo={props} duracao={interludio.duracao} />
          ) : (
            <PlacaBloco numero={interludio.numero} titulo={interludio.titulo} estilo={props} duracao={interludio.duracao} />
          )}
        </Sequence>
      )}
      {trechosComSelo(cenas).map(([inicio, duracao]) => (
        <Sequence key={`selo-${inicio}`} name="Selo inscrição" from={inicio} durationInFrames={duracao}>
          <SeloInscricao duracao={duracao} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

const CenaVisual: React.FC<{ cena: Cena; estilo: Estilo; entrada: number }> = ({ cena, estilo, entrada }) => {
  const frame = useCurrentFrame();
  const total = cena.duracao + entrada;
  return (
    <AbsoluteFill
      style={{
        opacity:
          entrada > 0
            ? interpolate(frame, [0, entrada], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.33, 0, 0.67, 1),
              })
            : 1,
      }}
    >
      <Conteudo cena={cena} estilo={estilo} total={total} />
    </AbsoluteFill>
  );
};

export const Conteudo: React.FC<{ cena: Cena; estilo: Estilo; total: number }> = ({ cena, estilo, total }) => {
  const comum = { midia: cena.midia, id: cena.id, estilo, duracao: total };
  switch (cena.tipo) {
    case "frase_impacto":
      return <FraseImpacto frase={cena.frase} estilo={estilo} duracao={total} />;
    case "grafico":
      return <GraficoAnimado grafico={cena.grafico} estilo={estilo} />;
    case "numero_destaque":
      return <NumeroDestaque numero={cena.numero} {...comum} />;
    case "split_topicos":
      return <SplitTopicos split={cena.split} {...comum} />;
    case "fluxo":
      return <Fluxo fluxo={cena.fluxo} id={cena.id} estilo={estilo} duracao={total} />;
    case "manchete":
      return <Manchete manchete={cena.manchete} {...comum} />;
    default:
      return (
        <>
          <MidiaCena midia={cena.midia} id={cena.id} duracao={total} estilo={estilo} />
          {cena.overlay?.tipo === "titulo_capitulo" && (
            <TituloCapitulo titulo={cena.overlay.titulo} numero={cena.overlay.numero} estilo={estilo} duracao={cena.duracao} />
          )}
          {cena.overlay?.tipo === "lower_third" && (
            <LowerThird titulo={cena.overlay.titulo} estilo={estilo} duracao={cena.duracao} />
          )}
          {cena.overlay?.tipo === "escalada" && (
            <Escalada titulo={cena.overlay.titulo} estilo={estilo} duracao={cena.duracao} />
          )}
        </>
      );
  }
};

// Junta cenas consecutivas marcadas com selo num único trecho, para o selo não piscar entre elas.
function trechosComSelo(cenas: Cena[]): [number, number][] {
  const trechos: [number, number][] = [];
  for (const cena of cenas) {
    if (!cena.selo) continue;
    const ultimo = trechos[trechos.length - 1];
    if (ultimo && ultimo[0] + ultimo[1] === cena.inicio) {
      ultimo[1] += cena.duracao;
    } else {
      trechos.push([cena.inicio, cena.duracao]);
    }
  }
  return trechos;
}
