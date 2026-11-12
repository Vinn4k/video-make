"""Trilha instrumental gerada no ComfyUI com ACE-Step 1.5 (Apache-2.0, sem direitos autorais)."""

from pathlib import Path

from . import comfy
from .util import RAIZ, log, rodar, slugify

MODELO = "ace_step_1.5_turbo_aio.safetensors"


def gerar(config: dict) -> Path | None:
    c = config["musica"]
    if not c.get("gerar") or not comfy.online():
        return None
    if MODELO not in comfy.opcoes("CheckpointLoaderSimple", "ckpt_name"):
        log("ACE-Step não está instalado no ComfyUI (Templates → Audio → ACE-Step 1.5 Music Generation AIO); "
            "seguindo sem música")
        return None
    pasta = RAIZ / "assets" / "musica"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"ace-{slugify(c['estilo'])[:40]}.m4a"
    log(f"Gerando trilha de {c['duracao_seg']} s com ACE-Step (pode levar alguns minutos)…")
    bruto = comfy.rodar("musica_ace15", {
        "tags": c["estilo"], "lyrics": "[Instrumental]", "bpm": c["bpm"], "keyscale": c["tom"],
        "duration": float(c["duracao_seg"]), "seed": c.get("semente", 7),
    }, pasta / "ace-bruto", timeout=900)
    rodar(["ffmpeg", "-y", "-v", "error", "-i", str(bruto), "-c:a", "aac", "-b:a", "192k", str(destino)])
    bruto.unlink()
    return destino
