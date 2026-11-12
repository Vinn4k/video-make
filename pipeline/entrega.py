"""Pasta publicar/: os arquivos prontos para subir, com o título no nome e numerados na ordem de postagem.

  publicar/1 - Vídeo - <título A>.mp4          (+ thumb A/B/C, legendas.srt e o texto do youtube.txt)
  publicar/2 - Short - <título do short_01>.mp4 (+ capa A/B e o texto para colar)
  publicar/3 - Short - …

Os arquivos são hardlinks dos originais (não ocupam espaço a mais); a pasta é refeita a cada etapa
de publicação ou de Shorts, então não edite nada dentro dela.
"""

import os
import re
import shutil
from pathlib import Path

from .util import ler_json, log

PASTA = "publicar"


def organizar(projeto: Path) -> None:
    destino = projeto / PASTA
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir()
    ordem = 1

    pub = projeto / "publicacao.json"
    video = projeto / "video_final.mp4"
    if video.exists():
        titulo = ler_json(pub)["titulos"][0] if pub.exists() else ler_json(projeto / "roteiro.json")["titulo"]
        base = f"{ordem} - Vídeo - {_nome(titulo)}"
        _ligar(video, destino / f"{base}.mp4")
        for letra in "ABC":
            _ligar(projeto / "thumbs" / f"thumb_{letra}.png", destino / f"{base} - thumb {letra}.png")
        _ligar(projeto / "legendas.srt", destino / f"{base} - legendas.srt")
        _ligar(projeto / "youtube.txt", destino / f"{base} - texto.txt")
        ordem += 1

    arquivo = projeto / "shorts.json"
    if arquivo.exists():
        pasta = projeto / "shorts"
        textos = _blocos(pasta / "shorts.txt")
        for n, short in enumerate(ler_json(arquivo)["shorts"], start=1):
            if not (pasta / f"short_{n:02d}.mp4").exists():
                continue
            base = f"{ordem} - Short - {_nome(short['titulo'])}"
            _ligar(pasta / f"short_{n:02d}.mp4", destino / f"{base}.mp4")
            for letra in "AB":
                _ligar(pasta / f"short_{n:02d}_capa_{letra}.jpg", destino / f"{base} - capa {letra}.jpg")
            if n in textos:
                (destino / f"{base} - texto.txt").write_text(textos[n])
            ordem += 1
    log(f"Prontos para subir, na ordem de postagem: {destino.relative_to(projeto.parent.parent)}/ ({ordem - 1} itens)")


def _nome(titulo: str) -> str:
    """Título como nome de arquivo: sem caracteres que Windows, nuvens e pendrives recusam."""
    nome = re.sub(r'[\\/:*?"<>|]+', "", titulo)
    nome = re.sub(r"\s+", " ", nome).strip(" .")
    return nome[:120]


def _ligar(origem: Path, destino: Path) -> None:
    if not origem.exists():
        return
    try:
        os.link(origem, destino)
    except OSError:  # outro disco ou sistema de arquivos sem hardlink
        shutil.copy2(origem, destino)


def _blocos(arquivo: Path) -> dict[int, str]:
    """Texto de cada Short no shorts.txt (título, descrição e hashtags), separado por número."""
    if not arquivo.exists():
        return {}
    blocos = {}
    for bloco in arquivo.read_text().split("\n\n"):
        m = re.match(r"SHORT (\d+):", bloco)
        if m:
            linhas = bloco.splitlines()
            # só o que vai para a rede social: do título em diante
            inicio = next((i for i, l in enumerate(linhas) if l.startswith("Título:")), 0)
            blocos[int(m.group(1))] = "\n".join(linhas[inicio:]).strip() + "\n"
    return blocos
