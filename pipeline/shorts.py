"""[8] Shorts: cortes verticais (1080x1920) dos trechos mais virais do vídeo longo, com a mesma narração.

O LLM escolhe os cortes com base nos ganchos do vídeo de referência (que viralizou): cada um tem
uma cena de abertura opcional (o gancho, tocado antes) e um trecho de cenas inteiras e seguidas.
Cada corte é renderizado no Remotion (composição Short) com chamada fixa no topo e legenda grande
palavra por palavra, e ganha duas capas em pé (A e B) na composição CapaShort.

Saídas em projetos/<slug>/: shorts.json e, em shorts/, short_01.mp4 (02, 03…, do mais viral para
o menos), short_01_capa_A.jpg e _B.jpg, e shorts.txt com título, descrição e hashtags.
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path

from . import entrega, llm, montagem, tts
from .util import PROMPTS, RENDER, duracao_midia, extrair_json, ler_json, log, preencher, rodar, salvar_json, versao_midias

MAX_PALAVRAS = 3     # palavras por bloco de legenda
MAX_CARACTERES = 18  # bloco maior que isso quebra em duas linhas grandes demais
FOLGA = 0.3          # segundos que a legenda fica na tela depois da última palavra
MAX_GANCHO = 10.0    # segundos da cena de abertura
DESLOCAMENTO_ID = 10000  # a cena do gancho pode reaparecer no trecho; o id copiado não pode colidir
# CTA de inscrição: usa o lugar do aviso e do convite (render/src/Short.tsx), então só entra no espaço entre os dois
FIM_AVISO = 5.0      # o aviso vai do 1º ao 5º segundo (AVISO_INICIO + AVISO_DURACAO)
CONVITE = 2.5        # o convite ocupa os últimos 2,5 s (FIM_CTA)
MIN_CTA = 1.5        # menos que isso livre, o CTA não entra
CLIQUE = 0.55        # o toque que vira o botão em "inscrito", em fração da duração do CTA
# sinal sonoro do CTA, sintetizado no ffmpeg: "plim-plim" de notificação na entrada e um clique no toque
PLIM = ("0.16*(sin(2*PI*1319*t)+0.35*sin(2*PI*3640*t)*exp(-6*t))*exp(-5*t)"
        "+0.16*gte(t,0.12)*(sin(2*PI*1760*(t-0.12))+0.35*sin(2*PI*4858*(t-0.12))*exp(-6*(t-0.12)))*exp(-4*(t-0.12))")
TOQUE = "0.35*sin(2*PI*1800*t)*exp(-90*t)"
# pergunta falada no fim ("E aí, o que você achou de…? Comenta aqui embaixo"), com a voz da narração
ID_PERGUNTA = 2 * DESLOCAMENTO_ID
ANTES_PERGUNTA = 0.35  # respiro entre o fim do trecho e a pergunta
DEPOIS_PERGUNTA = 0.6  # a imagem fica um pouco depois da última palavra


def gerar(config: dict, projeto: Path) -> list[Path]:
    cenas = ler_json(projeto / "cenas.json")
    longo = projeto / "video_final.mp4"
    if not longo.exists():
        raise RuntimeError("Os Shorts são cortes do vídeo longo: rode a etapa de vídeo antes.")
    c = config["shorts"]
    saida = projeto / "shorts.json"
    if not saida.exists():
        linhas = "\n".join(f"{x['id']} | cap {x['capitulo']} | {x['duracao']:.1f}s | {x['texto']}" for x in cenas)
        prompt = preencher((PROMPTS / "shorts.md").read_text(), cenas=linhas, referencia=_referencia(projeto),
                           quantidade=c["quantidade"], min_seg=c["min_seg"], max_seg=c["max_seg"])
        resposta = llm.gerar(config, prompt, projeto=projeto, etapa="8_shorts", saida=saida)
        dados = extrair_json(resposta)
        _validar(dados, cenas, c)
        dados["shorts"].sort(key=lambda s: -s.get("nota_viral", 0))  # short_01 é o mais forte: publique primeiro
        salvar_json(saida, dados)
    dados = ler_json(saida)

    pasta = projeto / "shorts"
    pasta.mkdir(exist_ok=True)
    codigo = hashlib.sha1(b"".join(p.read_bytes() for p in sorted((RENDER / "src").rglob("*.ts*")))).hexdigest()
    por_id = {x["id"]: x for x in cenas}
    feitos = []
    for n, short in enumerate(dados["shorts"], start=1):
        pecas = _pecas(short, cenas)
        pergunta = _pergunta(config, projeto, short)
        if pergunta:
            pecas.append(_peca_pergunta(pecas, pergunta))
        total = sum(p["duracao"] for p in pecas)
        arquivo = pasta / f"short_{n:02d}.mp4"
        props = _props(config, projeto, short, pecas, total)
        assinatura = hashlib.sha1((codigo + json.dumps(props, sort_keys=True) + versao_midias(props, projeto)).encode()).hexdigest()
        marca = arquivo.with_suffix(".sha1")
        if not (arquivo.exists() and marca.exists() and marca.read_text() == assinatura):
            gancho = f"gancho {short['gancho']} + " if short.get("gancho") else ""
            log(f"Renderizando Short {n}/{len(dados['shorts'])}: {gancho}cenas {short['inicio']}–{short['fim']} ({total:.0f} s)…")
            arquivo_props = pasta / f"short_{n:02d}.props.json"
            salvar_json(arquivo_props, props)
            visual = pasta / f"short_{n:02d}.visual.mp4"
            subprocess.run(
                ["npx", "remotion", "render", "src/index.ts", "Short", str(visual),
                 f"--props={arquivo_props}", f"--public-dir={projeto}", "--muted", "--log=error"],
                cwd=RENDER, check=True,
            )
            _audio(longo, visual, arquivo, pecas, props["inscricao"], fps=config["video"]["fps"])
            visual.unlink()
            marca.write_text(assinatura)
        for letra, capa in zip("AB", short.get("capas", [])):
            _capa(config, projeto, pasta, n, letra, capa, pecas, por_id, codigo)
        log(f"Short {n} (nota {short.get('nota_viral', '?')}): \"{short['titulo']}\" → shorts/{arquivo.name}")
        feitos.append(arquivo)
    _texto(projeto, dados, cenas)
    entrega.organizar(projeto)
    return feitos


def _referencia(projeto: Path) -> str:
    """Ganchos e técnicas de retenção do vídeo de referência, para os cortes seguirem o que já viralizou."""
    arquivo = projeto / "referencia.json"
    if not arquivo.exists():
        return "(sem análise da referência)"
    ref = ler_json(arquivo)
    linhas = [f"- Gancho de abertura: {b['tecnica']} ({b['resumo']})" for b in ref.get("beats", []) if b.get("nome") == "gancho"]
    linhas += [f"- {t}" for t in ref.get("tecnicas_retencao", [])]
    return "\n".join(linhas) or "(sem análise da referência)"


def _validar(dados: dict, cenas: list[dict], c: dict) -> None:
    por_id = {x["id"]: x for x in cenas}
    ordem = [x["id"] for x in cenas]
    usados = set()
    erro = "Corrija shorts.json.resposta e rode de novo."
    for short in dados.get("shorts", []):
        ini, fim, gancho = short.get("inicio"), short.get("fim"), short.get("gancho")
        if ini not in por_id or fim not in por_id or ordem.index(ini) > ordem.index(fim):
            raise RuntimeError(f"Short com cenas inválidas: {ini}–{fim}. {erro}")
        if gancho is not None and (gancho not in por_id or por_id[gancho]["duracao"] > MAX_GANCHO):
            raise RuntimeError(f"Short {ini}–{fim}: o gancho {gancho} não existe ou passa de {MAX_GANCHO:.0f} s. {erro}")
        trecho = ordem[ordem.index(ini): ordem.index(fim) + 1]
        duracao = por_id[fim]["inicio"] + por_id[fim]["duracao"] - por_id[ini]["inicio"]
        duracao += por_id[gancho]["duracao"] if gancho is not None else 0
        # tolera um pouco além da faixa: o corte é sempre em cena inteira
        if not c["min_seg"] * 0.85 <= duracao <= c["max_seg"] * 1.15:
            raise RuntimeError(f"Short {ini}–{fim} tem {duracao:.0f} s com o gancho; o pedido é de "
                               f"{c['min_seg']} a {c['max_seg']} s. {erro}")
        if usados & set(trecho):
            raise RuntimeError(f"Short {ini}–{fim} repete cenas de outro Short. {erro}")
        usados |= set(trecho)
        for campo in ("titulo", "chamada"):
            if not short.get(campo):
                raise RuntimeError(f"Short {ini}–{fim} sem {campo}. {erro}")
        for capa in short.get("capas", []):
            if capa.get("cena") not in por_id or not capa.get("texto"):
                raise RuntimeError(f"Short {ini}–{fim}: capa sem texto ou com cena inválida. {erro}")


def _pecas(short: dict, cenas: list[dict]) -> list[dict]:
    """Cenas do Short na ordem em que tocam (gancho e depois o trecho), com o início dentro do Short."""
    ids = [x["id"] for x in cenas]
    lista = [dict(x, origem=x["inicio"]) for x in cenas[ids.index(short["inicio"]): ids.index(short["fim"]) + 1]]
    if short.get("gancho") is not None:
        cena = cenas[ids.index(short["gancho"])]
        lista.insert(0, dict(cena, origem=cena["inicio"], id=cena["id"] + DESLOCAMENTO_ID))
    # a vinheta e a placa de bloco do vídeo longo não entram no Short: corta o silêncio do fim da cena
    for cena in lista:
        intervalo = cena.pop("interludio", None)
        if intervalo:
            cena["duracao"] = round(cena["duracao"] - intervalo["seg"], 3)
    # mídia própria para o vertical (shorts.json "midias_vertical": {"121": {"tipo": "video", "src": ...}}):
    # motions e templates feitos para 16:9 saem cortados no 9:16 (títulos e etiquetas nas bordas)
    trocas = {int(k): v for k, v in (short.get("midias_vertical") or {}).items()}
    for i, cena in enumerate(lista):
        troca = trocas.get(cena["id"] % DESLOCAMENTO_ID)
        if troca:
            lista[i] = dict({k: v for k, v in cena.items() if k != "fluxo"}, tipo="midia", midia=troca, overlay=None)
    # o primeiro segundo decide se a pessoa fica: abre com imagem em tela cheia, não com template na janela
    if lista[0]["tipo"] != "midia":
        midia = next((x.get("midia") for x in lista if x.get("midia")), None)
        lista[0] = dict(lista[0], tipo="midia", midia=lista[0].get("midia") or midia, overlay=None)
    t = 0.0
    for cena in lista:
        cena["inicio"] = t
        t += cena["duracao"]
    return lista


def _pergunta(config: dict, projeto: Path, short: dict) -> dict | None:
    """Fala da pergunta final do Short (`pergunta` no shorts.json), com a voz e o modelo da narração do vídeo.

    Só com a voz do Google: o modelo fica em audio/google/modelo.txt, então a pergunta soa igual ao resto
    (o canal nunca mistura vozes). O áudio fica guardado pelo texto; trocar a pergunta gera outro.
    """
    c = config["shorts"].get("pergunta") or {}
    texto = (short.get("pergunta") or "").strip()
    pasta = projeto / "audio" / "google"
    if not c.get("ligado") or not texto:
        return None
    if not (pasta / "modelo.txt").exists():
        log("Pergunta final dos Shorts só sai com a voz do Google (a narração deste vídeo é outra): pulando")
        return None
    wav = pasta / f"pergunta_{hashlib.sha1(texto.encode()).hexdigest()[:10]}.wav"
    marca = wav.with_suffix(".json")
    if not (wav.exists() and marca.exists()):
        log(f"Narrando a pergunta final: \"{texto}\"")
        bruto = tts._google(config, texto, wav.with_suffix(".bruto"), semente=0)
        rodar(["ffmpeg", "-y", "-v", "error", "-i", str(bruto), "-ac", "1", "-ar", "48000", "-af",
               "silenceremove=start_periods=1:start_threshold=-50dB,"
               "areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse", str(wav)])
        bruto.unlink()
        salvar_json(marca, tts._conferir(config, wav, texto))
    info = ler_json(marca)
    return {"texto": texto, "wav": wav, "duracao": duracao_midia(wav), "palavras": info.get("palavras"),
            "selo": c.get("selo", "Comenta aqui embaixo")}


def _peca_pergunta(pecas: list[dict], pergunta: dict) -> dict:
    """Última peça do Short: a imagem da última cena com mídia, enquanto a pergunta é falada."""
    base = next(x for x in reversed(pecas) if x.get("midia"))
    fim = pecas[-1]["inicio"] + pecas[-1]["duracao"]
    palavras = [[p, a + ANTES_PERGUNTA, b + ANTES_PERGUNTA] for p, a, b in pergunta["palavras"] or []] or None
    return {"id": ID_PERGUNTA, "capitulo": base.get("capitulo"), "tipo": "midia", "midia": base["midia"], "overlay": None,
            "cta": False, "texto": pergunta["texto"], "palavras": palavras, "inicio": fim, "origem": None,
            "duracao": round(ANTES_PERGUNTA + pergunta["duracao"] + DEPOIS_PERGUNTA, 3), "pergunta": pergunta}


def _props(config: dict, projeto: Path, short: dict, pecas: list[dict], total: float) -> dict:
    fps = config["video"]["fps"]
    marcos = [round(x["inicio"] * fps) for x in pecas] + [round(total * fps)]
    for i, cena in enumerate(pecas):
        cena["q_inicio"], cena["q_duracao"] = marcos[i], marcos[i + 1] - marcos[i]
    base = montagem._props(config, projeto, pecas, fps)
    for cena in base["cenas"]:
        cena["overlay"], cena["selo"] = None, False  # título de capítulo, escalada e selo de inscrição são do vídeo longo
    return {
        "fps": fps, "transicao": base["transicao"], "corDestaque": base["corDestaque"], "corFundo": base["corFundo"],
        "corTexto": base["corTexto"], "chamada": short["chamada"], "destaque": short.get("destaque", ""),
        "aviso": short.get("aviso", ""), "convite": short.get("convite", ""), "inscricao": _inscricao(config, fps, bool(short.get("aviso")), total),
        "cenas": base["cenas"], "legenda": _legenda(pecas, total, fps), "pergunta": _selo_pergunta(pecas, fps),
    }


def _selo_pergunta(pecas: list[dict], fps: int) -> dict | None:
    """Balão "comenta aqui" enquanto a pergunta final é falada, em quadros do Short."""
    ultima = pecas[-1]
    if not ultima.get("pergunta"):
        return None
    return {"inicio": round((ultima["inicio"] + ANTES_PERGUNTA) * fps), "texto": ultima["pergunta"]["selo"]}


def _inscricao(config: dict, fps: int, aviso: bool, total: float) -> dict | None:
    """CTA "inscreva-se" do meio do Short (shorts.cta no config), em quadros, já encaixado entre o aviso e o convite."""
    cta = config["shorts"].get("cta") or {}
    if not cta.get("ligado"):
        return None
    inicio = max(cta.get("inicio_seg", 10), FIM_AVISO if aviso else 0)
    fim = min(inicio + cta.get("duracao_seg", 4), total - CONVITE)
    if fim - inicio < MIN_CTA:
        return None
    duracao = round((fim - inicio) * fps)
    return {"inicio": round(inicio * fps), "duracao": duracao, "clique": round(duracao * CLIQUE),
            "texto": cta.get("texto", "Inscreva-se e ative o sino"), "inscrito": cta.get("inscrito", "Inscrito"),
            "som": bool(cta.get("som", True))}


def _legenda(pecas: list[dict], total: float, fps: int) -> list[dict]:
    """Blocos curtos de até 3 palavras com o tempo de cada uma, em quadros do Short."""
    palavras = []  # (texto, início, fim) em segundos do Short
    for cena in pecas:
        desloc = cena["inicio"]
        if cena.get("palavras"):
            palavras += [(p, desloc + a, desloc + b) for p, a, b in cena["palavras"]]
            continue
        # sem tempo do Whisper: reparte a fala pelo número de letras
        lista = cena["texto"].split()
        falado = cena["duracao"] * 0.92
        letras = sum(len(p) for p in lista)
        t = desloc
        for p in lista:
            dur = falado * len(p) / letras
            palavras.append((p, t, t + dur))
            t += dur

    blocos, atual = [], []
    for texto, a, b in palavras:
        limpo = re.sub(r"[.,;:…\"“”]+$", "", texto).lstrip("\"“")
        candidato = " ".join(p for p, _, _ in atual + [(limpo, a, b)])
        if atual and (len(atual) >= MAX_PALAVRAS or len(candidato) > MAX_CARACTERES):
            blocos.append(atual)
            atual = []
        atual.append((limpo, a, b))
        if re.search(r"[.,;:?!…]$", texto):  # pontuação fecha o bloco
            blocos.append(atual)
            atual = []
    if atual:
        blocos.append(atual)

    saida = []
    for i, bl in enumerate(blocos):
        inicio = bl[0][1]
        proximo = blocos[i + 1][0][1] if i + 1 < len(blocos) else total
        fim = min(proximo, bl[-1][2] + FOLGA)
        saida.append({
            "inicio": round(inicio * fps), "fim": max(round(fim * fps), round(inicio * fps) + 1),
            "palavras": [{"texto": p, "inicio": round(a * fps), "fim": round(b * fps)} for p, a, b in bl],
        })
    return saida


def _audio(longo: Path, visual: Path, destino: Path, pecas: list[dict], cta: dict | None, fps: int) -> None:
    """Corta o áudio já mixado do vídeo longo (gancho e trecho), junta, põe o sinal do CTA e normaliza."""
    # cenas seguidas no vídeo longo viram um corte só, sem emenda no meio da fala
    trechos = []
    pergunta = pecas[-1].get("pergunta")
    for cena in pecas:
        if cena.get("origem") is None:
            continue  # a pergunta final não vem do vídeo longo: entra depois, do próprio arquivo
        if trechos and abs(trechos[-1][1] - cena["origem"]) < 0.01:
            trechos[-1][1] = cena["origem"] + cena["duracao"]
        else:
            trechos.append([cena["origem"], cena["origem"] + cena["duracao"]])
    filtros = [f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.05,"
               f"afade=t=out:st={b - a - 0.12:.3f}:d=0.12[p{i}]" for i, (a, b) in enumerate(trechos)]
    entradas = ["-i", str(longo)]
    pedacos = "".join(f"[p{i}]" for i in range(len(trechos)))
    if pergunta:
        entradas += ["-i", str(pergunta["wav"])]
        canais = "stereo" if _canais(longo) == 2 else "mono"  # o concat exige o mesmo layout nos dois
        filtros.append(f"[1:a]aresample=48000,aformat=channel_layouts={canais},adelay={round(ANTES_PERGUNTA * 1000)}:all=1,apad=pad_dur={DEPOIS_PERGUNTA}[pf]")
        pedacos += "[pf]"
    filtros.append(pedacos + f"concat=n={len(trechos) + bool(pergunta)}:v=0:a=1"
                   + ("[n]" if cta and cta["som"] else "[a]"))
    if cta and cta["som"]:
        entra = round(cta["inicio"] / fps * 1000)
        toque = round((cta["inicio"] + cta["clique"]) / fps * 1000)
        filtros += [f"aevalsrc='{PLIM}':s=48000:d=0.9,adelay={entra}:all=1[plim]",
                    f"aevalsrc='{TOQUE}':s=48000:d=0.08,adelay={toque}:all=1[toque]",
                    "[n][plim][toque]amix=inputs=3:duration=first:normalize=0[a]"]
    juntos = destino.with_suffix(".wav")
    rodar(["ffmpeg", "-y", "-v", "error", *entradas, "-filter_complex", ";".join(filtros),
           "-map", "[a]", "-ar", "48000", str(juntos)])
    rodar(["ffmpeg", "-y", "-v", "error", "-i", str(visual), "-i", str(juntos), "-af", montagem.normalizar(juntos),
           "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-shortest", str(destino)])
    juntos.unlink()


def _canais(arquivo: Path) -> int:
    saida = rodar(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels",
                   "-of", "default=nw=1:nk=1", str(arquivo)]).stdout
    return int(saida.strip() or 1)


def _capa(config: dict, projeto: Path, pasta: Path, n: int, letra: str, capa: dict, pecas: list[dict],
          por_id: dict, codigo: str) -> None:
    """Capa em pé (1080x1920, JPEG abaixo de 2 MB) com a imagem da cena pedida, ou da primeira com mídia."""
    trocada = [x for x in pecas if x["id"] % DESLOCAMENTO_ID == capa["cena"] and x.get("midia") and x["midia"] != por_id[capa["cena"]].get("midia")]
    candidatas = trocada + [por_id[capa["cena"]]] + [x for x in pecas if x.get("midia")]  # mídia do vertical primeiro
    cena = next((x for x in candidatas if x.get("midia") and (projeto / x["midia"]["src"]).exists()), None)
    if not cena:
        return
    imagem = projeto / cena["midia"]["src"]
    if cena["midia"]["tipo"] == "video":  # quadro do meio do clipe
        quadro = pasta / f"short_{n:02d}_capa_{letra}_fundo.jpg"
        meio = duracao_midia(imagem) / 2
        rodar(["ffmpeg", "-y", "-v", "error", "-ss", f"{meio:.2f}", "-i", str(imagem), "-frames:v", "1",
               "-q:v", "2", str(quadro)])
        imagem = quadro
    props = {
        "imagem": str(imagem.relative_to(projeto)), "texto": capa["texto"], "destaque": capa.get("destaque", ""),
        "selo": capa.get("selo", ""), "layout": "centro",
        "corDestaque": config["visual"]["cor_destaque"], "corFundo": config["visual"]["cor_fundo"],
    }
    destino = pasta / f"short_{n:02d}_capa_{letra}.jpg"
    assinatura = hashlib.sha1((codigo + json.dumps(props, sort_keys=True) + str(imagem.stat().st_mtime)).encode()).hexdigest()
    marca = destino.with_suffix(".sha1")
    if destino.exists() and marca.exists() and marca.read_text() == assinatura:
        return
    arquivo_props = pasta / f"short_{n:02d}_capa_{letra}.props.json"
    salvar_json(arquivo_props, props)
    subprocess.run(["npx", "remotion", "still", "src/index.ts", "CapaShort", str(destino), f"--props={arquivo_props}",
                    f"--public-dir={projeto}", "--image-format=jpeg", "--jpeg-quality=88", "--log=error"],
                   cwd=RENDER, check=True)
    marca.write_text(assinatura)


def _tempo(seg: float) -> str:
    s = int(seg)
    return f"{s // 60}:{s % 60:02d}"


def _texto(projeto: Path, dados: dict, cenas: list[dict]) -> None:
    pub = ler_json(projeto / "publicacao.json") if (projeto / "publicacao.json").exists() else {}
    hashtags = ["#shorts"] + ["#" + re.sub(r"[^\w]", "", t) for t in pub.get("tags", []) if " " not in t][:2]
    por_id = {x["id"]: x for x in cenas}
    linhas = ["Ordem: do corte mais forte (short_01) para o mais fraco. Agenda: o 02 na véspera do vídeo longo (trailer), "
              "o 01 uma hora depois do longo, e os outros um por dia a partir do dia seguinte.", ""]
    for n, short in enumerate(dados["shorts"], start=1):
        ini, fim = por_id[short["inicio"]], por_id[short["fim"]]
        t0, t1 = ini["inicio"], fim["inicio"] + fim["duracao"]
        gancho = por_id.get(short.get("gancho"))
        total = t1 - t0 + (gancho["duracao"] if gancho else 0)
        linhas += [
            f"SHORT {n}: shorts/short_{n:02d}.mp4 ({total:.0f} s; nota viral {short.get('nota_viral', '?')})",
            f"Por que: {short.get('por_que', '')}",
            (f"Abre com o gancho: \"{gancho['texto']}\"" if gancho else "Sem gancho separado: abre na primeira cena do trecho"),
            f"Trecho {_tempo(t0)}–{_tempo(t1)} do vídeo longo",
            f"Capas: shorts/short_{n:02d}_capa_A.jpg e _capa_B.jpg",
            f"Título: {short['titulo']}",
            "Descrição:",
            short.get("descricao", ""),
            " ".join(hashtags),
            "",
        ]
    linhas += [
        "No YouTube Studio, em cada Short, ligue \"Vídeo relacionado\" ao vídeo longo: vira um link clicável no Short.",
        "Capas: o YouTube não faz teste A/B em Shorts. Use a A no YouTube (capa própria só aparece para canais do "
        "Programa de Parcerias; antes disso, escolha um quadro do vídeo) e a B no Instagram e no TikTok; depois de "
        "alguns posts, fique com o estilo que rendeu mais.",
    ]
    (projeto / "shorts" / "shorts.txt").write_text("\n".join(linhas) + "\n")
