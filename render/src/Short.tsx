import { AbsoluteFill, Easing, interpolate, interpolateColors, Sequence, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { MidiaCena } from "./cenas/MidiaCena";
import { Conteudo } from "./Documentario";
import { fontFamily } from "./fonte";
import { BlocoLegenda, Cena, Estilo, ShortProps } from "./tipos";

const suave = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.33, 0, 0.67, 1) } as const;

// Templates foram desenhados em 1920x1080: no Short entram inteiros numa janela, nesta altura.
const ESCALA = 1080 / 1920;
const TOPO_JANELA = 560;
const FIM_CTA = 75; // quadros finais com o convite para o vídeo completo
const AVISO_INICIO = 30; // o aviso de retenção entra depois do primeiro segundo (imagem limpa no início)
const AVISO_DURACAO = 120; // e fica uns 4 s

// Corte vertical (1080x1920) de um trecho do vídeo longo: as cenas com a mesma narração,
// uma chamada fixa no topo e legenda grande palavra por palavra.
export const Short: React.FC<ShortProps> = (props) => {
  const { cenas, transicao } = props;
  const { durationInFrames } = useVideoConfig();
  // o CTA de inscrição chega já encaixado entre o aviso e o convite (pipeline/shorts.py), com o sinal sonoro no mesmo quadro
  const cta = props.inscricao;
  return (
    <AbsoluteFill style={{ backgroundColor: props.corFundo, fontFamily }}>
      {cenas.map((cena, i) => {
        const ultima = i === cenas.length - 1;
        return (
          <Sequence
            key={cena.id}
            name={`Cena ${cena.id} · ${cena.tipo}`}
            from={cena.inicio}
            durationInFrames={cena.duracao + (ultima ? 0 : transicao)}
          >
            <CenaVertical cena={cena} estilo={props} entrada={i === 0 ? 0 : transicao} />
          </Sequence>
        );
      })}
      {/* sombras que garantem leitura da chamada e da legenda sobre qualquer imagem */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.65) 0%, rgba(0,0,0,0) 28%, rgba(0,0,0,0) 58%, rgba(0,0,0,0.6) 82%, rgba(0,0,0,0.2) 100%)",
        }}
      />
      <Chamada texto={props.chamada} destaque={props.destaque} estilo={props} />
      <Legenda blocos={props.legenda} estilo={props} />
      {props.aviso && (
        <Sequence name="Aviso" from={AVISO_INICIO} durationInFrames={AVISO_DURACAO}>
          <Aviso texto={props.aviso} estilo={props} />
        </Sequence>
      )}
      {cta && (
        <Sequence name="Inscrição" from={cta.inicio} durationInFrames={cta.duracao}>
          <Inscricao duracao={cta.duracao} clique={cta.clique} texto={cta.texto} inscrito={cta.inscrito} />
        </Sequence>
      )}
      {props.pergunta && (
        <Sequence name="Pergunta" from={props.pergunta.inicio}>
          <Comentario texto={props.pergunta.texto} estilo={props} />
        </Sequence>
      )}
      <Sequence name="Convite" from={Math.max(0, durationInFrames - FIM_CTA)}>
        <Convite texto={props.convite || "Vídeo completo no canal ▶"} estilo={props} />
      </Sequence>
    </AbsoluteFill>
  );
};

const CenaVertical: React.FC<{ cena: Cena; estilo: Estilo; entrada: number }> = ({ cena, estilo, entrada }) => {
  const frame = useCurrentFrame();
  const total = cena.duracao + entrada;
  const opacidade = entrada > 0 ? interpolate(frame, [0, entrada], [0, 1], suave) : 1;

  if (cena.tipo === "midia") {
    return (
      <AbsoluteFill style={{ opacity: opacidade }}>
        <MidiaCena midia={cena.midia} id={cena.id} duracao={total} estilo={estilo} />
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ opacity: opacidade, overflow: "hidden" }}>
      {cena.midia && (
        <AbsoluteFill style={{ filter: "blur(36px) brightness(0.45)", scale: 1.15 }}>
          <MidiaCena midia={cena.midia} id={cena.id} duracao={total} estilo={estilo} />
        </AbsoluteFill>
      )}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: TOPO_JANELA,
          width: 1920,
          height: 1080,
          transformOrigin: "top left",
          scale: ESCALA,
          overflow: "hidden",
          boxShadow: cena.midia ? "0 30px 80px rgba(0,0,0,0.6)" : undefined,
        }}
      >
        <Conteudo cena={cena} estilo={estilo} total={total} />
      </div>
    </AbsoluteFill>
  );
};

