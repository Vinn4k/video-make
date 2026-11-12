"""[3] Decupagem: divide o roteiro em cenas e define o visual de cada uma."""

import difflib
from pathlib import Path

from . import llm, referencia, roteiro as rot
from .util import PROMPTS, e_programa, extrair_json, ler_json, log, preencher, salvar_json


# os bancos de imagem devolvem o que têm de mais popular (metrô de Istambul, neve, placas em inglês) quando a busca não diz onde
LUGAR = """## Lugar

A história se passa em **{lugar}**. Em toda cena que mostra o lugar (ruas, transporte, obras, prédios, pessoas, paisagem), a primeira `busca` leva o nome da cidade ou do país (ex.: "São Paulo metro platform", "Brazil highway trucks") e nenhuma busca pede algo típico de outro país. O `prompt_imagem` dessas cenas também cita o lugar. Cenas genéricas (máquinas, documentos, close de objetos) dispensam o nome."""


PROGRAMA = """## Formato: programa de TV

O vídeo é um programa: o capítulo 1 é a abertura e os seguintes são os blocos, cada um com uma placa própria antes dele (o código põe a placa e a vinheta; você não precisa de cena para elas).
- **Escalada:** no capítulo 1, cada frase que anuncia um momento do programa ("Neste programa…", "E a rodovia que…") vira uma cena `midia` própria com `"overlay": {"tipo": "escalada", "titulo": "até 6 palavras"}`. O título resume o item como manchete ("A estação a 47 metros"). Use a imagem mais forte daquele assunto, a mesma que vai aparecer no bloco.
- **Sem `titulo_capitulo`:** a placa do bloco já mostra o nome. O resto (templates, ritmo, `lower_third`) segue igual.
"""


def gerar(config: dict, projeto: Path) -> list[dict]:
    saida = projeto / "cenas.json"
    if saida.exists():
        return ler_json(saida)
    roteiro = ler_json(projeto / "roteiro.json")
    texto = "\n\n".join(f"## Capítulo {i}: {c['titulo']}\n\n{c['texto']}"
                        for i, c in enumerate(roteiro["capitulos"], start=1))
    lugar = config.get("projeto", {}).get("lugar", "")
    prompt = preencher((PROMPTS / "decupagem.md").read_text(), roteiro=texto, lugar=LUGAR.format(lugar=lugar) if lugar else "",
                       formato=PROGRAMA if e_programa(config) else "")
    resposta = llm.gerar(config, prompt, projeto=projeto, etapa="3_decupagem", saida=saida)
    cenas = extrair_json(resposta)["cenas"]
    cenas = _validar(cenas, roteiro, e_programa(config))
    salvar_json(saida, cenas)
    tipos = {}
    for c in cenas:
        tipos[c["tipo"]] = tipos.get(c["tipo"], 0) + 1
    log(f"{len(cenas)} cenas: " + ", ".join(f"{n} {t}" for t, n in tipos.items()))
    return cenas


def _validar(cenas: list[dict], roteiro: dict, programa: bool = False) -> list[dict]:
    original = referencia._palavras(rot.narracao(roteiro))
    decupado = referencia._palavras(" ".join(c["texto"] for c in cenas))
    cobertura = difflib.SequenceMatcher(None, original, decupado, autojunk=False).ratio()
    if cobertura < 0.98:
        raise RuntimeError(f"As cenas não reproduzem o roteiro fielmente (semelhança {cobertura:.1%}). "
                           "Gere a decupagem de novo.")

    capitulos_vistos = set()
    for i, cena in enumerate(cenas, start=1):
        cena["id"] = i
        cena.setdefault("overlay", None)
        cena.setdefault("busca", [])
        cena["cta"] = bool(cena.get("cta"))
        if cena["tipo"] != "midia":
            cena["overlay"] = None
        if cena["overlay"] and cena["overlay"].get("tipo") == "escalada" and not cena["overlay"].get("titulo"):
            cena["overlay"] = None
        problema = _checar_template(cena)
        if problema:
            log(f"Cena {i}: {cena['tipo']} inválido ({problema}); vira cena de mídia")
            cena["tipo"] = "midia"
        if cena["tipo"] == "frase_impacto" and \
                cena["frase"].get("destaque", "").lower() not in cena["frase"]["texto"].lower():
            cena["frase"]["destaque"] = ""
        primeira_do_capitulo = cena["capitulo"] not in capitulos_vistos
        capitulos_vistos.add(cena["capitulo"])
        if programa:
            # a abertura entra a frio e cada bloco já tem a placa antes dele: sem título por cima da mídia
            if cena["overlay"] and cena["overlay"].get("tipo") == "titulo_capitulo":
                cena["overlay"] = None
            continue
        if primeira_do_capitulo and cena["tipo"] == "midia":
            overlay = cena["overlay"] or {}
            if overlay.get("tipo") != "titulo_capitulo":
                cena["overlay"] = {"tipo": "titulo_capitulo",
                                   "titulo": roteiro["capitulos"][cena["capitulo"] - 1]["titulo"]}
        if cena["overlay"] and cena["overlay"].get("tipo") == "titulo_capitulo":
            cena["overlay"]["numero"] = cena["capitulo"]
    return cenas


def _checar_template(cena: dict) -> str | None:
    """Devolve o que falta nos dados do template, ou None se estiver tudo certo."""
    tipo = cena["tipo"]
    if tipo == "midia":
        return None
    dados = cena.get({"frase_impacto": "frase", "grafico": "grafico", "numero_destaque": "numero",
                      "split_topicos": "split", "fluxo": "fluxo", "manchete": "manchete"}.get(tipo, "?")) or {}
    if tipo == "frase_impacto":
        return None if dados.get("texto") else "sem texto"
    if tipo == "grafico":
        pontos = dados.get("pontos") or []
        if not 2 <= len(pontos) <= 6:
            return "precisa de 2 a 6 pontos"
        if not all(isinstance(p, list) and len(p) == 2 and isinstance(p[1], (int, float)) for p in pontos):
            return "pontos devem ser [rótulo, número]"
        dados.setdefault("formato", "linha")
        return None
    if tipo == "numero_destaque":
        return None if dados.get("numero") and dados.get("texto") else "sem número ou texto"
    if tipo == "split_topicos":
        return None if dados.get("titulo") and 2 <= len(dados.get("topicos") or []) <= 4 else "precisa de 2 a 4 tópicos"
    if tipo == "fluxo":
        etapas = dados.get("etapas") or []
        if not 2 <= len(etapas) <= 4 or not all(e.get("rotulo") and e.get("busca") for e in etapas):
            return "precisa de 2 a 4 etapas com rótulo e busca"
        return None
    if tipo == "manchete":
        return None if dados.get("titulo") else "sem título"
    return f"tipo desconhecido {tipo}"
