"""Vídeos em alta no nicho do canal: ideias de tema e de referência para os próximos vídeos.

Busca no YouTube (Data API, região Brasil, em português) os vídeos recentes mais vistos para cada termo de
`tendencias.termos` no config.yaml, fica com os que passaram de `min_views` em até `dias` dias e têm pelo
menos `min_minutos` de duração, e ordena por visualizações por dia. Cada busca gasta 100 unidades da cota
diária da API (10.000 por padrão); 15 termos × 2 durações ≈ 3.000 unidades. Além disso, a busca
tem um limite próprio de buscas por dia (num projeto novo, poucas dezenas): rode uma vez por dia.

Grava projetos/<slug>/tendencias/AAAA-MM-DD_HHMM.json e .md. Para usar um como referência:
run.py --referencia "<link>" --projeto <nome> …
"""

import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .util import log, salvar_json


def gerar(config: dict, projeto: Path) -> list[dict]:
    from . import youtube

    c = config["tendencias"]
    yt = youtube._servico()
    agora = datetime.now(timezone.utc)
    desde = (agora - timedelta(days=c["dias"])).strftime("%Y-%m-%dT%H:%M:%SZ")

    from googleapiclient.errors import HttpError

    encontrados = {}  # id → termos que trouxeram o vídeo
    try:
        for termo in c["termos"]:
            for duracao in ("medium", "long"):  # medium: 4 a 20 min; long: mais de 20 min
                resposta = yt.search().list(
                    part="id", q=termo, type="video", order="viewCount", publishedAfter=desde,
                    regionCode="BR", relevanceLanguage="pt", videoDuration=duracao, maxResults=25,
                ).execute()
                for item in resposta.get("items", []):
                    encontrados.setdefault(item["id"]["videoId"], set()).add(termo)
    except HttpError as erro:
        if erro.status_code != 429 and "quota" not in str(erro).lower():
            raise
        # a busca tem limite diário próprio (poucas dezenas de buscas num projeto novo): fica com o que achou
        log(f"Limite diário de buscas da API atingido depois de {len(encontrados)} vídeos; seguindo com eles. "
            "Volta amanhã (zera à meia-noite do horário do Pacífico).")
    log(f"{len(encontrados)} vídeos recentes encontrados")

    videos, brutos = [], []
    ids = list(encontrados)
    for i in range(0, len(ids), 50):
        resposta = yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50])).execute()
        for v in resposta.get("items", []):
            brutos.append(v)
            views = int(v["statistics"].get("viewCount", 0))
            minutos = _minutos(v["contentDetails"].get("duration", "PT0S"))  # live agendada não tem duração
            publicado = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
            dias = max((agora - publicado).total_seconds() / 86400, 0.25)
            if views < c["min_views"] or not c["min_minutos"] <= minutos <= c.get("max_minutos", 600):
                continue
            if int(v["snippet"].get("categoryId", 0)) in c.get("categorias_fora", []) or not _em_portugues(v["snippet"]):
                continue
            videos.append({
                "id": v["id"], "url": f"https://youtu.be/{v['id']}", "titulo": v["snippet"]["title"],
                "canal": v["snippet"]["channelTitle"], "canal_id": v["snippet"]["channelId"], "publicado": v["snippet"]["publishedAt"],
                "dias": round(dias, 1), "views": views, "views_dia": round(views / dias),
                "likes": int(v["statistics"].get("likeCount", 0)), "comentarios": int(v["statistics"].get("commentCount", 0)),
                "minutos": round(minutos), "termos": sorted(encontrados[v["id"]]),
                "descricao": v["snippet"].get("description", "")[:600],
            })
    _fator(yt, videos)
    videos.sort(key=lambda x: -x["views_dia"])

    pasta = projeto / "tendencias"
    nome = datetime.now().strftime("%Y-%m-%d_%H%M")
    salvar_json(pasta / f"{nome}.json", videos)
    salvar_json(pasta / f"{nome}_brutos.json", brutos)  # tudo o que a busca trouxe, para refiltrar sem gastar cota
    (pasta / f"{nome}.md").write_text(_lista(videos, c))
    log(f"{len(videos)} vídeos com {c['min_views']:,}+ visualizações em até {c['dias']} dias".replace(",", "."))
    log(f"Salvo em {pasta.relative_to(projeto.parent.parent)}/{nome}.json e .md")
    return videos


def _fator(yt, videos: list[dict]) -> None:
    """Quanto cada vídeo saiu da curva do próprio canal: views ÷ mediana dos últimos 30 vídeos longos dele.
    Custa 3 unidades de cota por canal (nada perto das buscas)."""
    canais = {}
    for canal_id in {v["canal_id"] for v in videos}:
        canal = yt.channels().list(part="contentDetails,statistics", id=canal_id).execute()["items"][0]
        uploads = canal["contentDetails"]["relatedPlaylists"]["uploads"]
        itens = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=30).execute()["items"]
        resposta = yt.videos().list(part="statistics,contentDetails",
                                    id=",".join(i["contentDetails"]["videoId"] for i in itens)).execute() if itens else {"items": []}
        longos = [int(x["statistics"].get("viewCount", 0)) for x in resposta["items"]
                  if _minutos(x["contentDetails"].get("duration", "PT0S")) >= 4]
        canais[canal_id] = (int(canal["statistics"].get("subscriberCount", 0)), statistics.median(longos) if longos else 0)
    for v in videos:
        inscritos, mediana = canais[v["canal_id"]]
        v["inscritos"], v["mediana_canal"] = inscritos, round(mediana)
        v["fator"] = round(v["views"] / mediana, 1) if mediana else None


PALAVRAS_PT = re.compile(r"[ãõçâêô]|\b(como|que|do|da|dos|das|não|mais|maior|por|para|uma|você)\b", re.I)


def _em_portugues(snippet: dict) -> bool:
    """O idioma declarado decide; sem ele, o título precisa ter cara de português."""
    idioma = snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or ""
    if idioma:
        return idioma.lower().startswith("pt")
    return bool(PALAVRAS_PT.search(snippet["title"]))


def _minutos(iso: str) -> float:
    h, m, s = (int(x or 0) for x in re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso).groups())
    return h * 60 + m + s / 60


def _lista(videos: list[dict], c: dict) -> str:
    linhas = [f"# Em alta no nicho (últimos {c['dias']} dias, {c['min_views']:,}+ visualizações, {c['min_minutos']}+ min)".replace(",", "."),
              "", "Fator = views ÷ mediana dos últimos 30 vídeos longos do canal: quanto o vídeo saiu da curva dele.", "",
              "| # | Vídeo | Canal | Inscritos | Views | Por dia | Fator | Dias | Min | Termo |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for n, v in enumerate(videos, start=1):
        linhas.append(f"| {n} | [{v['titulo'][:70]}]({v['url']}) | {v['canal']} | {v['inscritos']:,} | {v['views']:,} | {v['views_dia']:,} | "
                      f"{v['fator'] if v['fator'] is not None else '–'}x | {v['dias']} | {v['minutos']} | {', '.join(v['termos'][:2])} |".replace(",", "."))
    return "\n".join(linhas) + "\n"
