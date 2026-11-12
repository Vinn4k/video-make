"""[6] Montagem: renderiza o visual no Remotion (um arquivo por capítulo) e mixa o áudio com ffmpeg.

Saídas em projetos/<slug>/:
- video_final.mp4   vídeo pronto
- legendas.srt      legenda aproximada por cena
- youtube.txt       título, capítulos com tempo, fontes e créditos de mídia
"""

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from . import musica, sfx
from .util import RAIZ, RENDER, duracao_midia, ler_json, log, rodar, salvar_json, versao_midias


def gerar(config: dict, projeto: Path) -> Path:
    cenas = ler_json(projeto / "cenas.json")
    fps = config["video"]["fps"]
    _quadros(cenas, fps)

    pasta = projeto / "render"
    pasta.mkdir(exist_ok=True)
    # mudanças nos templates também invalidam os capítulos já renderizados
    codigo = hashlib.sha1(b"".join(p.read_bytes() for p in sorted((RENDER / "src").rglob("*.ts*")))).hexdigest()
    partes = []
    capitulos = sorted({c["capitulo"] for c in cenas})
    for numero in capitulos:
        bloco = [c for c in cenas if c["capitulo"] == numero]
        saida = pasta / f"cap_{numero:02d}.mp4"
        props = _props(config, projeto, bloco, fps)
        assinatura = hashlib.sha1((codigo + json.dumps(props, sort_keys=True) + versao_midias(props, projeto)).encode()).hexdigest()
        marca = saida.with_suffix(".sha1")
        if not (saida.exists() and marca.exists() and marca.read_text() == assinatura):
            arquivo_props = pasta / f"cap_{numero:02d}.props.json"
            salvar_json(arquivo_props, props)
            log(f"Renderizando capítulo {numero}/{len(capitulos)} ({len(bloco)} cenas)…")
            subprocess.run(
                ["npx", "remotion", "render", "src/index.ts", "Documentario", str(saida),
                 f"--props={arquivo_props}", f"--public-dir={projeto}", "--muted", "--log=error",
                 f"--concurrency={config['video'].get('render_concorrencia', 2)}",
                 f"--timeout={config['video'].get('render_timeout_seg', 120) * 1000}"],
                cwd=RENDER, check=True,
            )
            marca.write_text(assinatura)
        partes.append(saida)

    lista = pasta / "partes.txt"
    lista.write_text("".join(f"file '{p.name}'\n" for p in partes))
    visual = pasta / "visual.mp4"
    rodar(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lista.name, "-c", "copy",
           visual.name], cwd=pasta)

    final = projeto / "video_final.mp4"
    _mixar(config, projeto, visual, final, cenas)
    _legendas(projeto, cenas)
    descricao(projeto, cenas)
    log(f"Pronto: {final.relative_to(RAIZ)} ({duracao_midia(final) / 60:.1f} min)")
    return final


LICENCAS_LIVRES = {"Pexels License": "Pexels", "Pixabay Content License": "Pixabay"}


def _midias_usadas(cenas: list[dict]) -> list[dict]:
    """Mídia de cada cena e de cada etapa de fluxo."""
    midias = [c["midia"] for c in cenas if c.get("midia")]
    for c in cenas:
        if c["tipo"] == "fluxo":
            midias += [e["midia"] for e in c["fluxo"]["etapas"] if e.get("midia")]
    return midias


# tipo de cena → campo com os dados do template
TEMPLATES = {"frase_impacto": "frase", "grafico": "grafico", "numero_destaque": "numero",
             "split_topicos": "split", "fluxo": "fluxo", "manchete": "manchete"}


def _midia(projeto: Path, midia: dict | None) -> dict | None:
    if not midia or not (projeto / midia["src"]).exists():
        return None
    saida = {"tipo": midia["tipo"], "src": midia["src"]}
    if midia["tipo"] == "video":
        saida["duracaoSeg"] = round(duracao_midia(projeto / midia["src"]), 2)
    if midia.get("credito"):
        saida["credito"] = midia["credito"]
    return saida


