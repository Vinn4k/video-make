"""[5] Mídia: escolhe uma foto ou um vídeo para cada cena.

1. Junta candidatos dos bancos de imagem (Pexels, Pixabay, Wikimedia).
2. Com o ComfyUI no ar, o Qwen3-VL dá uma nota de 0 a 10 para cada candidato e fica o melhor.
3. Se nenhum passar da nota mínima (ou a cena pedir "ia"), gera a imagem no Z-Image Turbo.
Sem ComfyUI, fica o primeiro candidato encontrado.
"""

import hashlib
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import comfy
from .util import ler_json, log, rodar, salvar_json

AGENTE = {"User-Agent": "video-make/0.1 (gerador de documentarios; uso pessoal)"}
INTERVALO = {"commons.wikimedia.org": 1.0, "upload.wikimedia.org": 1.0}  # segundos entre pedidos
_ultimo_pedido: dict[str, float] = {}
COM_MIDIA = {"midia", "numero_destaque", "split_topicos", "manchete"}
MODELO_IMAGEM = "z_image_turbo_bf16.safetensors"
# só o que deve aparecer: o Z-Image desenha o que é citado, até numa negação ("no text" traz letreiro)
ESTILO_IA = ", realistic documentary photograph, natural colors, high detail, clean blank surfaces"


def _get(url: str, **kwargs) -> requests.Response:
    """GET com espera entre pedidos ao mesmo site e nova tentativa quando o site pede calma (429/5xx)."""
    host = urlparse(url).netloc
    kwargs.setdefault("timeout", 60)
    kwargs["headers"] = {**AGENTE, **kwargs.get("headers", {})}
    for tentativa in range(6):
        espera = INTERVALO.get(host, 0) - (time.monotonic() - _ultimo_pedido.get(host, 0))
        if espera > 0:
            time.sleep(espera)
        _ultimo_pedido[host] = time.monotonic()
        r = requests.get(url, **kwargs)
        if r.status_code != 429 and r.status_code < 500:
            return r
        r.close()
        time.sleep(float(r.headers.get("retry-after") or 2 ** tentativa))
    return r


def gerar(config: dict, projeto: Path) -> list[dict]:
    cenas = ler_json(projeto / "cenas.json")
    pasta = projeto / "media"
    pasta.mkdir(exist_ok=True)
    creditos_arq = projeto / "creditos.json"
    creditos = ler_json(creditos_arq) if creditos_arq.exists() else {}
    c = config["midia"]
    provedores = [p for p in c["provedores"] if _disponivel(p)]

    # cada alvo é um lugar que precisa de mídia: a cena ou uma etapa de fluxo
    alvos = []
    for cena in cenas:
        if cena["tipo"] in COM_MIDIA:
            alvos.append((f"cena_{cena['id']:03d}", cena, cena["texto"]))
        if cena["tipo"] == "fluxo":
            for j, etapa in enumerate(cena["fluxo"]["etapas"], start=1):
                alvos.append((f"cena_{cena['id']:03d}_e{j}", etapa, cena["texto"]))
    usados = {a["midia"]["origem_id"] for _, a, _ in alvos if a.get("midia")}
    # mídias recusadas na revisão nunca voltam, mesmo depois de apagadas
    rejeitadas_arq = projeto / "midia_rejeitadas.json"
    if rejeitadas_arq.exists():
        usados |= set(ler_json(rejeitadas_arq))
    lugar = config.get("projeto", {}).get("lugar", "")

    ligado = comfy.online()
    visao = ligado and c["visao"]
    gerar_ia = ligado and c["gerar_imagem"] and MODELO_IMAGEM in comfy.opcoes("UNETLoader", "unet_name")
    log(f"Mídia via {', '.join(provedores)}"
        + ("; escolha por visão (Qwen3-VL)" if visao else "")
        + ("; imagens de IA (Z-Image) quando faltar" if gerar_ia else ""))

    geradas, sem = 0, 0
    for nome, alvo, narracao in alvos:
        if alvo.get("midia") and (projeto / alvo["midia"]["src"]).exists():
            continue
        escolhido = None
        if alvo.get("preferencia") != "ia":
            candidatos = _candidatos(alvo, provedores, usados, c["candidatos"])
            if visao and candidatos:
                for cand in candidatos:
                    cand.update(_avaliar(cand, alvo, narracao, pasta, lugar))
                melhor = max(candidatos, key=lambda x: x["nota"])
                if melhor["nota"] >= c["nota_minima"] or not gerar_ia:
                    escolhido = melhor
            elif candidatos:
                escolhido = candidatos[0]

        if escolhido:
            destino = pasta / f"{nome}{'.mp4' if escolhido['tipo'] == 'video' else '.jpg'}"
            _baixar(escolhido["url"], destino)
            usados.add(escolhido["origem_id"])
        elif gerar_ia and (alvo.get("prompt_imagem") or alvo.get("visual")):
            destino = pasta / f"{nome}.jpg"
            escolhido = _gerar_imagem(alvo, destino)
            geradas += 1
        else:
            alvo["midia"] = None
            sem += 1
            continue

        alvo["midia"] = {"tipo": escolhido["tipo"], "src": f"media/{destino.name}", "origem_id": escolhido["origem_id"],
                         "nota": escolhido.get("nota"), "descricao": escolhido.get("descricao")}
        creditos[destino.name] = {k: escolhido[k] for k in ("origem_id", "pagina", "autor", "licenca")}
        salvar_json(projeto / "cenas.json", cenas)
        salvar_json(creditos_arq, creditos)
        nota = f"(nota {escolhido['nota']})" if escolhido.get("nota") is not None else ""
        log(f"{nome}: {escolhido['origem_id']} {nota}".rstrip())

    salvar_json(projeto / "cenas.json", cenas)
    log(f"Mídia: {len(alvos) - sem}/{len(alvos)} com imagem ou vídeo"
        + (f", {geradas} gerada(s) por IA" if geradas else "")
        + (f" ({sem} sem resultado ficam com fundo animado)" if sem else ""))
    return cenas


