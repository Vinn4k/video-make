"""[2] Roteiro: escreve a narração a partir da análise da referência e checa cópia."""

import json
from pathlib import Path

from . import llm, referencia
from .util import PROMPTS, EtapaPendente, contar_palavras, e_programa, ler_json, log, preencher, salvar_json

MODOS = {
    "novo_angulo": "Mesmo tema da referência, com um ângulo novo: outro gancho, outra ordem, outros "
                   "exemplos e outro fechamento. Se o tema pedido estiver preenchido, ele define o ângulo.",
    "outro_tema": "Reaproveite apenas o esqueleto narrativo da referência. O assunto do vídeo é o tema pedido.",
    "aprofundar": "Escolha um trecho ou subtema da referência (o tema pedido, se houver) e transforme-o "
                  "no vídeo inteiro, aprofundando com informações que a referência não tem.",
}


def gerar(config: dict, projeto: Path, modo: str, tema: str) -> dict:
    roteiro_md = projeto / "roteiro.md"
    if not roteiro_md.exists():
        analise = ler_json(projeto / "referencia.json")
        duracao = config["video"]["duracao_alvo_min"]
        prompt = preencher(
            (PROMPTS / "roteiro_adaptacao.md").read_text(),
            modo_descricao=MODOS[modo],
            tema=tema or "(livre: escolha o melhor ângulo entre os sugeridos na análise)",
            analise=json.dumps(analise, ensure_ascii=False, indent=2),
            palavras_alvo=int(duracao * config["video"]["palavras_por_minuto"]),
            duracao_min=duracao,
            capitulos=_capitulos(config, duracao),
            formato=PROGRAMA if e_programa(config) else "",
        )
        resposta = llm.gerar(config, prompt, projeto=projeto, etapa="2_roteiro", saida=roteiro_md)
        roteiro_md.write_text(resposta.strip() + "\n")
    _checar_copia(config, projeto)
    roteiro = ler(roteiro_md)
    salvar_json(projeto / "roteiro.json", roteiro)
    palavras = sum(contar_palavras(c["texto"]) for c in roteiro["capitulos"])
    log(f"Roteiro: \"{roteiro['titulo']}\", {len(roteiro['capitulos'])} capítulos, {palavras} palavras "
        f"(≈ {palavras / config['video']['palavras_por_minuto']:.1f} min)")
    return roteiro


# quem assiste na TV da sala vê o vídeo como um programa: abertura com escalada, vinheta e blocos com intervalo
PROGRAMA = """## Formato: programa de TV

O público assiste principalmente na TV da sala. Escreva como um programa, não como um vídeo contínuo:
- **O primeiro capítulo é a abertura**, de 45 a 75 segundos: o gancho e, logo depois, a **escalada**, como num telejornal. O gancho é uma cena concreta já em andamento — o momento mais forte do vídeo, com lugar e ação ("Às três da manhã, o asfalto da marginal abriu") —, nunca contexto, apresentação do tema ou pergunta vaga. São 3 ou 4 frases curtas, cada uma anunciando um momento forte do programa sem entregar a resposta ("Neste programa: a estação de metrô a quarenta e sete metros da rua. A cratera que engoliu uma via expressa. E a rodovia que levou trinta anos para fechar."). A abertura termina na escalada, porque depois dela entra a vinheta do canal. Título da abertura: até 4 palavras.
- **Os capítulos seguintes são os blocos**, com tamanhos parecidos. O título de cada um é o nome do bloco (até 5 palavras) e aparece numa placa antes dele.
- **Cada bloco, menos o último, termina com uma chamada para o próximo**: uma frase que promete algo concreto do bloco seguinte ("Daqui a pouco: o dia em que a obra engoliu a marginal."). É ali que entra o intervalo.
- **Cada bloco, a partir do segundo, começa com uma frase de volta** que retoma o fio para quem chegou agora ou voltou do intervalo ("De volta à Linha 6, a obra que parou por quatro anos."). Uma frase só, sem resumir o bloco anterior.
- **Pedido de like ou inscrição:** nunca na abertura, que tem que ser rápida. Vai no fim do primeiro bloco, antes da chamada, e no fechamento. No formato programa, esta regra vale no lugar das proporções de CTA da referência.
"""


def _capitulos(config: dict, duracao: float) -> int:
    if e_programa(config):
        return 1 + max(2, round(duracao / config["programa"]["minutos_por_bloco"]))  # abertura + blocos
    return max(3, round(duracao / 4))


def ler(caminho: Path) -> dict:
    """Converte o roteiro.md em {titulo, capitulos: [{titulo, texto}], fontes}."""
    titulo, capitulos, fontes, atual = "", [], [], None
    for linha in caminho.read_text().splitlines():
        if linha.startswith("# "):
            titulo = linha[2:].strip()
        elif linha.startswith("## "):
            nome = linha[3:].strip()
            atual = None if nome.lower() in ("fontes", "referências", "referencias") else {"titulo": nome, "paragrafos": []}
            if atual is not None:
                capitulos.append(atual)
            else:
                atual = "fontes"
        elif atual == "fontes":
            if linha.strip().startswith("-"):
                fontes.append(linha.strip()[1:].strip())
        elif atual is not None and linha.strip():
            atual["paragrafos"].append(linha.strip())
    return {
        "titulo": titulo,
        "capitulos": [{"titulo": c["titulo"], "texto": " ".join(c["paragrafos"])} for c in capitulos],
        "fontes": fontes,
    }


def narracao(roteiro: dict) -> str:
    return " ".join(c["texto"] for c in roteiro["capitulos"])


def _checar_copia(config: dict, projeto: Path) -> None:
    limites = config["adaptacao"]
    ref = referencia.texto_referencia(projeto)
    for tentativa in range(limites["tentativas_reescrita"] + 1):
        roteiro_md = projeto / "roteiro.md"
        resultado = referencia.similaridade(narracao(ler(roteiro_md)), ref, limites["max_ngram_igual"])
        resultado["aprovado"] = (not resultado["trechos_copiados"]
                                 and resultado["sobreposicao_5gramas"] <= limites["max_sobreposicao"])
        salvar_json(projeto / "similaridade.json", resultado)
        log(f"Checagem anti-cópia: sobreposição {resultado['sobreposicao_5gramas']:.1%}, "
            f"{len(resultado['trechos_copiados'])} trecho(s) copiado(s)")
        if resultado["aprovado"]:
            return
        if tentativa == limites["tentativas_reescrita"]:
            break
        trechos = "\n".join(f"- {t}" for t in resultado["trechos_copiados"]) or \
            "- sobreposição geral alta: reformule as frases mais parecidas com a referência"
        prompt = preencher((PROMPTS / "reescrita.md").read_text(),
                           trechos=trechos, roteiro=roteiro_md.read_text())
        saida = projeto / f"roteiro_reescrita_{tentativa + 1}.md"
        resposta = llm.gerar(config, prompt, projeto=projeto, etapa=f"2b_reescrita_{tentativa + 1}", saida=saida)
        roteiro_md.write_text(resposta.strip() + "\n")
    raise EtapaPendente("O roteiro continua parecido demais com a referência (veja similaridade.json). "
                        "Edite roteiro.md à mão e rode de novo.")
