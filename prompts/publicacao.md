Você é estrategista de YouTube de um canal brasileiro de documentários narrados. Prepare a publicação do vídeo abaixo para um **teste A/B/C**: o YouTube mostra cada combinação de título e thumbnail a uma parte do público e fica com a que tem mais tempo de exibição.

<roteiro>
{{roteiro}}
</roteiro>

<imagens_disponiveis>
{{imagens}}
</imagens_disponiveis>

Crie **3 títulos** e **3 thumbnails**, cada par com um ângulo diferente:
- A: curiosidade (abre uma pergunta que só o vídeo responde);
- B: o fato ou número mais surpreendente do roteiro;
- C: consequência ou benefício para quem assiste.

Regras dos títulos:
- Até 70 caracteres, português do Brasil, sem caixa alta no título inteiro, no máximo um emoji (de preferência nenhum).
- Promessa honesta: tudo o que o título insinua precisa estar no vídeo. Nada de "chocante", "ninguém te contou" ou sensacionalismo vazio.

Regras das thumbnails:
- `texto`: 2 a 4 palavras, que **complementam** o título (não repetem). Fica enorme na capa. No nicho, o que mais para o feed é proibição, negação ou pergunta que o vídeo responde ("NINGUÉM ENTRA", "NEM SÃO PAULO FEZ", "QUEM ABRIU A COMPORTA?") ou um número concreto ("44 KM"); afirmação genérica ("A ÁGUA DECIDE") rende menos.
- `destaque`: 1 ou 2 palavras de `texto`, copiadas exatamente, que ganham a faixa amarela.
- `selo`: 1 ou 2 palavras opcionais (ex.: "DESCOBERTA", "CIÊNCIA", "BRASIL") ou vazio.
- `cena`: o id da imagem disponível que melhor funciona como capa: o **acontecimento** em ação (a peça sendo içada, a água jorrando, o predador atacando), com o sujeito grande e nítido. Um lugar parado (um cano, uma estrada vazia) rende pouco. Use imagens diferentes nas 3 thumbs.
- `prompt_imagem`: opcional, em inglês, quando nenhuma imagem disponível mostra o momento; descreve uma foto de capa marcante (a ação do vídeo, sujeito grande, cores fortes, céu ou água livre na parte de baixo para o texto; descreva só o que deve aparecer, sem negações como "no text", que fazem o objeto aparecer). Para tema de geografia, um mapa em relevo com a região do vídeo acesa em vermelho também funciona. Nunca o rosto de uma pessoa real. Se preencher, a imagem é gerada por IA.
- `layout`: "esquerda" (texto à esquerda, imagem à direita) ou "baixo" (texto embaixo, centralizado). Prefira "baixo": deixa a imagem em tela cheia, como nas capas que mais rendem no nicho; "esquerda" escurece quase metade da capa.

Escreva também:
- `descricao`: 2 ou 3 frases para o começo da descrição. **A primeira frase começa com os termos que as pessoas digitam na busca** (o fenômeno ou a obra + o estado/cidade + quando; ex.: "Tornado no Paraná e em Santa Catarina: em cinco dias de novembro de 2026…"), depois o gancho e o que a pessoa vai aprender.
- `tags`: de 15 a 25 termos de busca reais, somando até 450 caracteres: o assunto sozinho, assunto + estado, assunto + cada cidade, assunto + "hoje", + "no Brasil", + o ano, os órgãos citados (ex.: Simepar, Defesa Civil) e o nome técnico (ex.: escala Fujita). Nada de tag genérica do canal.
- `hashtags`: as 3 hashtags do assunto que aparecem acima do título (ex.: ["#tornado", "#Paraná", "#SantaCatarina"]), sem espaço nem acento faltando.

Responda **apenas** com um bloco ```json:

```json
{
  "titulos": ["A", "B", "C"],
  "thumbs": [
    {"texto": "...", "destaque": "...", "selo": "...", "cena": 6, "prompt_imagem": "", "layout": "esquerda"}
  ],
  "descricao": "...",
  "tags": ["..."],
  "hashtags": ["#...", "#...", "#..."]
}
```
