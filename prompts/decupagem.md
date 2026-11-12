Você é editor de vídeo de um canal de documentários narrados. Divida o roteiro abaixo em cenas e decida o visual de cada uma.

<roteiro>
{{roteiro}}
</roteiro>

Cada cena tem de 12 a 22 palavras de narração (≈ 5 a 9 segundos). O campo `texto` deve ser a narração **exata**, sem alterar nenhuma palavra; juntando os `texto` em ordem, o roteiro tem que sair inteiro e na mesma ordem. Corte em finais de frase ou vírgulas.

## Mídia (vale para todo tipo que mostra foto ou vídeo)

- `visual`: o que deve aparecer, em português.
- `busca`: 2 a 4 buscas curtas em **inglês**, da mais específica para a mais genérica, com substantivos concretos que existam em bancos de imagem (ex.: "mealworm larvae", "styrofoam waste", "laboratory petri dish").
- `prompt_imagem`: descrição em inglês, de 20 a 40 palavras, de uma **fotografia** realista para essa cena, usada se o banco de imagens não tiver nada bom (assunto, enquadramento, luz, ambiente). Descreva **só o que deve aparecer**, nunca com negação ("no toll booths", "no text", "without signs"): o gerador desenha tudo o que é citado, e a negação faz o objeto aparecer. Para evitar letreiros, peça superfícies lisas ("blank walls", "the front display is dark").
- `preferencia`: "video" para ação e ambiente, "foto" para objetos, pessoas e ciência, "ia" quando a cena é hipotética, microscópica ou impossível de existir em banco (ex.: "caminhão despejando bactérias num rio").

{{lugar}}

{{formato}}

## Tipos de cena

- `midia`: foto ou vídeo em tela cheia. É o tipo mais comum.
- `frase_impacto`: tela escura com frase curta em destaque, nas afirmações mais fortes. Preencha `frase`: `texto` (até 9 palavras, adaptado da narração), `destaque` (2 a 4 palavras de `texto`, copiadas exatamente), `rotulo` (1 a 3 palavras).
- `grafico`: quando a narração compara 2 a 6 números da mesma grandeza (no tempo ou entre categorias). Preencha `grafico`: `titulo` (até 5 palavras), `unidade` ("km", "%", "toneladas"… ou vazio), `formato` ("linha" para evolução no tempo, "barras" para comparação), `pontos` ([["rótulo", valor numérico], …]). Use **só** números ditos na narração.
- `numero_destaque`: quando a narração traz um número marcante. Preencha `numero`: `numero` (como deve aparecer, ex.: "90%", "1.000.000", "3 semanas") e `texto` (até 8 palavras que explicam o número). Também leva mídia de fundo.
- `split_topicos`: quando a narração lista 2 a 4 itens, resultados ou características. Preencha `split`: `titulo` (até 4 palavras) e `topicos` (2 a 4, até 6 palavras cada). Também leva mídia (aparece à esquerda).
- `fluxo`: quando a narração descreve um processo ou uma cadeia de 2 a 4 etapas. Preencha `fluxo`: `titulo` (até 5 palavras, opcional) e `etapas`: [{"rotulo": "1 ou 2 palavras", "busca": ["..."], "prompt_imagem": "..."}]. A cena em si não leva `busca`.
- `manchete`: quando a narração apresenta uma descoberta ou um acontecimento datado. Preencha `manchete`: `titulo` (até 12 palavras, em tom de notícia) e `subtitulo` (lugar e ano, ou instituição). Também leva mídia de fundo.

Ritmo: depois de 3 a 6 cenas `midia`, use um dos outros tipos; varie, nunca repita o mesmo tipo especial duas vezes seguidas, e não ponha dois tipos especiais um logo após o outro.

Sobreposições opcionais, só em cenas `midia` (`overlay`):
- `{"tipo": "titulo_capitulo", "titulo": "..."}`: obrigatório na primeira cena de cada capítulo (título curto, até 4 palavras). Prefira um visual amplo (paisagem, cidade, laboratório) nessa cena.
- `{"tipo": "escalada", "titulo": "..."}`: só no formato programa, nas frases da escalada da abertura (veja acima).
- `{"tipo": "lower_third", "titulo": "..."}`: até 4 palavras nomeando o lugar, a espécie ou o conceito que aparece. No máximo uma a cada 4 cenas.

Marque `"cta": true` nas cenas em que a narração pede inscrição, like ou comentário.

Responda **apenas** com um bloco ```json. Inclua em cada cena só os campos do seu tipo:

```json
{
  "cenas": [
    {
      "capitulo": 1,
      "texto": "narração exata",
      "tipo": "midia",
      "visual": "descrição",
      "busca": ["query one", "query two"],
      "prompt_imagem": "realistic documentary photograph of ...",
      "preferencia": "video",
      "overlay": null,
      "cta": false
    },
    {
      "capitulo": 1,
      "texto": "narração exata",
      "tipo": "numero_destaque",
      "visual": "descrição", "busca": ["..."], "prompt_imagem": "...", "preferencia": "foto",
      "numero": {"numero": "90%", "texto": "do plástico desmontado em dez horas"},
      "cta": false
    }
  ]
}
```

`capitulo` é o número do capítulo (1, 2, 3…) na ordem do roteiro.
