"""Funções compartilhadas: caminhos, configuração, JSON, ffmpeg."""

import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
PROJETOS = RAIZ / "projetos"
PROMPTS = RAIZ / "prompts"
ESTRUTURAS = RAIZ / "estruturas"
RENDER = RAIZ / "render"


class EtapaPendente(Exception):
    """A etapa precisa de uma ação humana (ex.: colar a resposta de um prompt)."""


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def carregar_env() -> None:
    arquivo = RAIZ / ".env"
    if not arquivo.exists():
        return
    for linha in arquivo.read_text().splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        if valor.strip() and not os.environ.get(chave.strip()):
            os.environ[chave.strip()] = valor.strip().strip('"').strip("'")


def carregar_config() -> dict:
    carregar_env()
    return yaml.safe_load((RAIZ / "config.yaml").read_text())


def slugify(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return texto[:60] or "projeto"


def ler_json(caminho: Path):
    return json.loads(caminho.read_text())


def salvar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2))


def extrair_json(texto: str):
    """Pega o primeiro bloco JSON de uma resposta de LLM (com ou sem cerca ```json)."""
    cerca = re.search(r"```(?:json)?\s*(.*?)```", texto, re.S)
    bruto = cerca.group(1) if cerca else texto
    inicio = min((i for i in (bruto.find("{"), bruto.find("[")) if i >= 0), default=-1)
    if inicio < 0:
        raise ValueError("Nenhum JSON encontrado na resposta")
    return json.JSONDecoder().raw_decode(bruto[inicio:])[0]


def preencher(template: str, **variaveis) -> str:
    for chave, valor in variaveis.items():
        template = template.replace("{{" + chave + "}}", str(valor))
    return template


def rodar(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    resultado = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if resultado.returncode != 0:
        raise RuntimeError(f"Falhou: {' '.join(map(str, cmd[:3]))}…\n{resultado.stderr[-2000:]}")
    return resultado


def e_programa(config: dict) -> bool:
    """O projeto está no formato de programa de TV (abertura, vinheta, blocos com placa)."""
    return config.get("projeto", {}).get("formato") == "programa"


def versao_midias(props: dict, pasta: Path) -> str:
    """Data de cada mídia citada nas props: trocar o arquivo sem mudar o nome também invalida o render."""
    nomes = sorted(set(re.findall(r'"(media/[^"]+)"', json.dumps(props))))
    return "".join(f"{n}:{(pasta / n).stat().st_mtime_ns if (pasta / n).exists() else 0};" for n in nomes)


def duracao_midia(caminho: Path) -> float:
    saida = rodar(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=nw=1:nk=1", str(caminho)]).stdout
    return float(saida.strip())


def contar_palavras(texto: str) -> int:
    return len(texto.split())
