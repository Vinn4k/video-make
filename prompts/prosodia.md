Você prepara narrações de documentário para uma voz sintética expressiva (Gemini TTS). Para cada cena abaixo, escreva a `fala`: o mesmo texto, com marcas de interpretação, para a voz soar como um narrador humano envolvente.

Regras:
- **Não mude, não acrescente e não tire nenhuma palavra.** Só pode mexer na pontuação, em maiúsculas e inserir as tags abaixo.
- Pontuação prosódica: reticências para suspense ("e então... a resposta apareceu"), travessão para uma pausa de virada, vírgulas para respirar, ponto de exclamação só quando houver surpresa real.
- Ênfase: escreva em MAIÚSCULAS no máximo uma ou duas palavras-chave por cena, as que um narrador acentuaria.
- Tags permitidas (em inglês, entre sinais de menor e maior), **sempre no começo ou no meio da fala, nunca no fim**: uma tag no fim do texto, sem nada depois, é lida em voz alta ("longa pausa", medido no vídeo do Rodoanel Norte em 31/10/2026).
  - `<breath>`: respiração audível. **No máximo uma a cada 30 cenas (cerca de uma por minuto)**, só onde um narrador de verdade tomaria fôlego: na frase de volta de um bloco ou antes de uma revelação longa. Nunca em cena seguida de outra com `<breath>`, nunca em pedido de like ou comentário. Em 05/11/2026 o público reclamou de "muita respiração" (o vídeo de Gizé saiu com 68 em 20 min, uma a cada 17 s); o código corta o excesso, mas marque pouco desde o início. Para humanizar, prefira vírgulas, ênfases e uma `<short pause>` bem colocada.
  - `<short pause>`: antes de uma revelação, depois de dois-pontos que anunciam algo, entre uma frase curta de impacto e a seguinte. Ponto final já pausa: não ponha `<short pause>` depois de todo ponto.
  - `<long pause>`: raro, antes de uma virada grande da história, sempre seguido de texto.
  - `<sigh>`: antes de uma constatação amarga ou de frustração. `<chuckle>`: no meio da frase, numa ironia de verdade.
- **Reticências e vírgulas quebram a fala: analise antes de pôr.** Só use reticências onde um narrador humano seguraria o suspense ("E então... chegou junho de 2018", "em cima deles... não tem NADA"). Nunca no meio de um sintagma que corre junto: entre verbo e complemento, antes de um adjunto curto ("a mata fechando a entrada... aos poucos" soou estranho), entre preposição e nome ("um filme de... ficção científica"), antes de uma oração relativa ("um prédio... que teve"). Na dúvida, deixe a frase corrida.
- Uma pausa logo antes de uma expressão às vezes faz a voz pular a expressão ("respondida: <short pause> quando, afinal" saiu sem o "quando, afinal" duas vezes). Depois de dois-pontos, a pausa dos dois-pontos já basta na maioria dos casos.
- Pedidos de inscrição e comentário: tom mais próximo e leve, sem reticências dramáticas.

<cenas>
{{cenas}}
</cenas>

Responda **apenas** com um bloco ```json:

```json
{"falas": [{"id": 1, "fala": "texto com marcas"}]}
```
