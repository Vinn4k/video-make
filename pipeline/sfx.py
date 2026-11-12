"""Efeitos sonoros nos momentos de revelação do vídeo longo, sintetizados no ffmpeg.

Não são voz nem música: são expressões e ruído filtrado (custo zero, sem misturar vozes com a narração).
Os sons ficam em assets/sfx/<nome>_gerado.wav; ponha <nome>.wav/.mp3 na mesma pasta para trocar por um próprio.

As deixas saem sozinhas do tipo da cena (número em destaque, frase de impacto, manchete) e são
espaçadas por `sfx.intervalo_min_seg` para não virar tique. Para forçar ou calar uma cena, ponha
`"sfx": "impacto"` (ou outro nome de SONS) ou `"sfx": false` nela no cenas.json.
"""

from pathlib import Path

from .util import RAIZ, log, rodar

TAXA = 48000

# nome -> filtro lavfi que gera o som pronto (os mesmos usados nos motions, render/motion/montar.py)
SONS = {
    "whoosh": "anoisesrc=d=0.7:c=pink:a=0.9,bandpass=f=1400:width_type=o:w=2.5,afade=t=in:d=0.3:curve=qsin,afade=t=out:st=0.3:d=0.4,volume=0.9",
    "tick": "aevalsrc='0.35*sin(2*PI*2600*t)*exp(-160*t)':d=0.05",
    "impacto": "aevalsrc='0.95*sin(2*PI*(42+70*exp(-18*t))*t)*exp(-4.5*t)+0.35*(2*random(0)-1)*exp(-45*t)':d=1.4",
    "impacto_leve": "aevalsrc='0.5*sin(2*PI*(80+120*exp(-25*t))*t)*exp(-9*t)':d=0.5",
    "riser": "anoisesrc=d=0.75:c=white:a=0.5,highpass=f=1800,volume='0.05+t*1.1':eval=frame,afade=t=out:st=0.65:d=0.1",
    "pop": "aevalsrc='0.4*sin(2*PI*(500+1100*exp(-30*t))*t)*exp(-22*t)':d=0.25",
    "motor": "aevalsrc='(0.10*sin(2*PI*95*t)+0.05*sin(2*PI*190*t)+0.03*sin(2*PI*285*t))*(1+0.4*sin(2*PI*9*t))':d=2.6,afade=t=in:d=0.2,afade=t=out:st=2.3:d=0.3",
    "clique": "aevalsrc='0.5*(2*random(1)-1)*exp(-120*t)':d=0.06",
    "bip": "aevalsrc='0.22*sin(2*PI*1760*t)*(lt(t,0.09)+gte(t,0.15)*lt(t,0.24))':d=0.26",
    "risco": "anoisesrc=d=1.35:c=white:a=0.25,bandpass=f=3200:width_type=o:w=1.2,tremolo=f=14:d=0.6,afade=t=in:d=0.1,afade=t=out:st=1.15:d=0.2",
    "corte": "aevalsrc='0.6*sin(2*PI*(70+90*exp(-20*t))*t)*exp(-8*t)+0.3*(2*random(2)-1)*exp(-70*t)':d=0.6",
    "baque": "aevalsrc='0.9*sin(2*PI*(38+60*exp(-14*t))*t)*exp(-6*t)+0.25*(2*random(3)-1)*exp(-30*t)':d=1.0",
    "ronco": "anoisesrc=d=2.4:c=brown:a=0.9,lowpass=f=160,afade=t=in:d=0.4,afade=t=out:st=1.8:d=0.6,volume=1.4",
    # graves puros (abaixo de ~100 Hz, sem ruído): sentem-se no peito e não encobrem a voz, que fala por cima
    "sub_leve": "aevalsrc='0.9*sin(2*PI*(55+40*exp(-25*t))*t)*exp(-12*t)':d=0.35",
    "sub": "aevalsrc='0.95*sin(2*PI*(38+45*exp(-14*t))*t)*exp(-5*t)':d=0.9",
    # sopro macio de passagem de cena: só ar, curto, feito para caber na pausa entre duas falas
    "passagem": "anoisesrc=d=0.5:c=pink:a=0.6,bandpass=f=900:width_type=o:w=2,afade=t=in:d=0.2:curve=qsin,afade=t=out:st=0.2:d=0.3,volume=0.8",
    "carimbo": "aevalsrc='0.95*sin(2*PI*(50+90*exp(-28*t))*t)*exp(-6*t)+0.55*(2*random(4)-1)*exp(-35*t)':d=1.1",
}

# tipo de cena -> [(som, deslocamento em segundos em relação ao início da cena, ganho 0–1)], na ordem de prioridade
POR_TIPO = {
    "frase_impacto": (3, [("sub", 0.0, 0.5)]),
    "numero_destaque": (2, [("sub_leve", 0.05, 0.45)]),
    "manchete": (1, [("tick", 0.0, 0.3)]),
}
GANHO_PASSAGEM = 0.35


