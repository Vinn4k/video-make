"""[4] Narração: gera um áudio por cena e junta tudo em narracao.wav com as pausas.

Com o serviço de análise (Whisper) no ar, cada fala é conferida contra o texto: se a voz
pulou ou trocou palavras (WER alto), a cena é gerada de novo com outra semente.
"""

import base64
import difflib
import hashlib
import json
import os
import re
import shutil
import time
import unicodedata
from pathlib import Path

import requests

from . import comfy, llm
from .util import (PROMPTS, RAIZ, EtapaPendente, duracao_midia, e_programa, extrair_json, ler_json, log, preencher, rodar,
                   salvar_json)

TAXA = 48000


COM_TAGS = {"google"}  # provedores que interpretam tags como <short pause> (os outros as leriam em voz alta)
TAG = re.compile(r"<[^>]+>")


class CotaEsgotada(EtapaPendente):
    pass


def provedor(config: dict) -> str:
    escolhido = config["tts"]["provedor"]
    if escolhido != "auto":
        return escolhido
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY_GRATIS"):
        return "google"
    if comfy.online():
        return "comfyui"
    if os.environ.get("ELEVENLABS_API_KEY") and config["tts"]["elevenlabs"]["voz_id"]:
        return "elevenlabs"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if shutil.which("say"):
        if os.environ.get("COMFY_URL"):
            log(f"ComfyUI em {comfy.url()} não respondeu; usando a voz do macOS só para teste")
        return "macos"
    raise RuntimeError("Nenhum provedor de voz disponível. Ligue o ComfyUI ou configure uma chave no .env.")


def gerar(config: dict, projeto: Path) -> list[dict]:
    """Narra o vídeo inteiro com uma voz só. Com o Google, se a cota acabar, o vídeo todo vai para a reserva
    (tts.google.reserva): misturar duas vozes no mesmo vídeo soaria pior do que trocar de voz."""
    nome = provedor(config)
    conferir = _analise_online(config)
    if nome != "google":
        return _gerar_com(config, projeto, nome, conferir)
    reserva = config["tts"]["google"].get("reserva", "esperar")
    usar_reserva = reserva != "esperar" and (reserva != "comfyui" or comfy.online())
    if config["tts"]["google"].get("blocos") and not conferir:
        # cena por cena gastaria um pedido da cota por cena; sem Whisper não dá para cortar os blocos
        if usar_reserva:
            log(f"Whisper desligado: a voz do Google em blocos precisa dele; narrando com {reserva}")
            return _gerar_com(config, projeto, reserva, conferir)
        raise EtapaPendente("A voz do Google em blocos precisa do serviço de análise (Whisper); suba-o e rode de novo.")
    try:
        return _gerar_com(config, projeto, "google", conferir)
    except CotaEsgotada as aviso:
        if not usar_reserva:
            raise
        log(f"{str(aviso).splitlines()[0]}\n  Narrando o vídeo inteiro com {reserva}; "
            "os blocos do Google ficam salvos e voltam a valer se você rodar com --voz google depois")
        return _gerar_com(config, projeto, reserva, conferir)


