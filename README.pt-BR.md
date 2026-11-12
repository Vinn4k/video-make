# video make (Português)

> English documentation: [README.md](README.md). Esta versão em português é o resumo; o inglês é mais detalhado.


> Projeto em português do Brasil (prompts, config e mensagens). Foi feito para um canal dark de documentários, mas nada impede de adaptar para outro nicho ou idioma: troque os prompts em [`prompts/`](prompts) e o [`config.yaml`](config.yaml).

## Visão geral

```
transcrição ─► [analise] ─► [roteiro] ─► [cenas] ─► [narracao] ─► [midia] ─► [video]
               estrutura    texto novo    visual de    voz por      foto/vídeo   Remotion +
               e ganchos    + anti-cópia  cada cena    cena         por cena     ffmpeg
                                                                                   │
                                      [shorts] ◄─ [publicacao] ◄───────────────────┘
                                      3 cortes     3 títulos + 3 thumbs (A/B/C)
                                      verticais
                                          │
                              avulsas: youtube · instagram · metricas · tendencias
```

Cada etapa grava arquivos em `projetos/<nome>/` e **é pulada se o arquivo já existe**. Para refazer, apague o arquivo da etapa e rode de novo. Todos os arquivos intermediários são texto/JSON, então dá para revisar e editar à mão entre as etapas.

| Etapa | Módulo | Saída em `projetos/<nome>/` | Editável? |
|---|---|---|---|
| analise | `pipeline/referencia.py` | `referencia.json` | sim |
| roteiro | `pipeline/roteiro.py` | `roteiro.md` | sim, é o melhor ponto de revisão |
| cenas | `pipeline/decupagem.py` | `cenas.json` | sim: buscas, templates, frases |
| narracao | `pipeline/tts.py` | `audio/`, `narracao.wav` | refeita quando o texto muda |
| midia | `pipeline/midia.py` | `media/`, `creditos.json` | apague `media/cena_XXX.*` para buscar de novo |
| video | `pipeline/montagem.py` | `video_final.mp4`, `legendas.srt`, `youtube.txt` | — |
| publicacao | `pipeline/publicacao.py` | `publicacao.json`, `thumbs/` | sim |
| shorts | `pipeline/shorts.py` | `shorts/`, `shorts.json` | sim |

## Arquitetura

```
run.py                  orquestrador (CLI): decide quais etapas rodar e avisa no Telegram
config.yaml             toda a configuração (duração, voz, mídia, publicação…); segredos ficam no .env
pipeline/               uma etapa por módulo (Python)
  llm.py                provedor de LLM: API do Claude ou modo manual
  comfy.py              cliente do ComfyUI (workflows em workflows/comfy)
  tts.py                narração (Google Gemini TTS, ComfyUI/ChatterBox, OpenAI, ElevenLabs, macOS)
  midia.py              bancos de imagem + nota por visão + imagem por IA
  montagem.py           chama o Remotion e mixa o áudio com ffmpeg
  sfx.py / musica.py    efeitos sonoros sintetizados e trilha (ACE-Step)
  youtube.py            envio e agendamento pela YouTube Data API
  instagram.py          Reels pelo Zernio
  metricas.py / tendencias.py / painel.py   análise do canal e do nicho
  revisao_web.py / previa.py                revisão manual de mídia antes do render
prompts/                prompts do LLM (análise, roteiro, reescrita, decupagem, prosódia, publicação, shorts)
workflows/comfy/        workflows do ComfyUI (voz, imagem, vídeo, música, visão) + manifestos de parâmetros
render/                 projeto Remotion (React/TypeScript)
  src/Documentario.tsx  composição do vídeo longo
  src/Short.tsx         composição vertical 1080×1920
  src/Thumbnail.tsx     thumbnails
  src/templates/        templates de cena (gráfico, número em destaque, manchete…)
```

### Decisões de projeto

- **Etapas idempotentes e retomáveis.** O estado vive em arquivos; rodar de novo continua de onde parou. Assinaturas (hash) invalidam só o que mudou (ex.: texto de uma cena → só aquela narração).
- **LLM com duas pernas.** Com `ANTHROPIC_API_KEY` o roteiro é automático. Sem ela, entra o **modo manual**: o prompt é gravado em `projetos/<nome>/prompts/`, você cola no Claude, salva a resposta e roda de novo.
- **Anti-cópia.** O roteiro é conferido contra a referência (maior sequência idêntica de palavras e sobreposição de trechos de 5 palavras); se passar do limite, é reescrito (`adaptacao` no config).
- **IA local opcional.** Um ComfyUI em outro PC com GPU faz voz, trilha, escolha de imagem por visão (Qwen3-VL) e geração de imagem (Z-Image Turbo). Tudo tem alternativa ou cai num modo simples.
- **Narração conferida.** O Whisper (serviço de análise) confere se a voz falou o texto; cena com mais de 12% de palavras erradas é gerada de novo. Também fornece o tempo de cada palavra para a legenda.
- **Voz em blocos.** O Gemini TTS narra até ~700 palavras por pedido, e o áudio é cortado por cena com os tempos do Whisper: entonação contínua e poucos pedidos. Cada provedor grava em pasta própria, então vozes nunca se misturam.
- **Formato "programa de TV".** Abertura com escalada, vinheta, blocos com placa e faixa "A SEGUIR", pensado para quem assiste na TV (`video.formato`).
- **Publicação só com confirmação.** Nada é enviado ao YouTube ou Instagram sem `--confirmar`; sem ele, só mostra a agenda.