def _candidatos(alvo: dict, provedores: list[str], usados: set, n: int) -> list[dict]:
    desejado = "video" if alvo.get("preferencia") == "video" else "imagem"
    vistos, lista = set(usados), []
    for busca in alvo.get("busca", []):
        for nome in _ordem(provedores, alvo.get("preferencia")):
            # pede bem mais que n: cenas com a mesma busca esgotam os primeiros resultados e caíam na Wikimedia (lenta)
            for cand in sorted(PROVEDORES[nome](busca, max(n, 15)), key=lambda x: x["tipo"] != desejado):
                if cand["origem_id"] not in vistos:
                    vistos.add(cand["origem_id"])
                    lista.append(cand)
            if len(lista) >= n:
                return lista[:n]
    return lista


def _avaliar(cand: dict, alvo: dict, narracao: str, pasta: Path, lugar: str = "") -> dict:
    """Pede ao Qwen3-VL uma nota de 0 a 10 para o quanto o candidato serve à cena."""
    previa, normalizada = pasta / ".previa", pasta / ".previa.jpg"
    try:
        _baixar(cand["previa"], previa)
        # JPEG pequeno: o LoadImage do ComfyUI não lê todo formato e a visão não precisa de mais
        rodar(["ffmpeg", "-y", "-v", "error", "-i", str(previa), "-vf", "scale=768:-2", "-frames:v", "1", str(normalizada)])
        comfy.enviar(normalizada, "video-make-candidato.jpg")
        pergunta = (
            "You are choosing B-roll for a documentary narrated in Portuguese.\n"
            f"Narration of this scene: \"{narracao}\"\n"
            f"The image should show: {alvo.get('visual', '')}. {alvo.get('prompt_imagem', '')}\n"
            "Look at the image and reply ONLY with JSON: "
            "{\"descricao\": \"what the image shows, max 12 words\", \"nota\": integer 0-10}. "
            "10 = shows exactly what the scene needs; 5 = loosely related; 0 = unrelated or misleading. "
            "Lower the score for watermarks, big text, logos, collages, diagrams or low quality."
        )
        if lugar:
            pergunta += (f"\nThe documentary takes place in {lugar}. Give at most 3 when the image clearly shows another "
                         "country: signs or text in a foreign language, foreign landmarks or vehicles, left-hand traffic, snow.")
        resposta = comfy.rodar("visao_qwen3vl", {"image": "video-make-candidato.jpg", "prompt": pergunta}, timeout=180)
        nota = re.search(r'"nota"\s*:\s*(\d+)', resposta)
        descricao = re.search(r'"descricao"\s*:\s*"([^"]*)"', resposta)
        return {"nota": min(10, int(nota.group(1))) if nota else 0,
                "descricao": descricao.group(1) if descricao else resposta[:80]}
    except (requests.RequestException, comfy.ComfyErro, RuntimeError) as erro:
        return {"nota": 0, "descricao": f"não avaliado: {erro}"[:120]}


def _gerar_imagem(alvo: dict, destino: Path) -> dict:
    prompt = (alvo.get("prompt_imagem") or alvo["visual"]) + ESTILO_IA
    semente = int(hashlib.sha1(prompt.encode()).hexdigest()[:8], 16)
    bruto = comfy.rodar("imagem_zimage", {"prompt": prompt, "seed": semente, "width": 1920, "height": 1088},
                        destino.with_name(destino.stem + ".bruto"), timeout=600)
    rodar(["ffmpeg", "-y", "-v", "error", "-i", str(bruto),
           "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080", "-q:v", "2", str(destino)])
    bruto.unlink()
    return {"tipo": "imagem", "origem_id": f"ia-zimage-{semente}", "pagina": "",
            "autor": "gerada por IA (Z-Image Turbo, local)", "licenca": "imagem sintética", "descricao": prompt[:80]}