const Chamada: React.FC<{ texto: string; destaque?: string; estilo: Estilo }> = ({ texto, destaque, estilo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entra = spring({ frame, fps, config: { damping: 200 } });
  const marcadas = new Set((destaque ?? "").toLowerCase().split(/\s+/).filter(Boolean));
  return (
    <div
      style={{
        position: "absolute",
        top: 190,
        left: 70,
        right: 70,
        textAlign: "center",
        color: estilo.corTexto,
        fontSize: 64,
        fontWeight: 900,
        lineHeight: 1.25,
        textTransform: "uppercase",
        textShadow: "0 4px 18px rgba(0,0,0,0.7)",
        opacity: entra,
        translate: `0 ${interpolate(entra, [0, 1], [-30, 0])}px`,
      }}
    >
      {texto.split(/\s+/).map((palavra, i, todas) => {
        const marcada = (p?: string) => !!p && marcadas.has(p.toLowerCase().replace(/[^\p{L}\p{N}-]/gu, ""));
        const marca = marcada(palavra);
        // palavras marcadas vizinhas viram uma faixa só
        const junta = (vizinha?: string) => marca && marcada(vizinha);
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              marginLeft: junta(todas[i - 1]) ? 0 : 8,
              marginRight: junta(todas[i + 1]) ? 0 : 8,
              padding: marca ? "0 14px" : 0,
              color: marca ? estilo.corFundo : estilo.corTexto,
              backgroundColor: marca ? estilo.corDestaque : "transparent",
              textShadow: marca ? "none" : undefined,
            }}
          >
            {palavra}
          </span>
        );
      })}
    </div>
  );
};

// Mostra um bloco curto por vez; a palavra que está sendo falada ganha a cor do canal.
const Legenda: React.FC<{ blocos: BlocoLegenda[]; estilo: Estilo }> = ({ blocos, estilo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const bloco = blocos.find((b) => frame >= b.inicio && frame < b.fim);
  if (!bloco) return null;
  const surge = spring({ frame: frame - bloco.inicio, fps, config: { damping: 14, stiffness: 220 }, durationInFrames: 8 });
  return (
    <div
      style={{
        position: "absolute",
        top: 1250,
        left: 60,
        right: 60,
        textAlign: "center",
        fontSize: 86,
        fontWeight: 900,
        lineHeight: 1.15,
        textTransform: "uppercase",
        scale: interpolate(surge, [0, 1], [0.85, 1]),
      }}
    >
      {bloco.palavras.map((p, i) => {
        const falando = frame >= p.inicio && (i === bloco.palavras.length - 1 || frame < bloco.palavras[i + 1].inicio);
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              margin: "0 12px",
              color: falando ? estilo.corDestaque : estilo.corTexto,
              WebkitTextStroke: "12px #000",
              paintOrder: "stroke fill",
              textShadow: "0 6px 20px rgba(0,0,0,0.6)",
            }}
          >
            {p.texto}
          </span>
        );
      })}
    </div>
  );
};