def _gerar_com(config: dict, projeto: Path, nome: str, conferir: bool) -> list[dict]:
    cenas = ler_json(projeto / "cenas.json")
    pasta = projeto / "audio" / nome  # uma pasta por voz: trocar de voz nunca mistura áudios no cache
    pasta.mkdir(parents=True, exist_ok=True)
    log(f"Narração com {nome} ({len(cenas)} cenas)"
        + ("; conferência por Whisper ligada" if conferir else "; sem conferência (serviço de análise desligado)"))
    if nome == "comfyui":
        _garantir_referencia(config)

    pronuncia = config["tts"].get("pronuncia") or {}
    falas = _preparar_falas(config, projeto, cenas) if nome in COM_TAGS and config["tts"].get("prosodia") else {}
    em_blocos = nome == "google" and config["tts"]["google"].get("blocos")
    if em_blocos:
        _narrar_em_blocos(config, pasta, cenas, falas, pronuncia)
    for cena in [] if em_blocos else cenas:
        cena.pop("pausa_inclusa", None)
        destino = pasta / f"cena_{cena['id']:03d}.wav"
        falado = _aplicar_pronuncia(falas.get(cena["id"], cena["texto"]), pronuncia)
        assinatura = hashlib.sha1(f"{nome}|{json.dumps(config['tts'].get(nome), sort_keys=True)}|{falado}".encode()).hexdigest()
        marca = destino.with_suffix(".json")
        if destino.exists() and marca.exists() and ler_json(marca).get("assinatura") == assinatura:
            info = ler_json(marca)
        else:
            info = _sintetizar(config, nome, cena, falado, destino, conferir)
            info["assinatura"] = assinatura
            salvar_json(marca, info)
        cena["wer"] = info.get("wer")
        cena["palavras"] = info.get("palavras")

    revisar = [c for c in cenas if c.get("wer") is not None and c["wer"] > config["tts"]["conferencia"]["wer_maximo"]]
    if revisar:
        log(f"Atenção: {len(revisar)} cena(s) com fala diferente do texto mesmo após novas tentativas: "
            + ", ".join(str(c["id"]) for c in revisar) + f" (veja audio/{nome}/)")
    _montar_trilha(config, projeto, pasta, cenas)
    salvar_json(projeto / "cenas.json", cenas)
    return cenas


def _sintetizar(config: dict, nome: str, cena: dict, falado: str, destino: Path, conferir: bool) -> dict:
    """Gera a fala, tentando de novo (nas vozes que variam a cada geração) quando a conferência reprova."""
    conf = config["tts"]["conferencia"]
    tentativas = conf["tentativas"] if (conferir and nome in ("comfyui", "google")) else 0  # vozes que variam a cada geração
    melhor = None
    for tentativa in range(tentativas + 1):
        bruto = destino.with_name(f"{destino.stem}.bruto")
        arquivo = PROVEDORES[nome](config, falado, bruto, semente=cena["id"] * 100 + tentativa)
        candidato = destino.with_name(f"{destino.stem}.t{tentativa}.wav")
        # padroniza: mono, 48 kHz, sem silêncio nas pontas
        rodar(["ffmpeg", "-y", "-v", "error", "-i", str(arquivo), "-ac", "1", "-ar", str(TAXA),
               "-af", "silenceremove=start_periods=1:start_threshold=-50dB,"
                      "areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse",
               str(candidato)])
        arquivo.unlink()
        palavras = len(cena["texto"].split())
        if duracao_midia(candidato) < palavras * 0.12:
            candidato.unlink()
            raise RuntimeError(f"A voz devolveu áudio curto demais na cena {cena['id']}; confira o log do ComfyUI.")
        info = _conferir(config, candidato, cena["texto"]) if conferir else {}
        if melhor is None or (info.get("wer") or 0) < (melhor[1].get("wer") or 0):
            if melhor:
                melhor[0].unlink()
            melhor = (candidato, info)
        else:
            candidato.unlink()
        if (melhor[1].get("wer") or 0) <= conf["wer_maximo"] or tentativa == tentativas:
            break
        log(f"Cena {cena['id']}: fala com {melhor[1]['wer']:.0%} de erro, gerando de novo")
    melhor[0].replace(destino)
    return melhor[1]


def _agrupar(cenas: list[dict], max_palavras: int) -> list[list[dict]]:
    """Cenas seguidas do mesmo capítulo, até `max_palavras` por bloco (≈ 5 min a 150 palavras/min)."""
    blocos, atual, palavras = [], [], 0
    for cena in cenas:
        n = len(cena["texto"].split())
        if atual and (cena["capitulo"] != atual[-1]["capitulo"] or palavras + n > max_palavras):
            blocos.append(atual)
            atual, palavras = [], 0
        atual.append(cena)
        palavras += n
    return blocos + [atual] if atual else blocos


