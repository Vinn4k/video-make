#!/usr/bin/env python3
"""Gerador de vídeos longos para YouTube.

Exemplos:
  .venv/bin/python run.py --referencia transcricao.txt --modo novo_angulo
  .venv/bin/python run.py --referencia "https://youtube.com/watch?v=..." --modo outro_tema --tema "Baía de Guanabara"
  .venv/bin/python run.py --referencia ref.txt --tema "Linha 6 do metrô" --duracao 15 --lugar "São Paulo, Brazil"
  .venv/bin/python run.py --projeto meu-video --ate cenas     # continua um projeto e para depois da decupagem
  .venv/bin/python run.py --projeto meu-video --so publicacao # refaz só títulos e thumbs
  .venv/bin/python run.py --projeto meu-video --so shorts     # cortes verticais do vídeo pronto
  .venv/bin/python run.py --projeto meu-video --so youtube    # mostra a agenda; com --confirmar, envia e agenda
  .venv/bin/python run.py --projeto meu-video --so instagram  # os Shorts como Reels (Zernio); com --confirmar, agenda
  .venv/bin/python run.py --projeto meu-video --so metricas   # números do YouTube de cada vídeo e Short do projeto

Cada etapa salva seus arquivos em projetos/<slug>/ e é pulada se o arquivo já existir.
Modo, tema, duração e lugar ficam em projetos/<slug>/projeto.json: passe só na primeira vez (ou para mudar).
Para refazer uma etapa, apague o arquivo dela (ex.: roteiro.md) e rode de novo.
"""

import argparse
import os
import sys
import time
from pathlib import Path

# temporários (quadros do Remotion, áudio, ffmpeg) no disco do projeto: o disco do sistema do Mac lota
# e um render de capítulo chega a gastar mais de 1 GB ali ("No space left on device" no meio do render)
TEMPORARIOS = Path(__file__).resolve().parent / ".tmp"
TEMPORARIOS.mkdir(exist_ok=True)
os.environ["TMPDIR"] = str(TEMPORARIOS)

from pipeline import (decupagem, instagram, metricas, midia, montagem, publicacao, referencia, roteiro, shorts,
                      telegram, tendencias, tts, youtube)
from pipeline.util import PROJETOS, EtapaPendente, carregar_config, ler_json, salvar_json, slugify

