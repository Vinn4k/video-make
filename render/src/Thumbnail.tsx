import { AbsoluteFill, Img, staticFile } from "remotion";
import { fontFamily } from "./fonte";

export type ThumbnailProps = {
  imagem: string; // caminho dentro da pasta pública (pasta do projeto)
  texto: string; // 2 a 4 palavras
  destaque?: string; // parte de `texto` que ganha a faixa na cor do canal
  selo?: string; // etiqueta pequena no canto (ex.: "DESCOBERTA")
  layout: "esquerda" | "baixo" | "centro"; // "centro": capa em pé dos Shorts (1080x1920)
  corDestaque: string;
  corFundo: string;
};

// Capa 1280x720 (ou 1080x1920 no layout "centro"): imagem saturada em tela cheia, texto enorme com contorno
// e o trecho de destaque numa faixa.
export const Thumbnail: React.FC<ThumbnailProps> = ({ imagem, texto, destaque, selo, layout, corDestaque, corFundo }) => {
  const esquerda = layout === "esquerda";
  // na capa em pé o texto fica no meio: é a parte que sobra nos recortes de YouTube, Instagram e TikTok
  const centro = layout === "centro";
  const palavras = dividir(texto, destaque);
  return (
    <AbsoluteFill style={{ backgroundColor: corFundo, fontFamily, overflow: "hidden" }}>
      <Img
        src={staticFile(imagem)}
        style={{
          position: "absolute",
          // no layout "esquerda" a imagem ocupa a direita e escapa para trás do texto
          left: esquerda ? "28%" : 0,
          width: esquerda ? "72%" : "100%",
          height: "100%",
          objectFit: "cover",
          filter: "saturate(1.3) contrast(1.12) brightness(1.04)",
        }}
      />
      <AbsoluteFill
        style={{
          background: centro
            ? `linear-gradient(0deg, ${corFundo}99 0%, ${corFundo}33 30%, ${corFundo}88 50%, ${corFundo}33 70%, ${corFundo}99 100%)`
            : esquerda
              ? `linear-gradient(90deg, ${corFundo} 0%, ${corFundo} 30%, ${corFundo}cc 45%, ${corFundo}00 68%)`
              : `linear-gradient(0deg, ${corFundo}f0 0%, ${corFundo}99 30%, ${corFundo}00 58%)`,
        }}
      />
      {selo && !centro && (
        <div
          style={{
            // na capa em pé o selo entra na coluna, logo acima do texto
            position: centro ? "relative" : "absolute",
            top: centro ? undefined : 36,
            left: centro ? undefined : 40,
            order: centro ? -1 : undefined,
            backgroundColor: "#E5262A",
            color: "white",
            fontSize: 34,
            fontWeight: 900,
            letterSpacing: 2,
            padding: "8px 22px",
            borderRadius: 10,
            textTransform: "uppercase",
            boxShadow: "0 6px 20px rgba(0,0,0,0.45)",
            rotate: "-3deg",
          }}
        >
          {selo}
        </div>
      )}
      <AbsoluteFill
        style={{
          justifyContent: esquerda || centro ? "center" : "flex-end",
          alignItems: esquerda ? "flex-start" : "center",
          padding: centro ? "0 50px" : esquerda ? "60px 0 0 48px" : "0 60px 46px",
        }}
      >
        {selo && centro && (
          <div
            style={{
              // na capa em pé o selo entra na coluna, logo acima do texto
              position: centro ? "relative" : "absolute",
              top: centro ? undefined : 36,
              left: centro ? undefined : 40,
              order: centro ? -1 : undefined,
              backgroundColor: "#E5262A",
              color: "white",
              fontSize: 34,
              fontWeight: 900,
              letterSpacing: 2,
              padding: "8px 22px",
              borderRadius: 10,
              textTransform: "uppercase",
              boxShadow: "0 6px 20px rgba(0,0,0,0.45)",
              rotate: "-3deg",
              marginBottom: 34,
            }}
          >
            {selo}
          </div>
        )}
        <div
          style={{
            maxWidth: centro ? 980 : esquerda ? 620 : 1160,
            textAlign: esquerda ? "left" : "center",
            color: "white",
            fontSize: centro ? 150 : esquerda ? 112 : 104,
            fontWeight: 900,
            lineHeight: 1.0,
            textTransform: "uppercase",
            letterSpacing: -1,
            WebkitTextStroke: centro ? "5px #000" : "3px #000",
            paintOrder: "stroke fill",
            textShadow: "0 8px 24px rgba(0,0,0,0.7)",
          }}
        >
          {palavras.map((p, i) => (
            <span
              key={i}
              style={{
                display: "inline-block",
                // pontuação logo depois (ex.: o "?" após o destaque) encosta na palavra
                margin: `0 ${/^[?!.,:;…]+$/.test(palavras[i + 1]?.texto ?? "") ? "0.04em" : "0.18em"} 0.12em 0`,
                padding: p.destaque ? "0 0.12em" : undefined,
                backgroundColor: p.destaque ? corDestaque : undefined,
                color: p.destaque ? "#111" : undefined,
                WebkitTextStroke: p.destaque ? "0px" : undefined,
                textShadow: p.destaque ? "none" : undefined,
                rotate: p.destaque ? "-2deg" : undefined,
              }}
            >
              {p.texto}
            </span>
          ))}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

function dividir(texto: string, destaque?: string): { texto: string; destaque: boolean }[] {
  const palavras = (s: string, marcado: boolean) => s.split(/\s+/).filter(Boolean).map((t) => ({ texto: t, destaque: marcado }));
  const i = destaque ? texto.toLowerCase().indexOf(destaque.toLowerCase()) : -1;
  if (!destaque || i < 0) return palavras(texto, false);
  return [
    ...palavras(texto.slice(0, i), false),
    // o destaque vira um bloco só, para a faixa não se partir entre as palavras
    { texto: texto.slice(i, i + destaque.length), destaque: true },
    ...palavras(texto.slice(i + destaque.length), false),
  ];
}