def _narrar_em_blocos(config: dict, pasta: Path, cenas: list[dict], falas: dict, pronuncia: dict) -> None:
    """Gemini TTS em blocos: um pedido narra várias cenas de uma vez (entonação contínua e menos cota),
    o Whisper dá o tempo de cada palavra e o áudio é cortado no começo de cada cena.

    As cenas de um bloco já carregam a pausa natural que a voz fez entre elas (`pausa_inclusa`).
    """
    c = config["tts"]["google"]
    conf = config["tts"]["conferencia"]
    blocos = _agrupar(cenas, c["max_palavras_bloco"])
    log(f"{len(blocos)} bloco(s) de até {c['max_palavras_bloco']} palavras")
    for n, bloco in enumerate(blocos, start=1):
        falados = [_aplicar_pronuncia(falas.get(x["id"], x["texto"]), pronuncia) for x in bloco]
        # só o que muda o som; o modelo fica fixo por vídeo em audio/google/modelo.txt
        assinatura = hashlib.sha1(json.dumps([c["voz"], c.get("estilo", ""), falados], ensure_ascii=False).encode()).hexdigest()
        marca = pasta / f"bloco_{n:02d}.json"
        arquivos = [pasta / f"cena_{x['id']:03d}.wav" for x in bloco]
        if marca.exists() and ler_json(marca).get("assinatura") == assinatura and all(a.exists() for a in arquivos):
            infos = ler_json(marca)["cenas"]
        else:
            for tentativa in range(c["tentativas_bloco"] + 1):
                infos = _narrar_bloco(config, pasta, n, bloco, falados)
                pior = max(i.get("wer") or 0 for i in infos.values())
                if pior <= conf["wer_maximo"] or tentativa == c["tentativas_bloco"]:
                    break
                log(f"Bloco {n}: uma cena saiu com {pior:.0%} de erro, gerando o bloco de novo")
            salvar_json(marca, {"assinatura": assinatura, "cenas": infos})
        for i, cena in enumerate(bloco):
            info = infos[str(cena["id"])]
            cena["wer"], cena["palavras"] = info.get("wer"), info.get("palavras")
            cena["pausa_inclusa"] = i < len(bloco) - 1


def _narrar_bloco(config: dict, pasta: Path, n: int, bloco: list[dict], falados: list[str]) -> dict:
    log(f"Bloco {n}: narrando {len(bloco)} cenas num pedido só…")
    wav = pasta / f"bloco_{n:02d}.wav"
    bruto = _google(config, "\n\n".join(falados), pasta / f"bloco_{n:02d}.bruto", semente=0)
    rodar(["ffmpeg", "-y", "-v", "error", "-i", str(bruto), "-ac", "1", "-ar", str(TAXA), str(wav)])
    bruto.unlink()

    # tempo de cada palavra do texto limpo; o índice da 1ª palavra de cada cena dá o ponto de corte
    r = requests.post(f"{os.environ['ANALISE_URL']}/align", timeout=900,
                      json={"path": str(wav.resolve()), "text": " ".join(x["texto"] for x in bloco), "language": "pt"})
    r.raise_for_status()
    palavras = r.json()["words"]
    primeira, i = [], 0
    for x in bloco:
        primeira.append(i)
        i += len(x["texto"].split())
    cortes = [0.0]
    for k in range(1, len(bloco)):
        inicio = palavras[primeira[k]]["startMs"] / 1000
        fim_anterior = palavras[primeira[k] - 1]["endMs"] / 1000
        cortes.append(max(fim_anterior, inicio - min(0.1, max(0.0, inicio - fim_anterior) / 2)))
    cortes.append(duracao_midia(wav))

    infos = {}
    for k, cena in enumerate(bloco):
        destino = pasta / f"cena_{cena['id']:03d}.wav"
        filtros = []
        if k == 0:
            filtros.append("silenceremove=start_periods=1:start_threshold=-50dB")
        if k == len(bloco) - 1:
            filtros.append("areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse")
        rodar(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-ss", f"{cortes[k]:.3f}", "-to", f"{cortes[k + 1]:.3f}",
               *(["-af", ",".join(filtros)] if filtros else []), str(destino)])
        infos[str(cena["id"])] = _conferir(config, destino, cena["texto"])
    return infos


