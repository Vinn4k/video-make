"""Chamada ao modelo de linguagem.

Dois provedores:
- anthropic: chama a API do Claude (precisa de ANTHROPIC_API_KEY).
- manual: grava o prompt em projetos/<slug>/prompts/ e para. Você cola o prompt
  no Claude (claude.ai ou Claude Code), salva a resposta no arquivo indicado e
  roda de novo. Útil para testar sem chave ou revisar cada etapa.
"""

import os
from pathlib import Path

from .util import EtapaPendente, log


def provedor(config: dict) -> str:
    escolhido = config["llm"]["provedor"]
    if escolhido == "auto":
        return "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "manual"
    return escolhido


def gerar(config: dict, prompt: str, *, projeto: Path, etapa: str, saida: Path,
          system: str | None = None) -> str:
    """Devolve a resposta do modelo. No modo manual, a resposta é o conteúdo de `saida`."""
    if provedor(config) == "manual":
        return _manual(prompt, projeto=projeto, etapa=etapa, saida=saida, system=system)
    return _anthropic(config, prompt, system)


def _manual(prompt, *, projeto, etapa, saida, system):
    resposta = saida.with_suffix(saida.suffix + ".resposta")
    if resposta.exists():
        return resposta.read_text()
    pasta = projeto / "prompts"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"{etapa}.md"
    corpo = (f"<instrucoes_de_sistema>\n{system}\n</instrucoes_de_sistema>\n\n" if system else "") + prompt
    arquivo.write_text(corpo)
    raise EtapaPendente(
        f"Modo manual: cole o conteúdo de\n    {arquivo}\n"
        f"  no Claude e salve a resposta completa em\n    {resposta}\n"
        f"  Depois rode o mesmo comando de novo."
    )


def _anthropic(config, prompt, system):
    import anthropic

    client = anthropic.Anthropic()
    log(f"Chamando {config['llm']['modelo']}…")
    parametros = dict(
        model=config["llm"]["modelo"],
        max_tokens=64000,
        thinking={"type": "adaptive"},
        output_config={"effort": config["llm"]["esforco"]},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    )
    if system:
        parametros["system"] = system
    with client.beta.messages.stream(**parametros) as stream:
        mensagem = stream.get_final_message()
    if mensagem.stop_reason == "refusal":
        raise RuntimeError("O modelo recusou a solicitação.")
    if mensagem.stop_reason == "max_tokens":
        raise RuntimeError("Resposta cortada por limite de tokens; divida a etapa em partes menores.")
    return "".join(bloco.text for bloco in mensagem.content if bloco.type == "text")