def _arquivo(config: dict, nome: str) -> Path:
    """<nome>.wav/.mp3/.m4a da pasta sfx.pasta, ou o som sintetizado (criado na primeira vez)."""
    pasta = RAIZ / config["sfx"]["pasta"]
    pasta.mkdir(parents=True, exist_ok=True)
    proprio = sorted(p for p in pasta.glob(f"{nome}.*") if p.suffix.lower() in (".mp3", ".wav", ".m4a"))
    if proprio:
        return proprio[0]
    gerado = pasta / f"{nome}_gerado.wav"
    if not gerado.exists():
        rodar(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", SONS[nome], "-ar", str(TAXA), "-ac", "1", str(gerado)])
    return gerado


def _pausa_antes(cenas: list[dict], i: int) -> float:
    """Segundo em que a cena i pode receber um efeito sem pisar na voz: o silêncio entre a última palavra
    da cena anterior e a primeira desta. Sem tempos de palavra, usa o início da cena."""
    c = cenas[i]
    primeira = c["inicio"] + (c["palavras"][0][1] if c.get("palavras") else 0.0)
    if i == 0 or not cenas[i - 1].get("palavras"):
        return max(0.0, primeira - 0.05)
    anterior = cenas[i - 1]
    fim = anterior["inicio"] + anterior["palavras"][-1][2]
    # o grave cai logo antes do corte visual (0,25 s antes da 1ª palavra), sem entrar antes do fim da fala anterior
    return max(fim + 0.03, primeira - 0.25) if primeira - fim > 0.1 else max(0.0, primeira - 0.05)


def _primeira_fala(c: dict) -> float:
    return c["inicio"] + (c["palavras"][0][1] if c.get("palavras") else 0.0)


def _passagens(config: dict, cenas: list[dict], ocupados: list[float]) -> list[tuple[str, float, float, float | None]]:
    """Sopros macios nos cortes de cena que têm pausa de verdade (`gap_min_seg`), espaçados e longe das revelações.
    Cada sopro termina 0,04 s antes da próxima fala e é cortado para caber na pausa."""
    cfg = config["sfx"]["passagem"]
    if not cfg["ativo"]:
        return []
    saida, ultimo = [], -1e9
    for i in range(1, len(cenas)):
        a, b = cenas[i - 1], cenas[i]
        if b.get("sfx") is False or b["tipo"] in POR_TIPO and b["tipo"] != "manchete" or not a.get("palavras"):
            continue
        fim, primeira = a["inicio"] + a["palavras"][-1][2], _primeira_fala(b)
        pausa = primeira - fim
        if pausa < cfg["gap_min_seg"] or b["capitulo"] != a["capitulo"] or a.get("interludio"):
            continue
        if primeira - ultimo < cfg["intervalo_min_seg"] or any(abs(primeira - o) < cfg["longe_de_revelacao_seg"] for o in ocupados):
            continue
        dur = min(0.5, pausa - 0.06)
        saida.append(("passagem", primeira - 0.04 - dur, GANHO_PASSAGEM, dur))
        ultimo = primeira
    return saida


def deixas(config: dict, cenas: list[dict]) -> list[tuple[str, float, float, float | None]]:
    """(som, segundo, ganho, duração máxima) de cada efeito, já espaçados. Cena com `sfx` explícito sempre entra."""
    minimo = config["sfx"]["intervalo_min_seg"]
    candidatas = []  # (prioridade, início da cena, [(som, segundo, ganho, duração)])
    for i, c in enumerate(cenas):
        if c.get("sfx") is False:
            continue
        ponto = _pausa_antes(cenas, i)
        if isinstance(c.get("sfx"), str) and c["sfx"] in SONS:
            candidatas.append((9, c["inicio"], [(c["sfx"], ponto, 0.5, None)]))
        elif c["tipo"] in POR_TIPO:
            prioridade, sons = POR_TIPO[c["tipo"]]
            candidatas.append((prioridade, c["inicio"], [(s, max(0.0, ponto + d), g, None) for s, d, g in sons]))
    # escolhe por prioridade e descarta quem cair perto demais de uma já escolhida
    escolhidas: list[tuple[int, float, list]] = []
    for cand in sorted(candidatas, key=lambda x: (-x[0], x[1])):
        if cand[0] < 9 and any(abs(cand[1] - e[1]) < minimo for e in escolhidas):
            continue
        escolhidas.append(cand)
    revelacoes = [d for _, _, sons in sorted(escolhidas, key=lambda x: x[1]) for d in sons]
    todas = revelacoes + _passagens(config, cenas, [seg for _, seg, _, _ in revelacoes])
    return sorted(todas, key=lambda d: d[1])


def trilha(config: dict, cenas: list[dict], duracao: float, saida: Path) -> Path | None:
    """Trilha só de efeitos com a duração da narração, ou None se não há nenhuma deixa."""
    if not config["sfx"]["ativo"]:
        return None
    marcas = deixas(config, cenas)
    if not marcas:
        return None
    entradas, filtros = [], []
    for i, (nome, seg, ganho, dur) in enumerate(marcas):
        entradas += ["-i", str(_arquivo(config, nome))]
        corte = f"atrim=0:{dur:.3f},afade=t=out:st={max(0.0, dur - 0.12):.3f}:d=0.12," if dur else ""
        filtros.append(f"[{i}:a]aresample={TAXA},{corte}volume={ganho},adelay={round(seg * 1000)}:all=1[s{i}]")
    filtros.append("".join(f"[s{i}]" for i in range(len(marcas))) +
                   f"amix=inputs={len(marcas)}:normalize=0,apad=whole_dur={duracao:.3f},atrim=0:{duracao:.3f},"
                   f"volume={config['sfx']['volume']},alimiter=limit=0.9[a]")
    rodar(["ffmpeg", "-y", "-v", "error", *entradas, "-filter_complex", ";".join(filtros), "-map", "[a]",
           "-ar", str(TAXA), str(saida)])
    log(f"Efeitos sonoros: {sum(m[0] != 'passagem' for m in marcas)} revelações e {sum(m[0] == 'passagem' for m in marcas)} passagens de cena")
    return saida
