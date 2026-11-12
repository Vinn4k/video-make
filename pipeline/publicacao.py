"""[7] Publicação: 3 títulos e 3 thumbnails para o teste A/B/C do YouTube, mais descrição e tags.

Saídas em projetos/<slug>/: publicacao.json, thumbs/thumb_A.png (B, C) e o youtube.txt atualizado.
"""

import json
import subprocess
from pathlib import Path

from . import comfy, entrega, llm, montagem, roteiro as rot
from .midia import ESTILO_IA, MODELO_IMAGEM
from .util import PROMPTS, RENDER, extrair_json, ler_json, log, preencher, rodar, salvar_json


def gerar(config: dict, projeto: Path) -> dict:
    cenas = ler_json(projeto / "cenas.json")
    saida = projeto / "publicacao.json"
    if not saida.exists():
        roteiro = ler_json(projeto / "roteiro.json")
        imagens = "\n".join(
            json.dumps({"cena": c["id"], "mostra": c["midia"].get("descricao") or c.get("visual", "")}, ensure_ascii=False)
            for c in cenas if c.get("midia") and c["midia"]["tipo"] == "imagem")
        texto = f"# {roteiro['titulo']}\n\n" + rot.narracao(roteiro)
        prompt = preencher((PROMPTS / "publicacao.md").read_text(), roteiro=texto, imagens=imagens)
        resposta = llm.gerar(config, prompt, projeto=projeto, etapa="7_publicacao", saida=saida)
        salvar_json(saida, extrair_json(resposta))
    dados = ler_json(saida)

    pasta = projeto / "thumbs"
    pasta.mkdir(exist_ok=True)
    por_id = {c["id"]: c for c in cenas}
    gerar_ia = comfy.online() and MODELO_IMAGEM in comfy.opcoes("UNETLoader", "unet_name")
    for letra, thumb in zip("ABC", dados["thumbs"]):
        imagem = _imagem(thumb, por_id, pasta, letra, gerar_ia)
        props = {
            "imagem": str(imagem.relative_to(projeto)), "texto": thumb["texto"], "destaque": thumb.get("destaque", ""),
            "selo": thumb.get("selo", ""), "layout": thumb.get("layout", "esquerda"),
            "corDestaque": config["visual"]["cor_destaque"], "corFundo": config["visual"]["cor_fundo"],
        }
        arquivo_props = pasta / f"thumb_{letra}.props.json"
        salvar_json(arquivo_props, props)
        subprocess.run(["npx", "remotion", "still", "src/index.ts", "Thumbnail", str(pasta / f"thumb_{letra}.png"),
                        f"--props={arquivo_props}", f"--public-dir={projeto}", "--log=error"], cwd=RENDER, check=True)
        log(f"Thumb {letra}: \"{thumb['texto']}\" → thumbs/thumb_{letra}.png")

    montagem.descricao(projeto, cenas)
    for letra, titulo in zip("ABC", dados["titulos"]):
        log(f"Título {letra}: {titulo}")
    entrega.organizar(projeto)
    return dados


def _imagem(thumb: dict, por_id: dict, pasta: Path, letra: str, gerar_ia: bool) -> Path:
    """Imagem de fundo da thumb: um arquivo escolhido à mão, gerada por IA se houver prompt e ComfyUI,
    senão a imagem da cena indicada."""
    if thumb.get("arquivo"):  # ex.: quadro recortado de um vídeo em pé, que na cena vem com laterais desfocadas
        return pasta.parent / thumb["arquivo"]
    if thumb.get("prompt_imagem") and gerar_ia:
        destino = pasta / f"fundo_{letra}.jpg"
        if not destino.exists():
            bruto = comfy.rodar("imagem_zimage", {"prompt": thumb["prompt_imagem"] + ESTILO_IA, "seed": ord(letra),
                                                  "width": 1280, "height": 720}, pasta / f"fundo_{letra}.bruto")
            rodar(["ffmpeg", "-y", "-v", "error", "-i", str(bruto), "-q:v", "2", str(destino)])
            bruto.unlink()
        return destino
    cena = por_id.get(thumb.get("cena"))
    midia = cena.get("midia") if cena else None
    if not midia:  # cena sem imagem: usa a primeira cena que tenha
        midia = next(c["midia"] for c in por_id.values() if c.get("midia") and c["midia"]["tipo"] == "imagem")
    origem = pasta.parent / midia["src"]
    if midia["tipo"] == "video":  # quadro do meio do clipe
        destino = pasta / f"fundo_{letra}.jpg"
        rodar(["ffmpeg", "-y", "-v", "error", "-ss", "2", "-i", str(origem), "-frames:v", "1", "-q:v", "2", str(destino)])
        return destino
    return origem