def _quadros(cenas: list[dict], fps: int) -> None:
    """Converte inicio/duracao em quadros sem acumular erro de arredondamento."""
    total = cenas[-1]["inicio"] + cenas[-1]["duracao"]
    marcos = [round(c["inicio"] * fps) for c in cenas] + [round(total * fps)]
    for i, cena in enumerate(cenas):
        cena["q_inicio"], cena["q_duracao"] = marcos[i], marcos[i + 1] - marcos[i]


def _props(config: dict, projeto: Path, bloco: list[dict], fps: int) -> dict:
    visual = config["visual"]
    base = bloco[0]["q_inicio"]
    cenas = []
    for i, c in enumerate(bloco):
        anterior_cta = i > 0 and bloco[i - 1]["cta"]
        selo = {"sempre": True, "nunca": False}.get(visual["selo_inscricao"], c["cta"] or anterior_cta)
        cena = {
            "id": c["id"], "inicio": c["q_inicio"] - base, "duracao": c["q_duracao"],
            "tipo": c["tipo"], "midia": _midia(projeto, c.get("midia")), "overlay": c.get("overlay"), "selo": selo,
        }
        campo = TEMPLATES.get(c["tipo"])
        if campo:
            cena[campo] = c[campo]
        if c["tipo"] == "fluxo":
            cena["fluxo"] = {**c["fluxo"], "etapas": [{"rotulo": e["rotulo"], "midia": _midia(projeto, e.get("midia"))}
                                                      for e in c["fluxo"]["etapas"]]}
        cenas.append(cena)
    props = {
        "fps": fps, "largura": config["video"]["largura"], "altura": config["video"]["altura"],
        "corDestaque": visual["cor_destaque"], "corFundo": visual["cor_fundo"], "corTexto": visual["cor_texto"],
        "transicao": visual["transicao_frames"], "cenas": cenas, "interludio": None, "aSeguir": None,
    }
    ultima = bloco[-1]
    if ultima.get("interludio"):
        _interludio(config, projeto, props, ultima, fps)
    return props


def _interludio(config: dict, projeto: Path, props: dict, ultima: dict, fps: int) -> None:
    """Fim do bloco no formato programa: a última cena encolhe e o silêncio vira vinheta ou placa do próximo bloco."""
    capitulos = ler_json(projeto / "roteiro.json")["capitulos"]
    proximo = ultima["capitulo"] + 1  # o capítulo 1 é a abertura: o capítulo 2 é o bloco 1
    quadros = round(ultima["interludio"]["seg"] * fps)
    cena = props["cenas"][-1]
    cena["duracao"] -= quadros
    inicio = cena["inicio"] + cena["duracao"]
    props["interludio"] = {"tipo": ultima["interludio"]["tipo"], "inicio": inicio, "duracao": quadros,
                           "numero": proximo - 1, "titulo": capitulos[proximo - 1]["titulo"]}
    if ultima["interludio"]["tipo"] == "placa":
        a_seguir = round(config["programa"]["a_seguir_seg"] * fps)
        props["aSeguir"] = {"titulo": capitulos[proximo - 1]["titulo"], "inicio": max(0, inicio - a_seguir),
                            "duracao": min(a_seguir, inicio)}


ALVO = "I=-14:TP=-1:LRA=11"  # referência de volume do YouTube


