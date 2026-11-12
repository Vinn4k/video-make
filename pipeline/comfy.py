"""Cliente do ComfyUI que roda no PC da GPU.

Os workflows ficam em workflows/comfy/<nome>.json (formato API), cada um com um
<nome>.manifest.json dizendo em qual nó entra cada parâmetro e de qual nó sai o arquivo:

  {"inputs": {"text": "2.inputs.text", "seed": ["94.inputs.seed", "3.inputs.seed"]},
   "output": {"node": "3", "kind": "audio"}}

Formato de workflow exportado em "API format" do ComfyUI + manifesto de parâmetros.
"""

import json
import os
import time
from pathlib import Path

import requests

from .util import RAIZ

WORKFLOWS = RAIZ / "workflows" / "comfy"


class ComfyErro(RuntimeError):
    pass


def url() -> str:
    return os.environ.get("COMFY_URL", "").rstrip("/")


def online() -> bool:
    if not url():
        return False
    try:
        return requests.get(f"{url()}/system_stats", timeout=3).ok
    except requests.RequestException:
        return False


def opcoes(classe: str, entrada: str) -> list:
    """Valores aceitos por uma entrada de nó (ex.: arquivos em input/ ou checkpoints instalados)."""
    info = requests.get(f"{url()}/object_info/{classe}", timeout=15).json().get(classe, {})
    spec = {**info.get("input", {}).get("required", {}), **info.get("input", {}).get("optional", {})}.get(entrada)
    if not spec:
        return []
    # formato antigo: [["a", "b"], {...}]; novo: ["COMBO", {"options": [...]}]
    return spec[0] if isinstance(spec[0], list) else spec[1].get("options", [])


def enviar(arquivo: Path, nome: str) -> None:
    """Envia um arquivo para a pasta input/ do ComfyUI."""
    with open(arquivo, "rb") as f:
        r = requests.post(f"{url()}/upload/image", timeout=60,
                          files={"image": (nome, f)}, data={"type": "input", "overwrite": "true"})
    if not r.ok:
        raise ComfyErro(f"Falha ao enviar {nome} ao ComfyUI: HTTP {r.status_code}")


def rodar(nome: str, parametros: dict, destino: Path | None = None, timeout: int = 600) -> Path | str:
    """Executa um workflow. Saída de arquivo é salva em `destino` (a extensão vem do ComfyUI);
    saída de texto ("kind": "text") é devolvida como string."""
    grafo = json.loads((WORKFLOWS / f"{nome}.json").read_text())
    manifesto = json.loads((WORKFLOWS / f"{nome}.manifest.json").read_text())
    for chave, valor in parametros.items():
        alvos = manifesto["inputs"].get(chave)
        if alvos is None:
            raise ComfyErro(f'Workflow "{nome}" não tem a entrada "{chave}".')
        for alvo in alvos if isinstance(alvos, list) else [alvos]:
            no, _, campo = alvo.split(".")
            grafo[no]["inputs"][campo] = valor

    r = requests.post(f"{url()}/prompt", json={"prompt": grafo, "client_id": "video-make"}, timeout=30)
    if not r.ok:
        raise ComfyErro(f'ComfyUI recusou o workflow "{nome}": {r.text[:800]}')
    prompt_id = r.json()["prompt_id"]

    saida = manifesto["output"]
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        time.sleep(1)
        entrada = requests.get(f"{url()}/history/{prompt_id}", timeout=30).json().get(prompt_id)
        if not entrada:
            continue
        status = entrada.get("status", {})
        if status.get("status_str") == "error":
            raise ComfyErro(f'Workflow "{nome}" falhou: {json.dumps(status.get("messages"))[:800]}')
        arquivos = entrada.get("outputs", {}).get(saida["node"], {}).get(saida["kind"])
        if not arquivos:
            if status.get("status_str") == "success":
                raise ComfyErro(f'Workflow "{nome}" terminou sem saída no nó {saida["node"]}.')
            continue
        if saida["kind"] == "text":
            return arquivos[0]
        arq = arquivos[0]
        r = requests.get(f"{url()}/view", timeout=120, params={
            "filename": arq["filename"], "subfolder": arq["subfolder"], "type": arq["type"]})
        r.raise_for_status()
        caminho = destino.with_suffix(Path(arq["filename"]).suffix or ".wav")
        caminho.write_bytes(r.content)
        return caminho
    raise ComfyErro(f'Workflow "{nome}" passou de {timeout} s.')