// Promessa curta logo abaixo da chamada: segura quem chegou pelo feed até a revelação.
const Aviso: React.FC<{ texto: string; estilo: Estilo }> = ({ texto, estilo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entra = spring({ frame, fps, config: { damping: 200 } });
  const sai = interpolate(frame, [AVISO_DURACAO - 10, AVISO_DURACAO], [1, 0], suave);
  return (
    <div
      style={{
        position: "absolute",
        top: 420,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity: Math.min(entra, sai),
        translate: `0 ${interpolate(entra, [0, 1], [20, 0])}px`,
      }}
    >
      <div
        style={{
          padding: "14px 30px",
          borderRadius: 999,
          backgroundColor: "rgba(0,0,0,0.72)",
          border: `4px solid ${estilo.corDestaque}`,
          color: estilo.corTexto,
          fontSize: 40,
          fontWeight: 800,
          maxWidth: 940,
          textAlign: "center",
        }}
      >
        {texto}
      </div>
    </div>
  );
};

const Convite: React.FC<{ texto: string; estilo: Estilo }> = ({ texto, estilo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entra = spring({ frame, fps, config: { damping: 200 } });
  return (
    <div
      style={{
        position: "absolute",
        top: 400,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity: entra,
        scale: interpolate(entra, [0, 1], [0.9, 1]),
      }}
    >
      <div
        style={{
          padding: "18px 36px",
          borderRadius: 999,
          backgroundColor: estilo.corDestaque,
          color: estilo.corFundo,
          fontSize: 42,
          fontWeight: 800,
          letterSpacing: 1,
        }}
      >
        {texto}
      </div>
    </div>
  );
};

const BALAO = "M4 3h16a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H9l-5 4v-4H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm3 6.5a1.5 1.5 0 1 0 0 .01Zm5 0a1.5 1.5 0 1 0 0 .01Zm5 0a1.5 1.5 0 1 0 0 .01Z";

// Balão "comenta aqui embaixo" no meio da tela enquanto o narrador faz a pergunta final; pulsa de leve.
const Comentario: React.FC<{ texto: string; estilo: Estilo }> = ({ texto, estilo }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entra = spring({ frame, fps, config: { damping: 12, stiffness: 160 } });
  const pulso = 1 + 0.04 * Math.sin((frame / fps) * Math.PI * 2);
  return (
    <div style={{ position: "absolute", top: 1020, left: 0, right: 0, display: "flex", justifyContent: "center" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 18,
          padding: "20px 40px 20px 28px",
          borderRadius: 36,
          backgroundColor: "white",
          color: estilo.corFundo,
          fontSize: 50,
          fontWeight: 900,
          textTransform: "uppercase",
          boxShadow: "0 12px 40px rgba(0,0,0,0.55)",
          scale: entra * pulso,
        }}
      >
        <svg width="58" height="58" viewBox="0 0 24 24" fill={estilo.corFundo} style={{ flexShrink: 0 }}>
          <path d={BALAO} fillRule="evenodd" />
        </svg>
        {texto}
      </div>
    </div>
  );
};

const SINO =
  "M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6V11a7 7 0 0 0-5.5-6.84V3.5a1.5 1.5 0 0 0-3 0v.66A7 7 0 0 0 5 11v5l-2 2v1h18v-1l-2-2Z";

// Botão "inscreva-se" com o sino balançando; um toque (no quadro `clique`) o vira em "inscrito".
const Inscricao: React.FC<{ duracao: number; clique: number; texto: string; inscrito: string }> = ({
  duracao,
  clique,
  texto,
  inscrito,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const feito = frame >= clique;
  const entra = spring({ frame, fps, config: { damping: 12, stiffness: 180 } });
  const sai = interpolate(frame, [duracao - 10, duracao], [1, 0], suave);
  const aperto = interpolate(frame, [clique - 4, clique, clique + 6], [1, 0.92, 1], suave);
  // depois do toque o sino toca mais forte por uns quadros, como notificação ativada
  const ciclo = feito ? frame - clique : frame % fps;
  const forca = feito ? interpolate(frame - clique, [0, 24], [1.6, 1], suave) : 1;
  const giro = interpolate(ciclo, [0, 4, 8, 12, 16], [0, 18, -14, 8, 0], { extrapolateRight: "clamp" }) * forca;
  // o "dedo" chega pela direita, toca e some; o anel marca o toque
  const dedo = interpolate(frame, [clique - 18, clique], [1, 0], suave);
  const dedoVisivel = interpolate(frame, [clique - 18, clique - 12, clique + 4, clique + 10], [0, 1, 1, 0], suave);
  const anel = interpolate(frame, [clique, clique + 14], [0, 1], suave);
  return (
    <div
      style={{
        position: "absolute",
        top: 420,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity: sai,
      }}
    >
      <div
        style={{
          position: "relative",
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "16px 38px 16px 26px",
          borderRadius: 999,
          backgroundColor: interpolateColors(frame, [clique, clique + 4], ["#E5262A", "#2B2B2B"]),
          border: "3px solid rgba(255,255,255,0.18)",
          color: "white",
          fontSize: 44,
          fontWeight: 900,
          textTransform: "uppercase",
          maxWidth: 940,
          boxShadow: "0 10px 34px rgba(0,0,0,0.55)",
          scale: entra * aperto,
        }}
      >
        <svg width="50" height="50" viewBox="0 0 24 24" fill="white" style={{ flexShrink: 0, transformOrigin: "50% 10%", rotate: `${giro}deg` }}>
          <path d={SINO} />
        </svg>
        {feito ? `✓ ${inscrito}` : texto}
        {frame >= clique && anel < 1 && (
          <div
            style={{
              position: "absolute",
              right: 40,
              top: "50%",
              width: 90,
              height: 90,
              marginTop: -45,
              borderRadius: 999,
              border: "6px solid white",
              opacity: 1 - anel,
              scale: 0.5 + anel * 1.4,
            }}
          />
        )}
        {dedoVisivel > 0 && (
          <div
            style={{
              position: "absolute",
              right: 55,
              top: "50%",
              width: 60,
              height: 60,
              marginTop: -30,
              borderRadius: 999,
              backgroundColor: "rgba(255,255,255,0.85)",
              boxShadow: "0 4px 14px rgba(0,0,0,0.5)",
              opacity: dedoVisivel,
              translate: `${dedo * 200}px ${dedo * 160}px`,
              scale: feito ? 0.85 : 1,
            }}
          />
        )}
      </div>
    </div>
  );
};
