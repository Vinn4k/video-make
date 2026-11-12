"""Mídia em paralelo com a narração e prévia rápida da mídia, antes do render.

    .venv/bin/python -m pipeline.previa copiar <projeto>   # cria projetos/<projeto>-midia para rodar --so midia nela
    .venv/bin/python -m pipeline.previa juntar <projeto>   # traz a mídia escolhida na cópia de volta para o projeto
    .venv/bin/python -m pipeline.previa video <projeto>    # previa_midia.mp4: cada cena em 2x, sem narração

A busca de mídia não depende da narração (só do cenas.json), mas as duas etapas gravam o cenas.json.
Rodar a mídia numa cópia deixa as duas andarem juntas sem uma sobrescrever a outra.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .util import PROJETOS, duracao_midia, ler_json, log, salvar_json

ARQUIVOS = ["cenas.json", "projeto.json", "creditos.json", "midia_rejeitadas.json", "referencia.txt", "referencia.json",
            "roteiro.md", "roteiro.json", "similaridade.json"]
PALAVRAS_POR_SEG = 170 / 60


def copiar(projeto: Path) -> Path:
    copia = projeto.with_name(projeto.name + "-midia")
    copia.mkdir(exist_ok=True)
    for nome in ARQUIVOS + [p.name for p in projeto.glob("*.resposta")]:
        if (projeto / nome).exists():
            shutil.copy2(projeto / nome, copia / nome)
    if (projeto / "media").exists():
        shutil.copytree(projeto / "media", copia / "media", dirs_exist_ok=True)
    log(f"Cópia pronta: rode .venv/bin/python run.py --projeto {copia.name} --so midia")
    return copia


def juntar(projeto: Path) -> None:
    copia = projeto.with_name(projeto.name + "-midia")
    cenas, da_copia = ler_json(projeto / "cenas.json"), {c["id"]: c for c in ler_json(copia / "cenas.json")}
    trazidas = 0
    for cena in cenas:
        outra = da_copia.get(cena["id"])
        if not outra:
            continue
        for chave in ("midia", "fluxo", "preferencia", "busca", "prompt_imagem"):
            if chave in outra:
                cena[chave] = outra[chave]
        trazidas += bool(outra.get("midia"))
    (projeto / "media").mkdir(exist_ok=True)
    for arq in (copia / "media").iterdir():
        if arq.is_dir():  # .miniaturas da página de revisão
            continue
        if not (projeto / "media" / arq.name).exists() or arq.stat().st_mtime > (projeto / "media" / arq.name).stat().st_mtime:
            shutil.copy2(arq, projeto / "media" / arq.name)
    creditos = ler_json(projeto / "creditos.json") if (projeto / "creditos.json").exists() else {}
    creditos.update(ler_json(copia / "creditos.json") if (copia / "creditos.json").exists() else {})
    salvar_json(projeto / "creditos.json", creditos)
    for nome in ("midia_rejeitadas.json",):
        if (copia / nome).exists():
            shutil.copy2(copia / nome, projeto / nome)
    salvar_json(projeto / "cenas.json", cenas)
    log(f"Mídia de {trazidas} cenas trazida de {copia.name}")


def video(projeto: Path, velocidade: float = 2.0) -> Path:
    """Cada cena com a sua mídia pelo tempo da narração (ou estimado pelas palavras), dividido pela velocidade."""
    cenas = ler_json(projeto / "cenas.json")
    saida = projeto / "previa_midia.mp4"
    escala = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25,format=yuv420p"
    with tempfile.TemporaryDirectory() as tmp:
        lista = []
        for cena in cenas:
            seg = (cena.get("duracao") or len(cena["texto"].split()) / PALAVRAS_POR_SEG) / velocidade
            midia = cena.get("midia") or {}
            arq = projeto / midia["src"] if midia.get("src") else None
            parte = Path(tmp) / f"{cena['id']:04d}.mp4"
            if arq and arq.exists() and arq.suffix == ".mp4":
                entrada = ["-stream_loop", "-1", "-i", str(arq)] if duracao_midia(arq) < seg else ["-i", str(arq)]
            elif arq and arq.exists():
                entrada = ["-loop", "1", "-i", str(arq)]
            else:  # templates sem mídia (frase, gráfico, fluxo): tela escura
                entrada = ["-f", "lavfi", "-i", "color=c=0x0B0F14:s=1280x720"]
            subprocess.run(["ffmpeg", "-v", "error", "-y", *entrada, "-t", f"{seg:.2f}", "-vf", escala, "-an",
                            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", str(parte)], check=True)
            lista.append(f"file '{parte}'")
        (Path(tmp) / "lista.txt").write_text("\n".join(lista))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(Path(tmp) / "lista.txt"),
                        "-c", "copy", str(saida)], check=True)
    log(f"Prévia: {saida} ({duracao_midia(saida) / 60:.1f} min, {velocidade:g}x, sem narração)")
    return saida


if __name__ == "__main__":
    acao, nome = sys.argv[1], sys.argv[2]
    {"copiar": copiar, "juntar": juntar, "video": video}[acao](PROJETOS / nome)
