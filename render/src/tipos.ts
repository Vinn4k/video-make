// Formato das props geradas por pipeline/montagem.py (uma composição por capítulo).

export type Midia = {
  tipo: "imagem" | "video";
  src: string;
  duracaoSeg?: number;
  credito?: string; // "Vídeo: Canal X / YouTube": texto pequeno no canto, para mídia de terceiros
};

export type Overlay =
  | { tipo: "titulo_capitulo"; titulo: string; numero?: number }
  | { tipo: "lower_third"; titulo: string }
  | { tipo: "escalada"; titulo: string };

// Formato programa: trecho sem narração no fim do capítulo (vinheta depois da abertura, placa entre blocos).
export type Interludio = { tipo: "vinheta" | "placa"; inicio: number; duracao: number; numero: number; titulo: string };

// Faixa "A SEGUIR" nos últimos segundos de um bloco.
export type ASeguir = { titulo: string; inicio: number; duracao: number };

export type Frase = {
  texto: string;
  destaque?: string;
  rotulo?: string;
};

export type Grafico = {
  titulo: string;
  unidade?: string;
  formato: "linha" | "barras";
  pontos: [string, number][];
};

export type NumeroDestaque = { numero: string; texto: string };

export type SplitTopicos = { titulo: string; topicos: string[] };

export type Fluxo = { titulo?: string; etapas: { rotulo: string; midia: Midia | null }[] };

export type Manchete = { titulo: string; subtitulo?: string };

type Base = {
  id: number;
  inicio: number; // quadro de início dentro do capítulo
  duracao: number; // em quadros
  midia: Midia | null;
  overlay: Overlay | null;
  selo: boolean;
};

export type Cena = Base &
  (
    | { tipo: "midia" }
    | { tipo: "frase_impacto"; frase: Frase }
    | { tipo: "grafico"; grafico: Grafico }
    | { tipo: "numero_destaque"; numero: NumeroDestaque }
    | { tipo: "split_topicos"; split: SplitTopicos }
    | { tipo: "fluxo"; fluxo: Fluxo }
    | { tipo: "manchete"; manchete: Manchete }
  );

export type Estilo = {
  corDestaque: string;
  corFundo: string;
  corTexto: string;
};

export type DocumentarioProps = Estilo & {
  fps: number;
  largura: number;
  altura: number;
  transicao: number;
  cenas: Cena[];
  interludio?: Interludio | null;
  aSeguir?: ASeguir | null;
};

// Formato das props geradas por pipeline/shorts.py (um Short vertical por trecho do vídeo longo).

export type PalavraLegenda = { texto: string; inicio: number; fim: number }; // quadros do Short

export type BlocoLegenda = { inicio: number; fim: number; palavras: PalavraLegenda[] };

export type ShortProps = Estilo & {
  fps: number;
  transicao: number;
  chamada: string;
  destaque?: string;
  aviso?: string; // promessa de retenção nos primeiros segundos ("Fica até o fim: ...")
  convite?: string; // texto do convite final para o vídeo completo
  inscricao?: { inicio: number; duracao: number; clique: number; texto: string; inscrito: string } | null; // CTA no meio, em quadros
  pergunta?: { inicio: number; texto: string } | null; // balão "comenta aqui" enquanto a pergunta final é falada
  cenas: Cena[];
  legenda: BlocoLegenda[];
};
