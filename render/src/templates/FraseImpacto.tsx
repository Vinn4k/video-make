import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { fontFamily } from "../fonte";
import { Estilo, Frase } from "../tipos";

const entrada = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) } as const;
const ATRASO = 3; // quadros entre uma palavra e a próxima
const INICIO = 8;

// Tela escura com a frase entrando palavra por palavra e o trecho de destaque marcado na cor do canal.
export const FraseImpacto: React.FC<{ frase: Frase; estilo: Estilo; duracao: number }> = ({ frase, estilo, duracao }) => {
  const frame = useCurrentFrame();
  const palavras = dividir(frase.texto, frase.destaque);
  const fimPalavras = INICIO + palavras.length * ATRASO;
  // a marca percorre as palavras de destaque uma após a outra
  const marcadas = palavras.filter((p) => p.destaque).length;
  let ordemMarca = 0;

  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        background: `radial-gradient(ellipse 60% 70% at ${interpolate(frame, [0, duracao], [20, 32])}% 75%, ${estilo.corDestaque}26 0%, ${estilo.corFundo}00 100%), ${estilo.corFundo}`,
      }}
    >
      <AbsoluteFill style={{ justifyContent: "center", padding: "0 180px", fontFamily }}>
        {frase.rotulo && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 20,
              marginBottom: 36,
              color: estilo.corDestaque,
              fontSize: 34,
              fontWeight: 800,
              letterSpacing: 6,
              textTransform: "uppercase",
              opacity: interpolate(frame, [0, 12], [0, 1], entrada),
            }}
          >
            <div style={{ height: 6, backgroundColor: estilo.corDestaque, width: interpolate(frame, [0, 18], [0, 70], entrada) }} />
            {frase.rotulo}
          </div>
        )}
        <div style={{ color: estilo.corTexto, fontSize: 104, fontWeight: 900, lineHeight: 1.2, textTransform: "uppercase", maxWidth: 1560 }}>
          {palavras.map((p, i) => {
            const surge = INICIO + i * ATRASO;
            let marca = 0;
            if (p.destaque) {
              const inicioMarca = fimPalavras + (ordemMarca * 12) / Math.max(1, marcadas);
              marca = interpolate(frame, [inicioMarca, inicioMarca + 10], [0, 100], entrada);
              ordemMarca++;
            }
            // palavras de destaque vizinhas encostam, formando uma faixa contínua
            const encosta = p.destaque && palavras[i + 1]?.destaque;
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  marginRight: encosta ? 0 : "0.28em",
                  padding: p.destaque ? "0 0.12em" : undefined,
                  color: marca > 55 ? estilo.corFundo : undefined,
                  background: p.destaque ? `linear-gradient(${estilo.corDestaque}, ${estilo.corDestaque}) no-repeat left / ${marca}% 100%` : undefined,
                  opacity: interpolate(frame, [surge, surge + 10], [0, 1], entrada),
                  translate: interpolate(frame, [surge, surge + 14], ["0px 40px", "0px 0px"], entrada),
                }}
              >
                {p.texto}
              </span>
            );
          })}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

function dividir(texto: string, destaque?: string): { texto: string; destaque: boolean }[] {
  const palavras = (s: string, marcado: boolean) => s.split(/\s+/).filter(Boolean).map((t) => ({ texto: t, destaque: marcado }));
  const i = destaque ? texto.toLowerCase().indexOf(destaque.toLowerCase()) : -1;
  if (!destaque || i < 0) return palavras(texto, false);
  const marcadas = palavras(texto.slice(i, i + destaque.length), true);
  const depois = palavras(texto.slice(i + destaque.length), false);
  // pontuação colada ao destaque ("acumulando?") fica junto da última palavra marcada
  if (depois.length && marcadas.length && /^\S/.test(texto.slice(i + destaque.length))) {
    marcadas[marcadas.length - 1].texto += depois.shift()!.texto;
  }
  return [...palavras(texto.slice(0, i), false), ...marcadas, ...depois];
}
