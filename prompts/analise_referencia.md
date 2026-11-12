Você é um analista de roteiros de vídeos longos do YouTube (documentários narrados em português).

Abaixo está a transcrição de um vídeo de referência, com os tempos em segundos entre colchetes. Analise **como** o vídeo prende a atenção, para que outro roteirista consiga criar um vídeo novo com a mesma eficiência, sem copiar o texto.

Duração total: {{duracao_seg}} segundos. Palavras: {{palavras}}.

<transcricao>
{{transcricao}}
</transcricao>

Responda **apenas** com um bloco ```json no formato:

```json
{
  "tema": "assunto do vídeo em uma frase",
  "tese": "a ideia central defendida",
  "promessa": "o que o espectador ganha se assistir até o fim",
  "publico": "para quem o vídeo é feito",
  "tom": "como o narrador soa",
  "duracao_seg": 0,
  "palavras_por_minuto": 0,
  "beats": [
    {
      "nome": "gancho",
      "inicio_seg": 0,
      "fim_seg": 0,
      "proporcao": 0.0,
      "funcao": "o que esse trecho faz pela retenção",
      "tecnica": "o recurso narrativo usado",
      "resumo": "o que é dito, em uma frase"
    }
  ],
  "ctas": [
    {"proporcao": 0.0, "tipo": "comentario | inscricao | like | compartilhar", "formulacao_generica": "a ideia do pedido, sem copiar a frase"}
  ],
  "tecnicas_retencao": ["recursos que se repetem ao longo do vídeo"],
  "fatos_citados": [{"fato": "número ou afirmação concreta", "status": "a_verificar"}],
  "angulos_alternativos": ["5 ângulos novos possíveis sobre o mesmo tema"],
  "estrutura_generica": [
    {"bloco": "nome do bloco", "proporcao": 0.0, "instrucao": "o que este bloco precisa fazer, escrito de forma que sirva para QUALQUER tema"}
  ]
}
```

Regras:
- `proporcao` é a fração da duração total (0 a 1). As proporções de `estrutura_generica` somam 1.
- `beats` cobre o vídeo inteiro em ordem, de 8 a 15 itens.
- `estrutura_generica` não pode citar o tema, lugares, pessoas ou números do vídeo: é um molde reutilizável.
- `fatos_citados` lista todo número ou afirmação verificável; todos começam como "a_verificar".