### Templates de cena (Remotion)

| Tipo | O que mostra |
|---|---|
| `midia` | foto (zoom lento) ou vídeo em tela cheia, com título de capítulo ou lower third opcional |
| `frase_impacto` | frase curta em tela escura, palavras destacadas |
| `grafico` | gráfico de linha ou barras animado |
| `numero_destaque` | número enorme que conta até o valor |
| `split_topicos` | imagem à esquerda, título e 2 a 4 tópicos à direita |
| `fluxo` | 2 a 4 etapas ligadas por setas |
| `manchete` | imagem em tela cheia com manchete de reportagem |

A decupagem escolhe o tipo de cada cena seguindo [`prompts/decupagem.md`](prompts/decupagem.md).

## Requisitos

- Python 3.11+
- Node.js 20.19+ (ou 22.13+/24+) e `ffmpeg`
- `yt-dlp` (opcional, para usar link do YouTube como referência)
- Opcionais, conforme o que for usar: chave da Anthropic, Gemini, OpenAI, ElevenLabs, Pexels, Pixabay; ComfyUI com GPU; Whisper; credenciais OAuth do Google (YouTube); bot do Telegram; Zernio (Instagram)

## Instalação

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd render && npm install
cp .env.example .env   # preencha só o que for usar
```

O `.env` nunca é versionado. A pasta `credenciais/` (OAuth do YouTube) também não.

### Arquivos que você precisa fornecer

Este repositório traz só o código. Estas pastas são locais e estão no `.gitignore`:

| Pasta | Para quê |
|---|---|
| `projetos/` | saída de cada vídeo (criada sozinha) |
| `assets/vozes/` | WAV de referência de voz para o ChatterBox (`tts.comfyui.referencia`) |
| `assets/musica/`, `assets/sfx/`, `assets/vinheta/` | música e sons próprios (opcional: sem eles o sistema gera) |
| `render/public/` | arquivos estáticos do Remotion (os exemplos do Studio usam `exemplo/*.jpg`: ponha imagens suas ou ajuste `render/src/Root.tsx`) |
| `credenciais/` | `youtube_client.json` (OAuth do Google Cloud) |

## Uso

```bash
.venv/bin/python run.py --referencia transcricao.txt --modo novo_angulo --tema "seu ângulo" --projeto meu-video
```

- `--modo novo_angulo`: mesmo tema da referência, ângulo novo
- `--modo outro_tema --tema "..."`: só a estrutura da referência, assunto diferente
- `--modo aprofundar --tema "..."`: um trecho da referência vira o vídeo inteiro
- `--ate cenas`: para depois de uma etapa (bom para revisar antes de gastar com voz e render)
- `--so publicacao | shorts | youtube | instagram | metricas | tendencias`: roda só uma etapa
- `--voz google|comfyui|openai|elevenlabs|macos`: força o provedor de voz
- `--confirmar`: com `--so youtube`/`instagram`, envia de verdade

Para visualizar e ajustar os templates: `cd render && npx remotion studio`.

## Serviços opcionais

| Serviço | Variável | Para quê |
|---|---|---|
| Claude API | `ANTHROPIC_API_KEY` | roteiro, decupagem, títulos e cortes automáticos |
| Gemini TTS | `GEMINI_API_KEY` | voz padrão, em blocos |
| ComfyUI (GPU) | `COMFY_URL` | voz ChatterBox, trilha ACE-Step, visão e imagem por IA |
| Whisper | `ANALISE_URL` | confere a fala e dá o tempo de cada palavra (serviço HTTP próprio) |
| Pexels / Pixabay | `PEXELS_API_KEY`, `PIXABAY_API_KEY` | fotos e vídeos; sem chave usa só Wikimedia Commons |
| YouTube Data/Analytics | `credenciais/youtube_client.json` | agendamento, métricas, tendências |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | avisos de fim de etapa ou erro |
| Zernio | `ZERNIO_API_KEY` | Reels no Instagram |

Sem o ComfyUI, a narração cai na voz do macOS (só para teste). Sem o Whisper, a narração sai sem conferência.

## Shorts, publicação e agenda

- **Publicação:** 3 títulos (curiosidade, fato marcante, consequência) e 3 thumbs para o teste A/B/C do YouTube Studio, mais descrição e 15 tags em `youtube.txt`. As regras estão em [`prompts/publicacao.md`](prompts/publicacao.md).
- **Shorts:** 3 cortes de 30 a 60 s do vídeo pronto, escolhidos pelo LLM ([`prompts/shorts.md`](prompts/shorts.md)), com legenda grande, chamada no topo e duas capas. O áudio vem do vídeo longo.
- **Pasta `publicar/`:** tudo pronto para postar, numerado na ordem.
- **Agenda:** `--so youtube` mostra a agenda; com `--confirmar` envia como privado com data de publicação, com marcação de conteúdo sintético quando há imagem de IA.

## Transparência sobre IA

Quando há imagem gerada por IA, o `youtube.txt` avisa para marcar "conteúdo alterado ou sintético" no YouTube Studio, e o envio pela API já marca. Respeite os termos de cada banco de imagens e crédite quando exigido (`creditos.json`).

## Segurança

- Chaves só no `.env` (ignorado pelo git). Nunca coloque segredos no `config.yaml`.
- O envio ao YouTube só acontece se a conta autorizada for o canal definido em `youtube.canal`.

## Licença

[MIT](LICENSE)