def _montar_trilha(config: dict, projeto: Path, pasta: Path, cenas: list[dict]) -> None:
    """Concatena as falas com pausas e grava inicio/duracao (segundos) em cada cena."""
    lista, tempo = [], 0.0
    for i, cena in enumerate(cenas):
        fala = pasta / f"cena_{cena['id']:03d}.wav"
        proxima = cenas[i + 1] if i + 1 < len(cenas) else None
        if cena.get("pausa_inclusa"):
            pausa = 0.0  # a pausa natural da voz já está no fim do áudio da cena
        elif proxima is None:
            pausa = 1.5
        elif proxima["capitulo"] != cena["capitulo"]:
            pausa = config["tts"]["pausa_capitulo"]
        else:
            pausa = config["tts"]["pausa_cena"]
        # programa de TV: vinheta depois da abertura e placa entre os blocos, em silêncio no fim da cena
        cena.pop("interludio", None)
        if e_programa(config) and proxima is not None and proxima["capitulo"] != cena["capitulo"]:
            tipo = "vinheta" if cena["capitulo"] == 1 else "placa"
            seg = config["programa"][f"{tipo}_seg"]
            cena["interludio"] = {"tipo": tipo, "seg": seg}
            pausa = max(pausa, config["tts"]["pausa_capitulo"]) + seg
        duracao = duracao_midia(fala) + pausa
        cena["inicio"] = round(tempo, 3)
        cena["duracao"] = round(duracao, 3)
        tempo += duracao
        lista.append(f"file '{fala.name}'")
        if pausa > 0:
            silencio = pasta / f"pausa_{int(pausa * 1000)}.wav"
            if not silencio.exists():
                rodar(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={TAXA}:cl=mono",
                       "-t", str(pausa), str(silencio)])
            lista.append(f"file '{silencio.name}'")
    (pasta / "lista.txt").write_text("\n".join(lista) + "\n")
    rodar(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "lista.txt",
           "-c", "pcm_s16le", str(projeto / "narracao.wav")], cwd=pasta)
    log(f"Narração total: {tempo / 60:.1f} min")


def _preparar_falas(config: dict, projeto: Path, cenas: list[dict]) -> dict[int, str]:
    """Versão "falada" de cada cena, com tags, pausas e ênfases, gerada pelo LLM (prompts/prosodia.md).

    Só vale se as palavras forem as mesmas do texto: senão a cena usa o texto original.
    """
    saida = projeto / "falas.json"
    if not saida.exists():
        lista = "\n".join(json.dumps({"id": c["id"], "texto": c["texto"]}, ensure_ascii=False) for c in cenas)
        prompt = preencher((PROMPTS / "prosodia.md").read_text(), cenas=lista)
        resposta = llm.gerar(config, prompt, projeto=projeto, etapa="4_prosodia", saida=saida)
        salvar_json(saida, extrair_json(resposta))
    falas = {f["id"]: f["fala"] for f in ler_json(saida)["falas"]}
    textos = {c["id"]: c["texto"] for c in cenas}
    validas = {i: f for i, f in falas.items() if i in textos and _tokens(TAG.sub(" ", f)) == _tokens(textos[i])}
    if len(validas) < len(falas):
        log(f"Prosódia: {len(falas) - len(validas)} cena(s) mudaram palavras e vão com o texto original")
    return _limitar_respiracao(config, cenas, validas)


def _limitar_respiracao(config: dict, cenas: list[dict], falas: dict[int, str]) -> dict[int, str]:
    """Tira os <breath> que vierem a menos de `tts.palavras_entre_respiracoes` palavras do anterior.

    O público reclamou de respiração demais (05/11/2026: 68 em 20 min no vídeo de Gizé); o padrão de
    170 palavras dá no máximo uma por minuto de fala.
    """
    minimo = config["tts"].get("palavras_entre_respiracoes", 170)
    saida, desde, tiradas = {}, minimo, 0
    for cena in cenas:
        fala = falas.get(cena["id"])
        if fala and "<breath>" in fala:
            if desde < minimo:
                fala = re.sub(r"\s*<breath>\s*", " ", fala).strip()
                tiradas += 1
            else:
                desde = 0
        if fala:
            saida[cena["id"]] = fala
        desde += len(cena["texto"].split())
    if tiradas:
        log(f"Prosódia: {tiradas} respiração(ões) a menos de {minimo} palavras da anterior foram tiradas")
    return saida