ETAPAS = ["analise", "roteiro", "cenas", "narracao", "midia", "video", "publicacao", "shorts"]
# fora da sequência: publica para fora, então só roda pedido com --so (e só envia com --confirmar)
AVULSAS = ["youtube", "instagram", "metricas", "tendencias"]
# rodada que levou pelo menos isso avisa no Telegram ao terminar, parar ou falhar (a curta você está vendo)
AVISO_APOS_S = 120


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--referencia", help="arquivo .txt com a transcrição ou link do YouTube")
    p.add_argument("--modo", choices=list(roteiro.MODOS), help="padrão: novo_angulo (fica salvo no projeto)")
    p.add_argument("--tema", help="tema ou ângulo do vídeo novo (fica salvo no projeto)")
    p.add_argument("--duracao", type=float, help="duração alvo em minutos (padrão: video.duracao_alvo_min; fica salva)")
    p.add_argument("--formato", choices=["programa", "documentario"],
                   help="programa de TV (abertura, vinheta, blocos) ou documentário contínuo (padrão: video.formato; fica salvo)")
    p.add_argument("--lugar", help='onde a história se passa, em inglês (ex.: "São Paulo, Brazil"): entra nas buscas '
                                    "de mídia e faz a visão recusar imagens de outro país (fica salvo)")
    p.add_argument("--projeto", help="nome (slug) do projeto; padrão: derivado do tema ou do arquivo")
    p.add_argument("--ate", choices=ETAPAS, default=ETAPAS[-1], help="última etapa a rodar")
    p.add_argument("--so", choices=ETAPAS + AVULSAS,
                   help="roda só esta etapa (ex.: --so publicacao para refazer títulos e thumbs; --so youtube para agendar)")
    p.add_argument("--confirmar", action="store_true", help="com --so youtube ou instagram: envia de verdade (sem ele, só mostra a agenda)")
    p.add_argument("--inicio", help="com --so youtube: primeiro dia da agenda; com --so instagram: primeiro dia da fila dos Shorts "
                                    "que já saíram no YouTube (AAAA-MM-DD; padrão: amanhã)")
    p.add_argument("--reagendar", nargs="+", metavar="ITEM=DATA",
                   help="com --so youtube ou instagram: muda a data de itens já enviados (ex.: short_01=2026-10-28T18:00)")
    p.add_argument("--substituir", nargs="+", metavar="ITEM",
                   help="com --so youtube: sobe de novo estes itens já enviados (video, short_01…) na mesma data e "
                        "apaga o envio antigo depois que o novo subir")
    p.add_argument("--itens", nargs="+", metavar="SHORT",
                   help="com --so instagram: agenda só estes Shorts (ex.: short_01 short_03); com --so youtube: só "
                        "envia e comenta estes itens (ex.: video)")
    p.add_argument("--voz", choices=["comfyui", "google", "openai", "elevenlabs", "macos"],
                   help="força um provedor de voz (sobrepõe tts.provedor do config.yaml)")
    args = p.parse_args()

    config = carregar_config()
    if args.voz:
        config["tts"]["provedor"] = args.voz
    nome = args.projeto or slugify(args.tema or (args.referencia or "").rsplit("/", 1)[-1].rsplit(".", 1)[0])
    projeto = PROJETOS / nome
    projeto.mkdir(parents=True, exist_ok=True)
    if not (projeto / "referencia.txt").exists() and not args.referencia and args.so not in AVULSAS:
        sys.exit(f"Projeto {nome} não tem referencia.txt. Passe --referencia.")
    if args.referencia:
        referencia.importar(args.referencia, projeto)
    dados = _dados_projeto(projeto, args, config)
    config["video"]["duracao_alvo_min"] = dados["duracao_min"]
    config["projeto"] = dados

    passos = {
        "analise": lambda: referencia.analisar(config, projeto),
        "roteiro": lambda: roteiro.gerar(config, projeto, dados["modo"], dados["tema"]),
        "cenas": lambda: decupagem.gerar(config, projeto),
        "narracao": lambda: tts.gerar(config, projeto),
        "midia": lambda: midia.gerar(config, projeto),
        "video": lambda: montagem.gerar(config, projeto),
        "publicacao": lambda: publicacao.gerar(config, projeto),
        "shorts": lambda: shorts.gerar(config, projeto),
        "metricas": lambda: metricas.gerar(config, projeto),
        "tendencias": lambda: tendencias.gerar(config, projeto),
        "youtube": lambda: youtube.enviar(config, projeto, args.confirmar, args.inicio, args.substituir, args.reagendar,
                                          args.itens),
        "instagram": lambda: instagram.enviar(config, projeto, args.confirmar, args.inicio, args.reagendar, args.itens),
    }
    print(f"Projeto: projetos/{nome} ({dados['formato']}, {dados['modo']}, {dados['duracao_min']:g} min"
          + (f", {dados['lugar']}" if dados["lugar"] else "") + ")")
    etapas = [args.so] if args.so else ETAPAS[: ETAPAS.index(args.ate) + 1]
    inicio = time.monotonic()
    etapa = etapas[0]
    try:
        for etapa in etapas:
            print(f"[{etapa}]")
            passos[etapa]()
    except EtapaPendente as pendencia:
        print(f"\n⏸  {pendencia}")
        _avisar(inicio, f"⏸ {nome} parou em [{etapa}]: {pendencia}")
        sys.exit(2)
    except Exception as erro:
        _avisar(inicio, f"❌ {nome} falhou em [{etapa}]: {type(erro).__name__}: {erro}")
        raise
    _avisar_pronto(inicio, nome, projeto, etapas)


def _avisar(inicio: float, texto: str, foto: Path | None = None) -> None:
    if time.monotonic() - inicio >= AVISO_APOS_S:
        telegram.enviar(f"{texto}\n({(time.monotonic() - inicio) / 60:.0f} min)", foto)


def _avisar_pronto(inicio: float, nome: str, projeto: Path, etapas: list[str]) -> None:
    """Fim da rodada: diz até onde chegou e, se as thumbs saíram, manda a A junto."""
    texto = f"✅ {nome}: {' → '.join(etapas)} pronto"
    final = projeto / "video_final.mp4"
    if "video" in etapas and final.exists():
        texto += f"\nVídeo: projetos/{nome}/video_final.mp4 ({final.stat().st_size / 1e9:.1f} GB)"
    if "shorts" in etapas and (projeto / "shorts").exists():
        texto += f"\nShorts: {len(list((projeto / 'shorts').glob('short_??.mp4')))}"
    thumb = projeto / "thumbs" / "thumb_A.png"
    _avisar(inicio, texto, thumb if "publicacao" in etapas and thumb.exists() else None)


def _dados_projeto(projeto, args, config) -> dict:
    """Modo, tema, duração e lugar do projeto: o que veio na linha de comando vale e fica salvo para as próximas rodadas."""
    arquivo = projeto / "projeto.json"
    dados = ler_json(arquivo) if arquivo.exists() else {}
    for chave, valor in (("modo", args.modo), ("tema", args.tema), ("duracao_min", args.duracao), ("lugar", args.lugar),
                         ("formato", args.formato)):
        if valor is not None:
            dados[chave] = valor
    dados.setdefault("modo", "novo_angulo")
    dados.setdefault("tema", "")
    dados.setdefault("duracao_min", config["video"]["duracao_alvo_min"])
    dados.setdefault("lugar", "")
    # projeto com roteiro de antes do formato programa continua documentário
    dados.setdefault("formato", "documentario" if (projeto / "roteiro.md").exists() else config["video"].get("formato", "documentario"))
    salvar_json(arquivo, dados)
    return dados


if __name__ == "__main__":
    main()