def _mixar(config: dict, projeto: Path, visual: Path, final: Path, cenas: list[dict]) -> None:
    narracao = _com_interludios(config, projeto, cenas)
    efeitos = sfx.trilha(config, cenas, duracao_midia(narracao), projeto / "render" / "sfx.wav")
    if efeitos:  # efeitos de revelação junto da voz, antes da música (que abaixa quando a voz toca)
        com_efeitos = projeto / "render" / "narracao_sfx.wav"
        rodar(["ffmpeg", "-y", "-v", "error", "-i", str(narracao), "-i", str(efeitos), "-filter_complex",
               "[0:a]aresample=48000[v];[v][1:a]amix=inputs=2:duration=first:normalize=0[a]",
               "-map", "[a]", "-ar", "48000", str(com_efeitos)])
        efeitos.unlink()
        if narracao.name != "narracao.wav":
            narracao.unlink()
        narracao = com_efeitos
    mix = projeto / "render" / "mix.wav"
    musica = _musica(config)
    if musica:
        log(f"Música: {musica.name}")
        rodar(["ffmpeg", "-y", "-v", "error", "-i", str(narracao), "-stream_loop", "-1", "-i", str(musica),
               "-filter_complex",
               f"[0:a]asplit=2[voz][chave];[1:a]volume={config['musica']['volume']}[m];"
               f"[m][chave]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=500[fundo];"
               f"[voz][fundo]amix=inputs=2:duration=first:normalize=0[a]",
               "-map", "[a]", "-ar", "48000", str(mix)])
    else:
        rodar(["ffmpeg", "-y", "-v", "error", "-i", str(narracao), "-ar", "48000", str(mix)])

    rodar(["ffmpeg", "-y", "-v", "error", "-i", str(visual), "-i", str(mix), "-af", normalizar(mix),
           "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-ar", "48000", "-shortest", str(final)])
    mix.unlink()
    if narracao.name != "narracao.wav":
        narracao.unlink()


def _com_interludios(config: dict, projeto: Path, cenas: list[dict]) -> Path:
    """Narração com o som da vinheta e das placas nos trechos sem fala (formato programa)."""
    narracao = projeto / "narracao.wav"
    marcas = [(c["interludio"]["tipo"], c["inicio"] + c["duracao"] - c["interludio"]["seg"]) for c in cenas if c.get("interludio")]
    if not marcas:
        return narracao
    sons = {tipo: _som(config, tipo) for tipo in {t for t, _ in marcas}}
    entradas, filtros = ["-i", str(narracao)], []
    for i, (tipo, inicio) in enumerate(marcas, start=1):
        entradas += ["-i", str(sons[tipo])]
        filtros.append(f"[{i}:a]aresample={TAXA_MIX},adelay={int(inicio * 1000)}:all=1[s{i}]")
    rotulos = "".join(f"[s{i}]" for i in range(1, len(marcas) + 1))
    filtros.append(f"[0:a]aresample={TAXA_MIX}[voz];[voz]{rotulos}amix=inputs={len(marcas) + 1}:duration=first:normalize=0[a]")
    saida = projeto / "render" / "narracao_programa.wav"
    rodar(["ffmpeg", "-y", "-v", "error", *entradas, "-filter_complex", ";".join(filtros), "-map", "[a]", str(saida)])
    return saida


TAXA_MIX = 48000


def _som(config: dict, tipo: str) -> Path:
    """vinheta.* ou placa.* da pasta programa.som; sem eles, gera um som simples e o guarda lá."""
    pasta = RAIZ / config["programa"]["som"]
    pasta.mkdir(parents=True, exist_ok=True)
    proprio = sorted(p for p in pasta.glob(f"{tipo}.*") if p.suffix.lower() in (".mp3", ".wav", ".m4a"))
    if proprio:
        return proprio[0]
    gerado = pasta / f"{tipo}_gerado.wav"
    if not gerado.exists():
        if tipo == "vinheta":
            # acorde suave que cresce e some (ré menor), com um sopro de ruído na entrada
            filtro = ("sine=f=146.8:d=4[a];sine=f=220:d=4[b];sine=f=293.7:d=4[c];sine=f=349.2:d=4[d];"
                      "anoisesrc=color=pink:d=1.2:a=0.25,highpass=f=800,lowpass=f=6000,afade=t=in:d=0.6,afade=t=out:st=0.6:d=0.6[r];"
                      "[a][b][c][d]amix=inputs=4:normalize=1,volume=0.9,afade=t=in:d=0.8,afade=t=out:st=2.4:d=1.6[p];"
                      "[p][r]amix=inputs=2:duration=longest:normalize=0,volume=0.5")
        else:
            # "whoosh" curto com uma batida grave, como a troca de bloco na TV
            filtro = ("anoisesrc=color=pink:d=1.1:a=0.3,highpass=f=500,lowpass=f=5000,afade=t=in:d=0.5,afade=t=out:st=0.5:d=0.6[r];"
                      "sine=f=55:d=1.4,afade=t=out:st=0.05:d=1.3,volume=1.6[g];"
                      "[r][g]amix=inputs=2:duration=longest:normalize=0,volume=0.5")
        rodar(["ffmpeg", "-y", "-v", "error", "-filter_complex", filtro, "-ar", str(TAXA_MIX), "-ac", "1", str(gerado)])
    return gerado