def _aplicar_pronuncia(texto: str, pronuncia: dict) -> str:
    """Troca palavras pela grafia que a voz pronuncia certo (ex.: "Stanford" → "Stênford"). A legenda não muda."""
    for original, falado in pronuncia.items():
        texto = re.sub(rf"\b{re.escape(original)}\b", falado, texto, flags=re.I)
    return texto


# ---------- conferência por Whisper (serviço HTTP de análise; contrato no README) ----------

def _analise_online(config: dict) -> bool:
    endereco = os.environ.get("ANALISE_URL", "")
    if not endereco or not config["tts"]["conferencia"]["ativa"]:
        return False
    try:
        return requests.get(f"{endereco}/health", timeout=3).ok
    except requests.RequestException:
        return False


def _conferir(config: dict, wav: Path, texto: str) -> dict:
    """Pede ao Whisper o tempo de cada palavra e estima quantas palavras a voz errou.

    O /align recebe o roteiro como dica e às vezes "não ouve" o começo do áudio: o erro sobe à toa e as
    palavras não ouvidas ganham tempos espremidos. Nesses casos uma segunda transcrição, sem dica,
    confirma o erro (vale o menor) e refaz o tempo das palavras para a legenda.
    """
    endereco = os.environ["ANALISE_URL"]
    r = requests.post(f"{endereco}/align", timeout=300,
                      json={"path": str(wav.resolve()), "text": texto, "language": "pt"})
    r.raise_for_status()
    dados = r.json()
    palavras = [[p["text"], p["startMs"] / 1000, p["endMs"] / 1000] for p in dados["words"]]
    total = max(1, len(_tokens(texto)))
    # divergências que só diferem em hífen/pontuação ("bicho-da-farinha" × "bicho -da -farinha") não contam
    reais = [d for d in dados.get("mismatches", []) if _tokens(d["expected"]) != _tokens(d["heard"])]
    wer = sum(max(len(_tokens(d["expected"])), len(_tokens(d["heard"]))) for d in reais) / total
    if wer > config["tts"]["conferencia"]["wer_maximo"] or _tempos_suspeitos(palavras):
        r = requests.post(f"{endereco}/transcribe", timeout=300,
                          json={"path": str(wav.resolve()), "language": "pt"})
        if r.ok:
            ouvido = r.json()
            wer = min(wer, _wer(texto, ouvido["text"]))
            if _tempos_suspeitos(palavras):
                palavras = _realinhar(texto, ouvido["words"]) or palavras
    return {"wer": round(wer, 3), "palavras": palavras, "divergencias": reais}


def _tempos_suspeitos(palavras: list) -> bool:
    """Palavras com menos de 30 ms são as que o /align não ouviu e preencheu no chute."""
    return sum(1 for _, ini, fim in palavras if fim - ini < 0.03) >= 2


def _realinhar(texto: str, ouvidas: list[dict]) -> list | None:
    """Tempo de cada palavra do roteiro a partir das palavras ouvidas numa transcrição livre.

    Compara as duas sequências já normalizadas (sem acento, hífen ou pontuação, números por extenso);
    palavras do roteiro sem par recebem o intervalo entre as vizinhas, dividido pelo tamanho.
    """
    roteiro = texto.split()
    # cada palavra vira uma ou mais "subpalavras" normalizadas, lembrando de qual palavra veio
    a, dono_a = [], []
    for i, p in enumerate(roteiro):
        for t in _tokens(p):
            a.append(t)
            dono_a.append(i)
    b, tempo_b = [], []
    for p in ouvidas:
        partes = _tokens(p["text"])
        ini, fim = p["startMs"] / 1000, p["endMs"] / 1000
        for k, t in enumerate(partes):
            passo = (fim - ini) / len(partes)
            b.append(t)
            tempo_b.append((ini + k * passo, ini + (k + 1) * passo))
    if not a or not b:
        return None
    tempos: list = [None] * len(roteiro)
    for bloco in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(bloco.size):
            i = dono_a[bloco.a + k]
            ini, fim = tempo_b[bloco.b + k]
            tempos[i] = (min(ini, tempos[i][0]), max(fim, tempos[i][1])) if tempos[i] else (ini, fim)
    if sum(t is not None for t in tempos) < len(roteiro) / 2:
        return None  # transcrição muito diferente: melhor ficar com o que havia
    fim_audio = tempo_b[-1][1]
    i = 0
    while i < len(roteiro):
        if tempos[i]:
            i += 1
            continue
        j = i
        while j < len(roteiro) and not tempos[j]:
            j += 1
        ini = tempos[i - 1][1] if i > 0 else 0.0
        fim = tempos[j][0] if j < len(roteiro) else fim_audio
        pesos = [len(roteiro[k]) + 1 for k in range(i, j)]
        cursor = ini
        for k, peso in zip(range(i, j), pesos):
            dur = max(fim - ini, 0.05 * (j - i)) * peso / sum(pesos)
            tempos[k] = (cursor, cursor + dur)
            cursor += dur
        i = j
    return [[p, round(ini, 3), round(fim, 3)] for p, (ini, fim) in zip(roteiro, tempos)]