def _disponivel(nome: str) -> bool:
    return nome == "wikimedia" or bool(os.environ.get(f"{nome.upper()}_API_KEY"))


def _ordem(provedores: list[str], preferencia: str | None) -> list[str]:
    # Wikimedia quase só tem fotos; quando a cena pede vídeo, ela fica por último
    if preferencia == "video":
        return sorted(provedores, key=lambda p: p == "wikimedia")
    return provedores


def _baixar(url: str, destino: Path) -> None:
    with _get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for parte in r.iter_content(1 << 16):
                f.write(parte)


# ---------- provedores ----------
# Cada um devolve candidatos: {tipo, url, previa, origem_id, pagina, autor, licenca}

def _pexels(busca: str, n: int) -> list[dict]:
    cab = {"Authorization": os.environ["PEXELS_API_KEY"]}
    resultados = []
    r = _get("https://api.pexels.com/videos/search", headers=cab, timeout=30,
             params={"query": busca, "orientation": "landscape", "per_page": n})
    if r.ok:
        for v in r.json().get("videos", []):
            arquivos = [a for a in v["video_files"] if a.get("width") and 1280 <= a["width"] <= 1920]
            if arquivos and v.get("duration", 0) >= 4:
                # o menor entre 1280 e 1920: download bem menor; o clipe é fundo de cena e o render escala
                melhor = min(arquivos, key=lambda a: a["width"])
                resultados.append({"tipo": "video", "url": melhor["link"], "previa": v["image"],
                                   "origem_id": f"pexels-v{v['id']}", "pagina": v["url"], "autor": v["user"]["name"],
                                   "licenca": "Pexels License"})
    r = _get("https://api.pexels.com/v1/search", headers=cab, timeout=30,
             params={"query": busca, "orientation": "landscape", "per_page": n})
    if r.ok:
        for f in r.json().get("photos", []):
            resultados.append({"tipo": "imagem", "url": f["src"]["large2x"], "previa": f["src"]["medium"],
                               "origem_id": f"pexels-f{f['id']}", "pagina": f["url"], "autor": f["photographer"],
                               "licenca": "Pexels License"})
    return resultados


def _pixabay(busca: str, n: int) -> list[dict]:
    chave = os.environ["PIXABAY_API_KEY"]
    resultados = []
    r = _get("https://pixabay.com/api/videos/", timeout=30, params={"key": chave, "q": busca, "per_page": max(3, n)})
    if r.ok:
        for v in r.json().get("hits", []):
            arquivo = v["videos"].get("medium") or v["videos"].get("large")  # medium é 1280: download menor
            if arquivo and arquivo.get("url") and arquivo.get("width", 0) >= 1280:
                resultados.append({"tipo": "video", "url": arquivo["url"], "previa": arquivo.get("thumbnail") or "",
                                   "origem_id": f"pixabay-v{v['id']}", "pagina": v["pageURL"], "autor": v["user"],
                                   "licenca": "Pixabay Content License"})
    r = _get("https://pixabay.com/api/", timeout=30,
             params={"key": chave, "q": busca, "image_type": "photo", "orientation": "horizontal",
                     "min_width": 1600, "per_page": max(3, n)})
    if r.ok:
        for f in r.json().get("hits", []):
            resultados.append({"tipo": "imagem", "url": f["largeImageURL"], "previa": f["webformatURL"],
                               "origem_id": f"pixabay-f{f['id']}", "pagina": f["pageURL"], "autor": f["user"],
                               "licenca": "Pixabay Content License"})
    return resultados


def _wikimedia(busca: str, n: int) -> list[dict]:
    r = _get("https://commons.wikimedia.org/w/api.php", timeout=30, params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": f"{busca} filetype:bitmap", "gsrlimit": n * 2, "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1920,
    })
    if not r.ok:
        return []
    paginas = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    resultados = []
    for p in paginas:
        info = (p.get("imageinfo") or [{}])[0]
        largura, altura = info.get("width", 0), info.get("height", 1)
        if info.get("mime") != "image/jpeg" or largura < 1200 or largura / altura < 1.2:
            continue
        meta = info.get("extmetadata", {})
        autor = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
        url = info.get("thumburl") or info["url"]
        resultados.append({"tipo": "imagem", "url": url, "previa": url.replace("/1920px-", "/960px-"),
                           "origem_id": f"wikimedia-{p['pageid']}", "pagina": info.get("descriptionurl"),
                           "autor": autor or "desconhecido",
                           "licenca": meta.get("LicenseShortName", {}).get("value", "ver página")})
        if len(resultados) >= n:
            break
    return resultados


PROVEDORES = {"pexels": _pexels, "pixabay": _pixabay, "wikimedia": _wikimedia}
