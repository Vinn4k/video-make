"""[0] Modo adaptação: lê a transcrição de referência, extrai a estrutura e checa cópia."""

import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

from . import llm
from .util import (ESTRUTURAS, PROMPTS, EtapaPendente, contar_palavras, extrair_json,
                   ler_json, log, preencher, rodar, salvar_json)

TEMPO = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")
LIXO = re.compile(r"\[(música|aplausos|risos|music)\]", re.I)


# ---------- entrada ----------

def importar(fonte: str, projeto: Path) -> None:
    """Copia a transcrição (arquivo ou link do YouTube) para projeto/referencia.txt."""
    destino = projeto / "referencia.txt"
    if destino.exists():
        return
    if fonte.startswith("http"):
        destino.write_text(_baixar_legenda(fonte))
    else:
        destino.write_text(Path(fonte).read_text())
    log(f"Transcrição salva em {destino.name}")


def _baixar_legenda(url: str) -> str:
    # o yt-dlp do ambiente do projeto (.venv) vale tanto quanto um instalado no sistema
    yt_dlp = shutil.which("yt-dlp") or shutil.which("yt-dlp", path=str(Path(sys.executable).parent))
    if not yt_dlp:
        raise EtapaPendente("Para usar link do YouTube instale o yt-dlp (.venv/bin/pip install yt-dlp) "
                            "ou cole a transcrição num arquivo .txt e passe o caminho.")
    with tempfile.TemporaryDirectory() as tmp:
        rodar([yt_dlp, "--skip-download", "--write-auto-subs", "--write-subs",
               "--sub-langs", "pt.*,pt", "--sub-format", "vtt", "-o", f"{tmp}/legenda", url])
        arquivos = sorted(Path(tmp).glob("*.vtt"))
        if not arquivos:
            raise RuntimeError("O vídeo não tem legenda em português disponível.")
        return _vtt_para_texto(arquivos[0].read_text())


def _vtt_para_texto(vtt: str) -> str:
    linhas, ultima = [], None
    for linha in vtt.splitlines():
        m = re.match(r"^(\d{2}):(\d{2}):(\d{2})\.\d+ -->", linha)
        if m:
            h, mi, s = map(int, m.groups())
            linhas.append(f"{h * 60 + mi}:{s:02d}" if h == 0 else f"{h}:{mi:02d}:{s:02d}")
            continue
        texto = re.sub(r"<[^>]+>", "", linha).strip()
        if texto and "-->" not in texto and not texto.startswith(("WEBVTT", "Kind:", "Language:")) and texto != ultima:
            linhas.append(texto)
            ultima = texto
    return "\n".join(linhas)


def segmentar(texto: str) -> list[dict]:
    """Transforma a transcrição copiada do YouTube (tempo numa linha, texto nas seguintes) em segmentos."""
    segmentos, atual = [], None
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        m = TEMPO.match(linha)
        if m:
            a, b, c = m.groups()
            seg = int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)
            atual = {"t": seg, "texto": ""}
            segmentos.append(atual)
        elif atual is not None:
            atual["texto"] = (atual["texto"] + " " + LIXO.sub("", linha)).strip()
    if not segmentos:  # texto puro, sem tempos
        segmentos = [{"t": 0, "texto": LIXO.sub("", texto).strip()}]
    return [s for s in segmentos if s["texto"]]


# ---------- análise ----------

def analisar(config: dict, projeto: Path) -> dict:
    saida = projeto / "referencia.json"
    if saida.exists():
        return ler_json(saida)
    segmentos = segmentar((projeto / "referencia.txt").read_text())
    texto_completo = " ".join(s["texto"] for s in segmentos)
    duracao = segmentos[-1]["t"] + 10 if len(segmentos) > 1 else contar_palavras(texto_completo) / 2.5
    prompt = preencher(
        (PROMPTS / "analise_referencia.md").read_text(),
        duracao_seg=int(duracao),
        palavras=contar_palavras(texto_completo),
        transcricao="\n".join(f"[{s['t']}] {s['texto']}" for s in segmentos),
    )
    resposta = llm.gerar(config, prompt, projeto=projeto, etapa="0_analise_referencia", saida=saida)
    analise = extrair_json(resposta)
    salvar_json(saida, analise)
    salvar_json(ESTRUTURAS / f"{projeto.name}.json", {
        "origem": projeto.name,
        "tecnicas_retencao": analise.get("tecnicas_retencao", []),
        "ctas": analise.get("ctas", []),
        "estrutura_generica": analise.get("estrutura_generica", []),
    })
    log(f"Análise salva ({len(analise.get('beats', []))} beats); molde salvo em estruturas/{projeto.name}.json")
    return analise


# ---------- checagem de similaridade ----------

def _palavras(texto: str) -> list[str]:
    texto = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", texto)


def _ngrams(palavras: list[str], n: int) -> set[tuple]:
    return {tuple(palavras[i:i + n]) for i in range(len(palavras) - n + 1)}


def similaridade(texto_novo: str, texto_ref: str, max_ngram: int) -> dict:
    novo, ref = _palavras(texto_novo), _palavras(texto_ref)
    sobreposicao = len(_ngrams(novo, 5) & _ngrams(ref, 5)) / max(1, len(_ngrams(novo, 5)))
    # trechos com mais de max_ngram palavras iguais, já unidos em passagens contínuas
    proibidos = _ngrams(ref, max_ngram + 1)
    trechos, i = [], 0
    while i <= len(novo) - (max_ngram + 1):
        if tuple(novo[i:i + max_ngram + 1]) in proibidos:
            fim = i + max_ngram + 1
            while fim < len(novo) and tuple(novo[fim - max_ngram:fim + 1]) in proibidos:
                fim += 1
            trechos.append(" ".join(novo[i:fim]))
            i = fim
        else:
            i += 1
    return {"sobreposicao_5gramas": round(sobreposicao, 4), "trechos_copiados": trechos}


def texto_referencia(projeto: Path) -> str:
    return " ".join(s["texto"] for s in segmentar((projeto / "referencia.txt").read_text()))
