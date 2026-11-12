"""Métricas do canal no YouTube: o que cada vídeo e cada Short de um projeto está rendendo.

Junta duas fontes:
- YouTube Data API: visualizações, likes e comentários em tempo real (os números públicos);
- YouTube Analytics API: minutos assistidos, duração média, porcentagem assistida, inscritos ganhos,
  compartilhamentos e de onde vêm as visualizações (Shorts, busca, sugeridos, vídeo relacionado…).
  O Analytics chega com 1 a 2 dias de atraso; impressões e CTR da miniatura não saem pela API (só no Studio).

Grava projetos/<slug>/metricas/AAAA-MM-DD_HHMM.json e um resumo .md, para comparar rodada a rodada.
"""

from datetime import date, datetime, timezone
from pathlib import Path

from .util import ler_json, log, salvar_json

METRICAS = ["views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage",
            "subscribersGained", "likes", "comments", "shares"]

# nomes do insightTrafficSourceType em português, só os que aparecem num canal como este
ORIGENS = {
    "SHORTS": "feed de Shorts", "YT_SEARCH": "busca do YouTube", "RELATED_VIDEO": "vídeo relacionado/sugerido",
    "SUBSCRIBER": "página inicial (inscritos)", "BROWSE": "página inicial e navegação", "EXT_URL": "sites externos",
    "NO_LINK_OTHER": "direto ou desconhecido", "YT_CHANNEL": "página do canal", "YT_OTHER_PAGE": "outras páginas do YouTube",
    "NOTIFICATION": "notificações", "PLAYLIST": "playlists", "END_SCREEN": "tela final", "ANNOTATION": "cards",
    "HASHTAGS": "hashtags", "SOUND_PAGE": "página de som", "CAMPAIGN_CARD": "campanha", "LIVE_REDIRECT": "redirecionamento de live",
}


def gerar(config: dict, projeto: Path) -> dict:
    from . import youtube

    credenciais = youtube._credenciais()
    yt = youtube._servico(credenciais)
    analytics = youtube._servico_analytics(credenciais)
    estado_arq = projeto / "youtube.json"
    if estado_arq.exists():
        estado = {k: v for k, v in ler_json(estado_arq).items() if isinstance(v, dict) and v.get("id")}
    else:  # projeto enviado à mão: mede o canal inteiro
        log("Projeto sem youtube.json (enviado à mão): medindo todos os vídeos do canal")
        estado = _canal_inteiro(yt)

    ids = {v["id"]: chave for chave, v in estado.items()}
    publicos = _publicos(yt, list(ids))
    hoje = date.today().isoformat()
    inicio = min((p["publicado"][:10] for p in publicos.values() if p["publicado"]), default=hoje)
    por_video = _relatorio(analytics, list(ids), inicio, hoje)
    origens = _origens(analytics, list(ids), inicio, hoje)

    videos = []
    for video_id, chave in sorted(ids.items(), key=lambda par: estado[par[1]]["publica_em"]):
        p = publicos.get(video_id, {})
        videos.append({"chave": chave, "id": video_id, "url": estado[chave]["url"], "titulo": estado[chave]["titulo"],
                       "publica_em": estado[chave]["publica_em"], **p,
                       "analytics": por_video.get(video_id, {}), "origens": origens.get(video_id, {})})
    relatorio = {"gerado_em": datetime.now(timezone.utc).isoformat(), "periodo": [inicio, hoje], "videos": videos}

    pasta = projeto / "metricas"
    nome = datetime.now().strftime("%Y-%m-%d_%H%M")
    salvar_json(pasta / f"{nome}.json", relatorio)
    texto = _resumo(relatorio)
    (pasta / f"{nome}.md").write_text(texto)
    print(texto)
    log(f"Salvo em {(pasta / nome).relative_to(projeto.parent.parent)}.json e .md")
    return relatorio