def normalizar(audio: Path, antes: str = "") -> str:
    """Filtro de loudnorm em duas passadas: mede o áudio inteiro e devolve um ganho linear que acerta o alvo."""
    filtro = f"{antes}," if antes else ""
    saida = rodar(["ffmpeg", "-hide_banner", "-i", str(audio), "-af", f"{filtro}loudnorm={ALVO}:print_format=json",
                   "-f", "null", "-"]).stderr
    m = json.loads(saida[saida.rindex("{"):saida.rindex("}") + 1])
    return (f"{filtro}loudnorm={ALVO}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
            f"offset={m['target_offset']}:linear=true")


def _musica(config: dict) -> Path | None:
    if config["musica"]["arquivo"]:
        return RAIZ / config["musica"]["arquivo"]
    arquivos = sorted(p for p in (RAIZ / "assets" / "musica").glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a"))
    return arquivos[0] if arquivos else musica.gerar(config)


def _tempo_srt(seg: float) -> str:
    ms = int(round(seg * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


LINHA = 42       # caracteres por linha de legenda
LINHA_MAX = 52   # tolerância para não deixar uma palavra sozinha na última linha
MIN_TELA = 0.8   # segundos mínimos de cada legenda na tela


def _legendas(projeto: Path, cenas: list[dict]) -> None:
    itens = []  # (início, fim, texto) em segundos do vídeo
    for c in cenas:
        if c.get("palavras"):  # tempo real de cada palavra, vindo da conferência por Whisper
            linhas, linha = [], []
            for palavra in c["palavras"]:
                if linha and len(" ".join(p for p, _, _ in linha + [palavra])) > LINHA:
                    linhas.append(linha)
                    linha = []
                linha.append(palavra)
            linhas.append(linha)
            sobra = " ".join(p for p, _, _ in linhas[-1])
            if len(linhas) > 1 and (len(linhas[-1]) <= 2 or len(sobra) < 12) and \
                    len(" ".join(p for p, _, _ in linhas[-2] + linhas[-1])) <= LINHA_MAX:
                ultima = linhas.pop()
                linhas[-1] += ultima
            for linha in linhas:
                itens.append((c["inicio"] + linha[0][1], c["inicio"] + linha[-1][2], " ".join(p for p, _, _ in linha)))
            continue
        linhas, atual = [], ""
        for palavra in c["texto"].split():
            if len(atual) + len(palavra) + 1 > LINHA and atual:
                linhas.append(atual)
                atual = palavra
            else:
                atual = f"{atual} {palavra}".strip()
        linhas.append(atual)
        falado = c["duracao"] * 0.92
        total = sum(len(l) for l in linhas)
        t = c["inicio"]
        for linha in linhas:
            dur = falado * len(linha) / total
            itens.append((t, t + dur, linha))
            t += dur
    blocos = []
    for i, (ini, fim, texto) in enumerate(itens):
        proximo = itens[i + 1][0] if i + 1 < len(itens) else fim + MIN_TELA
        fim = max(fim, min(ini + MIN_TELA, proximo))  # estica legendas curtas sem invadir a seguinte
        blocos.append(f"{i + 1}\n{_tempo_srt(ini)} --> {_tempo_srt(fim)}\n{texto}\n")
    (projeto / "legendas.srt").write_text("\n".join(blocos))


def descricao(projeto: Path, cenas: list[dict]) -> None:
    """Escreve o youtube.txt; depois da etapa de publicação, inclui os títulos do teste A/B/C, a descrição e as tags."""
    roteiro = ler_json(projeto / "roteiro.json")
    pub = ler_json(projeto / "publicacao.json") if (projeto / "publicacao.json").exists() else None
    if pub:
        linhas = ["TÍTULOS (teste A/B/C no YouTube Studio; thumbs em thumbs/thumb_A/B/C.png):"]
        linhas += [f"{letra}) {titulo}" for letra, titulo in zip("ABC", pub["titulos"])]
        linhas += ["", "DESCRIÇÃO:", pub["descricao"], ""]
    else:
        linhas = [roteiro["titulo"], ""]
    linhas += ["Capítulos:"]
    vistos = set()
    for i, c in enumerate(cenas):
        if c["capitulo"] not in vistos:
            # o YouTube exige que o primeiro capítulo comece em 0:00; no formato programa, o bloco começa na placa
            placa = cenas[i - 1]["interludio"]["seg"] if i and cenas[i - 1].get("interludio") else 0
            seg = int(c["inicio"] - placa) if vistos else 0
            vistos.add(c["capitulo"])
            linhas.append(f"{seg // 60}:{seg % 60:02d} {roteiro['capitulos'][c['capitulo'] - 1]['titulo']}")
    if roteiro.get("fontes"):
        linhas += ["", "Fontes:"] + [f"- {f}" for f in roteiro["fontes"]]
    creditos_arq = projeto / "creditos.json"
    if creditos_arq.exists():
        # só o que está no vídeo: o creditos.json guarda também as mídias trocadas na revisão
        usados = {Path(m["src"]).name for m in _midias_usadas(cenas)}
        creditos = [c for nome, c in ler_json(creditos_arq).items() if nome in usados]
        geradas = sum(1 for c in creditos if c["origem_id"].startswith("ia-"))
        bancos = [c for c in creditos if c["licenca"] in LICENCAS_LIVRES]
        # pedido do usuário (06/11/2026): nada de lista "Imagens e vídeos" na descrição; só o crédito que a licença
        # exige (CC BY, CC BY-SA, ODbL/OpenStreetMap). Bancos livres, CC0, material enviado e IA não entram.
        exigidos = [c for c in creditos if not c["origem_id"].startswith("ia-")
                    and re.search(r"CC BY|ODbL", c["licenca"])]
        if exigidos:
            linhas += ["", "Créditos exigidos pela licença:"]
        # Muitas mídias do mesmo autor viram uma linha só, com o link da página dele (a descrição tem 5.000 caracteres)
        grupos = {}
        for c in exigidos:
            grupos.setdefault((c["autor"], c["licenca"]), set()).add(c["pagina"])
        for (autor, licenca), paginas in sorted(grupos.items()):
            paginas = sorted(p for p in paginas if p)
            if len(paginas) > 3:
                base = os.path.commonprefix(paginas)
                base = base[: base.rstrip("/").rfind("/") + 1] if not base.endswith("/") else base
                linhas.append(f"- {autor} ({licenca}), {len(paginas)} imagens: {base}")
            else:
                linhas += [f"- {autor} ({licenca}) {p}".rstrip() for p in paginas or [""]]
        if bancos:
            log(f"Créditos de banco livre fora da descrição: {len(bancos)} (a licença não exige)")
        if geradas:
            log(f"Lembrete: o vídeo tem {geradas} imagem(ns) de IA; marque \"conteúdo alterado ou sintético\" no YouTube Studio")
    if pub:
        linhas += ["", "TAGS:", ", ".join(pub["tags"])]
    intervalos = [c["inicio"] + c["duracao"] - c["interludio"]["seg"] for c in cenas
                  if c.get("interludio", {}).get("tipo") == "placa"]
    if intervalos:
        linhas += ["", "INTERVALOS PARA ANÚNCIOS (YouTube Studio → Monetização → Intervalos de anúncio → Adicionar):"]
        linhas += [f"{int(t) // 60}:{int(t) % 60:02d}" for t in intervalos]
    (projeto / "youtube.txt").write_text("\n".join(linhas) + "\n")
