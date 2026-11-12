import { CalculateMetadataFunction, Composition } from "remotion";
import { Documentario } from "./Documentario";
import { Avatar, Banner } from "./Marca";
import { Short } from "./Short";
import { Thumbnail } from "./Thumbnail";
import { DocumentarioProps, ShortProps } from "./tipos";

// Props de exemplo para abrir no Studio sem rodar o pipeline.
const exemplo: DocumentarioProps = {
  fps: 30,
  largura: 1920,
  altura: 1080,
  corDestaque: "#F5C518",
  corFundo: "#0B0F14",
  corTexto: "#FFFFFF",
  transicao: 10,
  cenas: [
    {
      id: 1, inicio: 0, duracao: 150, tipo: "midia", selo: false,
      midia: { tipo: "imagem", src: "exemplo/larvas.jpg" },
      overlay: { tipo: "titulo_capitulo", titulo: "O exército invisível", numero: 1 },
    },
    {
      id: 2, inicio: 150, duracao: 150, tipo: "frase_impacto", midia: null, overlay: null, selo: true,
      frase: { texto: "Uma larva que transforma isopor em comida", destaque: "isopor em comida", rotulo: "Descoberta" },
    },
    {
      id: 3, inicio: 300, duracao: 150, tipo: "midia", selo: false,
      midia: { tipo: "imagem", src: "exemplo/lab.jpg" },
      overlay: { tipo: "lower_third", titulo: "Universidade de Stanford" },
    },
    {
      id: 4, inicio: 450, duracao: 180, tipo: "grafico", midia: null, overlay: null, selo: false,
      grafico: { titulo: "Extensão da mancha", unidade: "km", formato: "linha", pontos: [["1993", 530], ["2014", 85], ["2019", 200], ["2023", 174]] },
    },
    {
      id: 5, inicio: 630, duracao: 150, tipo: "numero_destaque", overlay: null, selo: false,
      midia: { tipo: "imagem", src: "exemplo/isopor.jpg" },
      numero: { numero: "90%", texto: "do plástico desmontado em dez horas" },
    },
    {
      id: 6, inicio: 780, duracao: 180, tipo: "split_topicos", overlay: null, selo: false,
      midia: { tipo: "imagem", src: "exemplo/larvas.jpg" },
      split: { titulo: "O resultado", topicos: ["Isopor cheio de túneis", "Larvas vivas e saudáveis", "Metade virou gás carbônico"] },
    },
    {
      id: 7, inicio: 960, duracao: 180, tipo: "fluxo", midia: null, overlay: null, selo: false,
      fluxo: {
        titulo: "Do lixo ao bioplástico",
        etapas: [
          { rotulo: "Garrafa", midia: { tipo: "imagem", src: "exemplo/isopor.jpg" } },
          { rotulo: "Bactéria", midia: { tipo: "imagem", src: "exemplo/larvas.jpg" } },
          { rotulo: "Bioplástico", midia: { tipo: "imagem", src: "exemplo/lab.jpg" } },
        ],
      },
    },
    {
      id: 8, inicio: 1140, duracao: 150, tipo: "manchete", overlay: null, selo: false,
      midia: { tipo: "imagem", src: "exemplo/abelhas.jpg" },
      manchete: { titulo: "Larva de traça fura sacola plástica em menos de uma hora", subtitulo: "Espanha, 2017" },
    },
  ],
};

const calculateMetadata: CalculateMetadataFunction<DocumentarioProps> = ({ props }) => {
  const ultima = props.cenas[props.cenas.length - 1];
  const fim = props.interludio ? props.interludio.inicio + props.interludio.duracao : ultima.inicio + ultima.duracao;
  return {
    durationInFrames: Math.max(1, fim),
    fps: props.fps,
    width: props.largura,
    height: props.altura,
  };
};

// Short de exemplo: as três primeiras cenas de exemplo, com legenda falsa de 3 palavras por bloco.
const exemploShort: ShortProps = {
  fps: 30,
  corDestaque: exemplo.corDestaque,
  corFundo: exemplo.corFundo,
  corTexto: exemplo.corTexto,
  transicao: 10,
  chamada: "Larvas que comem isopor",
  destaque: "isopor",
  cenas: exemplo.cenas.slice(0, 5).map((c) => ({ ...c, overlay: null, selo: false })),
  legenda: Array.from({ length: 26 }, (_, i) => ({
    inicio: i * 30,
    fim: i * 30 + 30,
    palavras: ["Uma", "larva", "que"].map((texto, j) => ({ texto, inicio: i * 30 + j * 10, fim: i * 30 + j * 10 + 10 })),
  })),
};

const metadataShort: CalculateMetadataFunction<ShortProps> = ({ props }) => {
  const ultima = props.cenas[props.cenas.length - 1];
  return { durationInFrames: Math.max(1, ultima.inicio + ultima.duracao), fps: props.fps, width: 1080, height: 1920 };
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
    <Composition id="Avatar" component={Avatar} durationInFrames={1} fps={30} width={800} height={800} />
    <Composition id="Banner" component={Banner} durationInFrames={1} fps={30} width={2560} height={1440} />
    <Composition
      id="Thumbnail"
      component={Thumbnail}
      durationInFrames={1}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{
        imagem: "exemplo/larvas.jpg",
        texto: "Elas comem isopor",
        destaque: "isopor",
        selo: "Descoberta",
        layout: "esquerda" as const,
        corDestaque: "#F5C518",
        corFundo: "#0B0F14",
      }}
    />
    <Composition
      id="CapaShort"
      component={Thumbnail}
      durationInFrames={1}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        imagem: "exemplo/larvas.jpg",
        texto: "Elas comem isopor?",
        destaque: "isopor",
        selo: "Descoberta",
        layout: "centro" as const,
        corDestaque: "#F5C518",
        corFundo: "#0B0F14",
      }}
    />
    <Composition
      id="Documentario"
      component={Documentario}
      durationInFrames={450}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={exemplo}
      calculateMetadata={calculateMetadata}
    />
    <Composition
      id="Short"
      component={Short}
      durationInFrames={780}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={exemploShort}
      calculateMetadata={metadataShort}
    />
    </>
  );
};