def _canal_inteiro(yt) -> dict:
    canal = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads = canal["contentDetails"]["relatedPlaylists"]["uploads"]
    estado, pagina = {}, None
    while True:
        resposta = yt.playlistItems().list(part="snippet,contentDetails", playlistId=uploads, maxResults=50,
                                           pageToken=pagina).execute()
        for item in resposta["items"]:
            video_id = item["contentDetails"]["videoId"]
            estado[f"canal_{len(estado) + 1:02d}"] = {
                "id": video_id, "url": f"https://youtu.be/{video_id}", "titulo": item["snippet"]["title"],
                "publica_em": item["contentDetails"].get("videoPublishedAt") or item["snippet"]["publishedAt"]}
        pagina = resposta.get("nextPageToken")
        if not pagina:
            return estado


def _publicos(yt, ids: list[str]) -> dict:
    """Números públicos em tempo real (Data API)."""
    saida = {}
    for i in range(0, len(ids), 50):
        resposta = yt.videos().list(part="statistics,status,snippet,contentDetails", id=",".join(ids[i:i + 50])).execute()
        for v in resposta.get("items", []):
            s = v.get("statistics", {})
            saida[v["id"]] = {
                "status": v["status"]["privacyStatus"],
                "publicado": v["snippet"].get("publishedAt") if v["status"]["privacyStatus"] == "public" else None,
                "duracao": v["contentDetails"]["duration"],
                "views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                "comentarios": int(s.get("commentCount", 0)),
            }
    return saida


def _relatorio(analytics, ids: list[str], inicio: str, fim: str) -> dict:
    resposta = analytics.reports().query(
        ids="channel==MINE", startDate=inicio, endDate=fim, metrics=",".join(METRICAS),
        dimensions="video", filters="video==" + ",".join(ids), maxResults=200,
    ).execute()
    nomes = [c["name"] for c in resposta.get("columnHeaders", [])]
    return {linha[0]: dict(zip(nomes[1:], linha[1:])) for linha in resposta.get("rows", [])}


def _origens(analytics, ids: list[str], inicio: str, fim: str) -> dict:
    """Visualizações por origem de tráfego, vídeo a vídeo (a API não cruza vídeo e origem numa consulta só)."""
    saida = {}
    for video_id in ids:
        resposta = analytics.reports().query(
            ids="channel==MINE", startDate=inicio, endDate=fim, metrics="views",
            dimensions="insightTrafficSourceType", filters=f"video=={video_id}", sort="-views",
        ).execute()
        saida[video_id] = {ORIGENS.get(origem, origem): int(views) for origem, views in resposta.get("rows", [])}
    return saida


def _resumo(relatorio: dict) -> str:
    linhas = [f"# Métricas ({relatorio['gerado_em'][:16].replace('T', ' ')} UTC)", "",
              "Visualizações, likes e comentários são de agora. O resto vem do YouTube Analytics, que atrasa 1 a 2 dias.", "",
              "| Item | Status | Views | Likes | Coment. | Min. assistidos | Duração média | % assistida | Inscritos | Compart. |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for v in relatorio["videos"]:
        a = v["analytics"]
        duracao = a.get("averageViewDuration")
        linhas.append(
            f"| {v['chave']}: {v['titulo'][:45]} | {v.get('status', '?')} | {v.get('views', 0)} | {v.get('likes', 0)} | "
            f"{v.get('comentarios', 0)} | {a.get('estimatedMinutesWatched', '–')} | "
            f"{f'{int(duracao) // 60}:{int(duracao) % 60:02d}' if duracao is not None else '–'} | "
            f"{f'{a['averageViewPercentage']:.0f}%' if a.get('averageViewPercentage') is not None else '–'} | "
            f"{a.get('subscribersGained', '–')} | {a.get('shares', '–')} |")
    if not any(v["analytics"] for v in relatorio["videos"]):
        linhas += ["", "O YouTube Analytics ainda não tem dados deste período. Em canal novo, os primeiros números "
                   "aparecem de 48 a 72 h depois do primeiro vídeo público; rode de novo amanhã."]
    linhas += ["", "## De onde vêm as visualizações", ""]
    for v in relatorio["videos"]:
        if v["origens"]:
            total = sum(v["origens"].values()) or 1
            partes = ", ".join(f"{origem} {n} ({n * 100 // total}%)" for origem, n in v["origens"].items())
            linhas.append(f"- **{v['chave']}**: {partes}")
    return "\n".join(linhas) + "\n"