def _wer(esperado: str, ouvido: str) -> float:
    a, b = _tokens(esperado), _tokens(ouvido)
    erros = sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2
                in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if op != "equal")
    return erros / max(1, len(a))


UNIDADES = ("zero um dois três quatro cinco seis sete oito nove dez onze doze treze quatorze quinze "
            "dezesseis dezessete dezoito dezenove").split()
DEZENAS = "_ _ vinte trinta quarenta cinquenta sessenta setenta oitenta noventa".split()
CENTENAS = "_ cento duzentos trezentos quatrocentos quinhentos seiscentos setecentos oitocentos novecentos".split()


def _extenso(n: int) -> str:
    """Número por extenso (até 9999), para comparar "10" com "dez"."""
    if n < 20:
        return UNIDADES[n]
    if n < 100:
        return DEZENAS[n // 10] + ("" if n % 10 == 0 else " e " + UNIDADES[n % 10])
    if n < 1000:
        return "cem" if n == 100 else CENTENAS[n // 100] + ("" if n % 100 == 0 else " e " + _extenso(n % 100))
    milhar = "mil" if n // 1000 == 1 else _extenso(n // 1000) + " mil"
    resto = n % 1000
    if resto == 0:
        return milhar
    # "mil e quinze", "mil e trezentos", mas "mil novecentos e noventa"
    return milhar + (" e " if resto < 100 or resto % 100 == 0 else " ") + _extenso(resto)


def _tokens(texto: str) -> list[str]:
    texto = re.sub(r"\d+", lambda m: _extenso(int(m.group())) if int(m.group()) < 10000 else m.group(), texto.lower())
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", texto)


# ---------- provedores: cada um grava o áudio e devolve o caminho do arquivo ----------

def _garantir_referencia(config: dict) -> None:
    c = config["tts"]["comfyui"]
    nome_remoto = f"video-make-{c['referencia']}"
    if nome_remoto not in comfy.opcoes("LoadAudio", "audio"):
        comfy.enviar(RAIZ / "assets" / "vozes" / c["referencia"], nome_remoto)
        log(f"Voz de referência enviada ao ComfyUI: {nome_remoto}")


def _comfyui(config: dict, texto: str, destino: Path, semente: int) -> Path:
    c = config["tts"]["comfyui"]
    return comfy.rodar(c["workflow"], {
        "text": texto, "seed": semente, "reference": f"video-make-{c['referencia']}",
        "cfg": c["cfg"], "temperature": c["temperature"],
    }, destino)


_GRATIS_ESGOTADA = False


def _pedir_voz(modelo: str, conteudo: dict, voz: str) -> requests.Response:
    """Usa a chave grátis (GEMINI_API_KEY_GRATIS) enquanto houver cota e depois a paga (GEMINI_API_KEY).
    É o mesmo modelo e a mesma voz nas duas: trocar de chave não muda o som."""
    global _GRATIS_ESGOTADA
    corpo = {"model": modelo, "input": [{"type": "user_input", "content": [conteudo]}],
             "response_format": {"type": "audio"}, "generation_config": {"speech_config": [{"voice": voz}]}}
    gratis = os.environ.get("GEMINI_API_KEY_GRATIS")
    if gratis and not _GRATIS_ESGOTADA:
        r = requests.post(URL_VOZ, headers={"x-goog-api-key": gratis}, json=corpo, timeout=300)
        if r.status_code != 429 or not os.environ.get("GEMINI_API_KEY"):
            return r
        _GRATIS_ESGOTADA = True
        log("Limite da chave grátis do Gemini atingido; seguindo com a chave paga até o fim desta rodada")
    return requests.post(URL_VOZ, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, json=corpo, timeout=300)


URL_VOZ = "https://generativelanguage.googleapis.com/v1beta/interactions"


def _google(config: dict, texto: str, destino: Path, semente: int) -> Path:
    """Gemini TTS (o "Generate Speech" do AI Studio), pela Interactions API.

    Tenta os modelos de tts.google.modelos em ordem quando a cota de um acaba. O primeiro que funcionar
    fica gravado em audio/google/modelo.txt e vale até o fim do vídeo, para a voz não mudar no meio.
    """
    c = config["tts"]["google"]
    fixo = destino.parent / "modelo.txt"
    modelos = [fixo.read_text().strip()] if fixo.exists() else c["modelos"]
    conteudo = {"type": "text", "text": texto}
    if c.get("estilo"):  # a recomendação é deixar vazio e marcar a emoção no próprio texto
        conteudo["annotations"] = [{"type": "speech_metadata", "style": c["estilo"]}]
    for i, modelo in enumerate(modelos):
        # no nível pago, 429 é limite por minuto: espera em vez de trocar de modelo (a voz mudaria no meio do vídeo)
        for tentativa in range(6 if c.get("pago") else 1):
            r = _pedir_voz(modelo, conteudo, c["voz"])
            if r.status_code != 429 or not c.get("pago"):
                break
            espera = float(r.headers.get("retry-after") or 10 * 2 ** tentativa)
            log(f"Limite por minuto do {modelo}; tentando de novo em {espera:.0f} s")
            time.sleep(espera)
        if r.status_code != 429:
            break
        if i == len(modelos) - 1:
            detalhe = r.json().get("error", {}).get("message", r.text)[:300]
            raise CotaEsgotada(f"Cota do Gemini TTS esgotada ({modelo}): {detalhe}\n"
                               "  O que já foi narrado fica salvo; rode o mesmo comando depois para continuar.")
        log(f"Cota do {modelo} esgotada; tentando {modelos[i + 1]}")
    if r.ok and not fixo.exists():
        fixo.write_text(modelo)
    if not r.ok:
        raise RuntimeError(f"Gemini TTS recusou: HTTP {r.status_code} {r.text[:500]}")
    audios = [p["data"] for passo in r.json().get("steps", []) if passo.get("type") == "model_output"
              for p in passo.get("content", []) if p.get("type") == "audio"]
    if not audios:
        raise RuntimeError(f"Gemini TTS não devolveu áudio: {r.text[:300]}")
    destino.write_bytes(base64.b64decode(audios[-1]))
    return destino


def _openai(config: dict, texto: str, destino: Path, semente: int) -> Path:
    c = config["tts"]["openai"]
    r = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={"model": c["modelo"], "voice": c["voz"], "input": texto,
              "instructions": c["instrucoes"], "response_format": "wav"},
        timeout=120,
    )
    r.raise_for_status()
    destino.write_bytes(r.content)
    return destino


def _elevenlabs(config: dict, texto: str, destino: Path, semente: int) -> Path:
    c = config["tts"]["elevenlabs"]
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{c['voz_id']}?output_format=mp3_44100_128",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
        json={"text": texto, "model_id": c["modelo"]},
        timeout=120,
    )
    r.raise_for_status()
    destino.write_bytes(r.content)
    return destino


def _macos(config: dict, texto: str, destino: Path, semente: int) -> Path:
    c = config["tts"]["macos"]
    rodar(["say", "-v", c["voz"], "-r", str(c["velocidade"]), "--file-format=WAVE",
           "--data-format=LEI16@48000", "-o", str(destino), texto])
    return destino


PROVEDORES = {"comfyui": _comfyui, "google": _google, "openai": _openai, "elevenlabs": _elevenlabs, "macos": _macos}
