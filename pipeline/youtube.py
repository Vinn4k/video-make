"""Envio e agendamento no YouTube pela API (YouTube Data API v3).

Monta a agenda (vídeo longo no primeiro dia, depois um Short por dia, do mais viral para o menos)
e só envia quando chamado com confirmar=True. Cada vídeo sobe como privado com data de publicação
(publishAt): o YouTube publica sozinho na hora marcada.

Credenciais em credenciais/ (fora do projeto de vídeo e ignoradas pelo git):
- youtube_client.json  cliente OAuth "App para computador" baixado do Google Cloud
- youtube_token.json   criado no primeiro login (abre o navegador uma vez)

O que já subiu fica em projetos/<slug>/youtube.json, para nunca enviar o mesmo vídeo duas vezes.

Atenção: projetos de API não verificados sobem vídeos travados em privado até passarem pela
auditoria do YouTube (formulário grátis); veja o WORKFLOW.md.
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .util import RAIZ, EtapaPendente, ler_json, log, salvar_json

PASTA_CREDENCIAIS = RAIZ / "credenciais"
CLIENTE = PASTA_CREDENCIAIS / "youtube_client.json"
TOKEN = PASTA_CREDENCIAIS / "youtube_token.json"
ESCOPOS = ["https://www.googleapis.com/auth/youtube.upload",
           "https://www.googleapis.com/auth/youtube.force-ssl",  # force-ssl: legendas, datas e descrições
           "https://www.googleapis.com/auth/yt-analytics.readonly"]  # métricas (run.py --so metricas)
LIMITE_DESCRICAO = 5000


def enviar(config: dict, projeto: Path, confirmar: bool = False, inicio: str | None = None,
           substituir: list[str] | None = None, reagendar: list[str] | None = None,
           apenas: list[str] | None = None) -> None:
    """Com `substituir` (ex.: ["video"]), sobe de novo esses itens na mesma data, apaga o envio antigo só depois
    que o novo subiu e, se o longo mudou de link, corrige o link na descrição dos Shorts já enviados.
    Com `apenas` (ex.: ["video"]), só mexe nesses itens (envio e comentário do manual)."""
    estado_arq = projeto / "youtube.json"
    estado = ler_json(estado_arq) if estado_arq.exists() else {}
    substituir = [s for s in (substituir or []) if s in estado]
    novas_datas = _novas_datas(config, reagendar or [], estado)
    for chave, quando in novas_datas.items():
        log(f"Reagendar {chave}: {datetime.fromisoformat(estado[chave]['publica_em']):%d/%m %H:%M} → {quando:%d/%m %H:%M}")
    itens = [i for i in agenda(config, projeto, inicio, estado) if not apenas or i["chave"] in apenas]
    antigos = {s: estado.pop(s) for s in substituir}  # a data vem do envio antigo (já fixada na agenda acima)
    if not itens:
        raise RuntimeError("Nada para enviar: rode as etapas de vídeo, publicação e Shorts antes.")

    log("Agenda do YouTube:")
    itens.sort(key=lambda item: (item["tipo"] != "vídeo", item["quando"]))  # o longo sobe antes: os Shorts levam o link dele
    for item in itens:
        feito = estado.get(item["chave"])
        situacao = (f"já enviado: {feito['url']}" if feito else
                    f"substitui {antigos[item['chave']]['url']}" if item["chave"] in antigos else "a enviar")
        log(f"  {item['quando']:%d/%m %H:%M}  {item['tipo']:<5}  {item['titulo']}  ({situacao})")
        if feito and feito.get("comentario") and item["comentario"] and feito["comentario"]["texto"] != item["comentario"]:
            log(f"      💬 comentário do manual a trocar pelo texto novo ({feito['comentario']['url']}): {item['comentario']}")
        elif feito and feito.get("comentario"):
            log(f"      💬 comentário do manual publicado: {feito['comentario']['url']}")
        elif item["comentario"]:
            depois = " (vídeo agendado: sai quando ele ficar público)" if item["quando"] > datetime.now(item["quando"].tzinfo) else ""
            log(f"      💬 comentário do manual{depois}: {item['comentario']}")
    if not confirmar:
        raise EtapaPendente("Confira a agenda acima. Para enviar ao YouTube, rode de novo com --confirmar "
                            "(opcional: --inicio AAAA-MM-DD para mudar o primeiro dia).")

    yt = _servico()
    canal = _canal(yt)
    if canal != config["youtube"]["canal"]:
        raise RuntimeError(f"A conta autorizada é o canal \"{canal}\", não \"{config['youtube']['canal']}\". "
                           f"Apague {TOKEN.relative_to(RAIZ)} e rode de novo, escolhendo o canal certo no login.")
    log(f"Canal: {canal}")
    for chave, quando in novas_datas.items():
        _mudar_data(yt, estado[chave]["id"], quando)
        estado[chave]["publica_em"] = quando.isoformat()
        salvar_json(estado_arq, estado)
        log(f"  {chave} agora publica em {quando:%d/%m %H:%M} ({estado[chave]['url']})")
    for item in itens:
        if item["chave"] in estado:
            continue
        if item["tipo"] == "short" and "{video_longo}" in item["descricao"]:
            longo = estado.get("video")
            estreia = datetime.fromisoformat(longo["publica_em"]) if longo else None
            if longo and item["quando"] < estreia:  # trailer: o link só abre na estreia
                chamada = f"O vídeo completo estreia {estreia:%d/%m} às {estreia:%H:%M} no canal: {longo['url']}"
            else:
                chamada = f"Vídeo completo: {longo['url']}" if longo else "Vídeo completo no canal."
            item["descricao"] = item["descricao"].replace("{video_longo}", chamada)
        log(f"Enviando {item['tipo']}: {item['titulo']}…")
        video_id = _subir(yt, config, item)
        url = f"https://youtu.be/{video_id}"
        estado[item["chave"]] = {"id": video_id, "url": url, "publica_em": item["quando"].isoformat(),
                                 "titulo": item["titulo"]}
        salvar_json(estado_arq, estado)
        if item.get("thumb"):
            _thumb(yt, video_id, item["thumb"])
        if item.get("legendas"):
            _legendas(yt, config, video_id, item["legendas"])
        log(f"  {url} (publica em {item['quando']:%d/%m %H:%M})")
    for chave, antigo in antigos.items():
        if estado.get(chave, {}).get("id") in (None, antigo["id"]):
            continue
        yt.videos().delete(id=antigo["id"]).execute()
        estado.setdefault("apagados", []).append({**antigo, "chave": chave, "substituido_por": estado[chave]["url"]})
        salvar_json(estado_arq, estado)
        log(f"Apagado o envio antigo de {chave}: {antigo['url']}")
        if chave == "video":
            _trocar_link_nos_shorts(yt, estado, antigo["url"], estado["video"]["url"])
    _comentar(yt, estado, estado_arq, itens)
    shorts_enviados = [i["chave"] for i in itens if i["chave"].startswith("short_") and estado.get(i["chave"], {}).get("id")]
    if shorts_enviados:
        # A API não tem o campo "Vídeo relacionado"; Short reenviado (--substituir) também perde o vínculo.
        log("⚠ FALTA NO STUDIO: ligar \"Vídeo relacionado\" ao vídeo longo em cada Short enviado agora:")
        for chave in shorts_enviados:
            log(f"   {chave}: https://studio.youtube.com/video/{estado[chave]['id']}/edit")
    log("Pronto. Confira no YouTube Studio: os vídeos aparecem como Agendados. Se aparecerem como "
        "\"Bloqueado como privado\", o projeto da API ainda precisa da auditoria (WORKFLOW.md).")


def agenda(config: dict, projeto: Path, inicio: str | None, estado: dict) -> list[dict]:
    """Itens na ordem de postagem, com data e hora; o que já subiu mantém a data original."""
    c = config["youtube"]
    fuso = ZoneInfo(c["fuso"])
    if inicio:
        dia = datetime.fromisoformat(inicio).date()
    else:
        dia = (datetime.now(fuso) + timedelta(days=1)).date()
    hora = lambda texto: [int(x) for x in texto.split(":")]
    if not inicio and c.get("short_vespera"):
        # o trailer sai na véspera: se o horário dele já passou hoje (ou está a menos de 1 h), o lançamento vai para depois de amanhã
        h, m = hora(c["short_vespera"])
        trailer = datetime(dia.year, dia.month, dia.day, h, m, tzinfo=fuso) - timedelta(days=1)
        if trailer < datetime.now(fuso) + timedelta(hours=1):
            dia += timedelta(days=1)

    def quando(chave: str, deslocamento: int, horario: str, minutos: int = 0) -> datetime:
        if chave in estado:
            return datetime.fromisoformat(estado[chave]["publica_em"])
        h, m = hora(horario)
        return datetime(dia.year, dia.month, dia.day, h, m, tzinfo=fuso) + timedelta(days=deslocamento, minutes=minutos)

    def quando_short(chave: str, n: int) -> datetime:
        """Trailer (2º Short) na véspera, o mais forte logo depois do longo, os outros um por dia."""
        vespera, depois = c.get("short_vespera"), c.get("short_depois_min")
        if n == 2 and vespera:
            return quando(chave, -1, vespera)
        if n == 1 and depois is not None:
            return quando(chave, 0, c["hora_video"], depois)
        seguintes = [k for k in range(1, n + 1) if not (k == 2 and vespera) and not (k == 1 and depois is not None)]
        return quando(chave, len(seguintes), c["hora_shorts"])

    cenas = ler_json(projeto / "cenas.json")
    ia = {c2["id"] for c2 in cenas if (c2.get("midia") or {}).get("origem_id", "").startswith("ia-")}
    itens = []

    pub_arq, video = projeto / "publicacao.json", projeto / "video_final.mp4"
    if video.exists() and pub_arq.exists():
        pub = ler_json(pub_arq)
        itens.append({
            "chave": "video", "tipo": "vídeo", "arquivo": video, "titulo": pub["titulos"][0],
            "descricao": _descricao_longo(projeto, _rodape(c["rodape"], pub.get("hashtags"))), "tags": pub.get("tags", []),
            "thumb": projeto / "thumbs" / "thumb_A.png", "legendas": projeto / "legendas.srt",
            "sintetico": bool(ia), "comentario": comentario_manual(config, "video"),
            "quando": quando("video", 0, c["hora_video"]),
        })

    shorts_arq = projeto / "shorts.json"
    if shorts_arq.exists():
        pub = ler_json(pub_arq) if pub_arq.exists() else {}
        tags = [t for t in pub.get("tags", [])]
        ids = [x["id"] for x in cenas]
        for n, short in enumerate(ler_json(shorts_arq)["shorts"], start=1):
            arquivo = projeto / "shorts" / f"short_{n:02d}.mp4"
            if not arquivo.exists():
                continue
            usadas = set(ids[ids.index(short["inicio"]): ids.index(short["fim"]) + 1]) | {short.get("gancho")}
            hashtags = (short["hashtags_yt"].split() if short.get("hashtags_yt") else
                        ["#shorts"] + ["#" + re.sub(r"[^\w]", "", t) for t in tags if " " not in t][:2])
            chave = f"short_{n:02d}"
            itens.append({
                "chave": chave, "tipo": "short", "arquivo": arquivo, "titulo": short["titulo"],
                "descricao": f"{short.get('descricao', '')}\n\n{{video_longo}}\n\n{' '.join(hashtags)}",
                "tags": tags, "thumb": projeto / "shorts" / f"short_{n:02d}_capa_A.jpg", "legendas": None,
                "sintetico": bool(usadas & ia), "comentario": comentario_manual(config, "short"),
                "quando": quando_short(chave, n),
            })
    return itens


def comentario_manual(config: dict, tipo: str) -> str | None:
    """CTA do manual "Vídeos com IA" para "video", "short" ou "reels_tiktok"; None quando desligado no config.yaml."""
    c = (config.get("publicacao") or {}).get("comentario_manual") or {}
    return (c.get(tipo) or "").strip() or None if c.get("ligado") else None


def _comentar(yt, estado: dict, estado_arq: Path, itens: list[dict]) -> None:
    """Publica o comentário do manual nos vídeos enviados que ainda não têm. Vídeo agendado (privado) pode recusar
    comentário: o dele fica para a próxima rodada com --confirmar depois que ele sair. A API não fixa comentário."""
    from googleapiclient.errors import HttpError

    publicados, pendentes = [], []
    for item in itens:
        feito = estado.get(item["chave"])
        if not item["comentario"] or not feito:
            continue
        if feito.get("comentario"):
            if feito["comentario"]["texto"] != item["comentario"]:  # texto mudou no config: edita o mesmo (continua fixado)
                yt.comments().update(part="snippet", body={"id": feito["comentario"]["id"], "snippet": {
                    "textOriginal": item["comentario"]}}).execute()
                feito["comentario"]["texto"] = item["comentario"]
                salvar_json(estado_arq, estado)
                log(f"  Comentário do manual de {item['chave']} trocado pelo texto novo: {feito['comentario']['url']}")
            continue
        quando = datetime.fromisoformat(feito["publica_em"])
        try:
            resposta = yt.commentThreads().insert(part="snippet", body={"snippet": {
                "videoId": feito["id"], "topLevelComment": {"snippet": {"textOriginal": item["comentario"]}}}}).execute()
        except HttpError as erro:
            if quando > datetime.now(quando.tzinfo):
                pendentes.append(f"{item['chave']} ({quando:%d/%m %H:%M})")
            else:
                log(f"  Comentário do manual em {item['chave']} não publicado ({erro.status_code}): {erro.reason}")
            continue
        url = f"https://www.youtube.com/watch?v={feito['id']}&lc={resposta['id']}"
        feito["comentario"] = {"id": resposta["id"], "url": url, "texto": item["comentario"]}
        salvar_json(estado_arq, estado)
        publicados.append(f"{item['chave']}: {url}")
    if publicados:
        log("Comentário do manual publicado. A API não fixa: abra cada link, ⋮ no comentário → Fixar")
        for linha in publicados:
            log(f"  {linha}")
    if pendentes:
        log(f"Comentário do manual pendente (vídeo ainda agendado): {', '.join(pendentes)}. "
            "Rode de novo com --confirmar depois que ele sair.")


def _rodape(rodape: str, hashtags: list[str] | str | None) -> str:
    """Rodapé do canal com as hashtags do assunto (publicacao.json "hashtags") no lugar das genéricas do config."""
    if not hashtags:
        return rodape
    if isinstance(hashtags, str):
        hashtags = hashtags.split()
    linhas = [l for l in rodape.strip().splitlines() if not l.strip().startswith("#")]
    return "\n".join(linhas + [" ".join(hashtags[:3])])


def _descricao_longo(projeto: Path, rodape: str) -> str:
    """Do youtube.txt: descrição, capítulos, fontes e créditos (sem os títulos A/B/C e as tags), mais o rodapé."""
    texto = (projeto / "youtube.txt").read_text()
    corpo = texto.split("DESCRIÇÃO:\n", 1)[-1].split("\n\nTAGS:", 1)[0].strip()
    descricao = f"{corpo}\n\n{rodape.strip()}"
    if len(descricao) > LIMITE_DESCRICAO:
        # créditos longos: mantém autor e licença, tira os links
        corpo = re.sub(r" https?://\S+", "", corpo)
        descricao = f"{corpo}\n\n{rodape.strip()}"
    if len(descricao) > LIMITE_DESCRICAO:
        log(f"Aviso: descrição com {len(descricao)} caracteres; cortada em {LIMITE_DESCRICAO}")
        descricao = descricao[:LIMITE_DESCRICAO - 1] + "…"
    return descricao


def _servico(cred=None):
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=cred or _credenciais())


def _servico_analytics(cred=None):
    from googleapiclient.discovery import build

    return build("youtubeAnalytics", "v2", credentials=cred or _credenciais())


def _credenciais():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CLIENTE.exists():
        raise EtapaPendente(f"Falta o cliente OAuth do Google em {CLIENTE.relative_to(RAIZ)}. "
                            "Siga a seção \"YouTube pela API\" do WORKFLOW.md.")
    from google.auth.exceptions import RefreshError

    cred = Credentials.from_authorized_user_file(str(TOKEN), ESCOPOS) if TOKEN.exists() else None
    if cred and set(ESCOPOS) - set(ler_json(TOKEN).get("scopes") or []):  # token de antes de uma permissão nova
        log("O login guardado não tem todas as permissões (ex.: Analytics); é preciso autorizar de novo")
        cred = None
    if cred and cred.expired and cred.refresh_token:
        try:
            cred.refresh(Request())
        except RefreshError:
            # app em modo de teste no Google: o acesso vence a cada 7 dias e precisa de novo login
            cred = None
    if not cred or not cred.valid:
        if os.environ.get("YOUTUBE_SEM_LOGIN"):  # execução agendada: ninguém no navegador para autorizar
            raise EtapaPendente("O login do YouTube venceu (em modo de teste, a cada 7 dias). Rode "
                                "`run.py --projeto canal --so metricas` no Mac e autorize no navegador.")
        log("Abrindo o navegador para você autorizar o canal (só na primeira vez)…")
        cred = InstalledAppFlow.from_client_secrets_file(str(CLIENTE), ESCOPOS).run_local_server(port=0)
    TOKEN.write_text(cred.to_json())
    TOKEN.chmod(0o600)
    return cred


def _canal(yt) -> str:
    itens = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
    return itens[0]["snippet"]["title"] if itens else "(nenhum canal)"


def _novas_datas(config: dict, pedidos: list[str], estado: dict) -> dict[str, datetime]:
    """"short_01=2026-10-28T18:00" → {"short_01": datetime no fuso do canal}, só para itens já enviados."""
    fuso = ZoneInfo(config["youtube"]["fuso"])
    datas = {}
    for pedido in pedidos:
        chave, _, quando = pedido.partition("=")
        if chave not in estado:
            raise RuntimeError(f"{chave} ainda não foi enviado; a data dele sai da agenda.")
        data = datetime.fromisoformat(quando)
        datas[chave] = data if data.tzinfo else data.replace(tzinfo=fuso)
    return datas


def _mudar_data(yt, video_id: str, quando: datetime) -> None:
    """Muda o publishAt de um vídeo agendado, mantendo o resto do status (o update substitui a parte inteira)."""
    atual = yt.videos().list(part="status", id=video_id).execute()["items"][0]["status"]
    status = {k: atual[k] for k in ("privacyStatus", "selfDeclaredMadeForKids", "embeddable", "license",
                                    "publicStatsViewable", "containsSyntheticMedia") if k in atual}
    status["publishAt"] = quando.isoformat()
    yt.videos().update(part="status", body={"id": video_id, "status": status}).execute()


def _trocar_link_nos_shorts(yt, estado: dict, velho: str, novo: str) -> None:
    """Os Shorts já enviados levam o link do longo na descrição: troca o antigo pelo novo."""
    for chave, feito in estado.items():
        if not chave.startswith("short_"):
            continue
        itens = yt.videos().list(part="snippet", id=feito["id"]).execute().get("items", [])
        if not itens or velho not in itens[0]["snippet"].get("description", ""):
            continue
        snippet = itens[0]["snippet"]
        snippet["description"] = snippet["description"].replace(velho, novo)
        yt.videos().update(part="snippet", body={"id": feito["id"], "snippet": {
            k: snippet[k] for k in ("title", "description", "tags", "categoryId", "defaultLanguage", "defaultAudioLanguage")
            if k in snippet}}).execute()
        log(f"  Link do vídeo longo atualizado na descrição de {chave} ({feito['url']})")


def _subir(yt, config: dict, item: dict) -> str:
    from googleapiclient.http import MediaFileUpload

    c = config["youtube"]
    corpo = {
        "snippet": {
            "title": item["titulo"][:100], "description": item["descricao"], "tags": item["tags"],
            "categoryId": str(c["categoria"]), "defaultLanguage": c["idioma"], "defaultAudioLanguage": c["idioma"],
        },
        "status": {
            "privacyStatus": "private", "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": item["sintetico"],
        },
    }
    if item.get("quando"):  # sem data: fica privado até alguém publicar no Studio (usado em testes)
        corpo["status"]["publishAt"] = item["quando"].isoformat()
    midia = MediaFileUpload(str(item["arquivo"]), chunksize=16 * 1024 * 1024, resumable=True)
    pedido = yt.videos().insert(part="snippet,status", body=corpo, media_body=midia)
    resposta = None
    while resposta is None:
        progresso, resposta = pedido.next_chunk()
        if progresso:
            log(f"  {progresso.progress() * 100:.0f}%")
    return resposta["id"]


def _thumb(yt, video_id: str, arquivo: Path) -> None:
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    if not arquivo.exists():
        return
    try:
        yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(arquivo))).execute()
    except HttpError as erro:
        # capa própria exige canal verificado por telefone (e, em Shorts, o Programa de Parcerias)
        log(f"  Capa não enviada ({erro.status_code}): escolha no YouTube Studio. {erro.reason}")


def _legendas(yt, config: dict, video_id: str, arquivo: Path) -> None:
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    if not arquivo.exists():
        return
    try:
        yt.captions().insert(
            part="snippet",
            body={"snippet": {"videoId": video_id, "language": config["youtube"]["idioma"], "name": "Português"}},
            media_body=MediaFileUpload(str(arquivo), mimetype="application/octet-stream"),
        ).execute()
    except HttpError as erro:
        log(f"  Legenda não enviada ({erro.status_code}): envie o .srt no YouTube Studio. {erro.reason}")
