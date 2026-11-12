"""Reels no Instagram pelo Zernio (zernio.com), que publica com o app da Meta deles.

Cada Short do projeto vira um Reel com a capa B, legenda (título, descrição, chamada para o vídeo completo
e hashtags) e o aviso de IA quando o trecho tem imagem gerada. O horário é o mesmo do Short no YouTube;
se esse já passou (Short antigo), o Reel entra numa fila: um por dia a partir de amanhã (ou de --inicio),
no horário instagram.hora do config.yaml.

Só envia com confirmar=True. O Zernio guarda o post e publica sozinho na hora marcada (o Mac pode estar
desligado). O que já foi agendado fica em projetos/<slug>/instagram.json, para nunca enviar duas vezes.

Chave: ZERNIO_API_KEY no .env (zernio.com/dashboard/api-keys). A conta do Instagram é conectada no painel do Zernio.
A API do Instagram não põe adesivo de link em story: o story do manual continua à mão.
"""

import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from . import youtube
from .util import EtapaPendente, carregar_env, ler_json, log, salvar_json

API = "https://zernio.com/api/v1"
TIMEOUT = 60
LIMITE_LEGENDA = 2200
# horário a menos disso de agora não dá tempo de o Zernio buscar o vídeo: vai para a fila
FOLGA = timedelta(minutes=15)


def enviar(config: dict, projeto: Path, confirmar: bool = False, inicio: str | None = None,
           reagendar: list[str] | None = None, apenas: list[str] | None = None) -> None:
    """Com `apenas` (ex.: ["short_01", "short_03"]), agenda só esses Shorts (ex.: os mais vistos de um projeto antigo)."""
    estado_arq = projeto / "instagram.json"
    estado = ler_json(estado_arq) if estado_arq.exists() else {}
    novas_datas = youtube._novas_datas(config, reagendar or [], estado)
    itens = agenda(config, projeto, inicio, estado, apenas)
    if not itens:
        raise RuntimeError("Nada para enviar: rode a etapa de Shorts antes.")

    zernio = _sessao(obrigatoria=confirmar)
    if zernio and estado:
        _atualizar_situacao(zernio, estado)
        salvar_json(estado_arq, estado)
    for chave, quando in novas_datas.items():
        log(f"Reagendar {chave}: {datetime.fromisoformat(estado[chave]['publica_em']):%d/%m %H:%M} → {quando:%d/%m %H:%M}")
    comentario = youtube.comentario_manual(config, "reels_tiktok")
    # Reel ainda agendado sem o comentário do manual (enviado antes de ele existir) ou com um texto antigo: entra por edição do post
    sem_comentario = [c for c, feito in estado.items() if comentario and feito.get("status") == "scheduled"
                      and feito.get("comentario") != comentario and (not apenas or c in apenas)]
    log("Agenda do Instagram (Reels):")
    for item in itens:
        feito = estado.get(item["chave"])
        situacao = (f"{feito['status']}" + (f": {feito['url']}" if feito.get("url") else "")) if feito else "a enviar"
        log(f"  {item['quando']:%d/%m %H:%M}  {item['chave']}  {item['titulo']}  ({situacao})")
        if feito and feito.get("comentario") and item["chave"] not in sem_comentario:
            log("      💬 1º comentário do manual: incluído no post")
        elif comentario and (not feito or item["chave"] in sem_comentario):
            acao = "" if not feito else " (trocar no post agendado)" if feito.get("comentario") else " (incluir no post agendado)"
            log(f"      💬 1º comentário do manual{acao}: {comentario}")
    if not confirmar:
        raise EtapaPendente("Confira a agenda acima. Para agendar no Instagram, rode de novo com --confirmar "
                            "(opcional: --inicio AAAA-MM-DD para a fila dos Shorts antigos).")

    conta = _conta(zernio, config["instagram"]["conta"])
    log(f"Conta: @{conta['username']}")
    for chave, quando in novas_datas.items():
        if estado[chave]["status"] != "scheduled":
            raise RuntimeError(f"{chave} está \"{estado[chave]['status']}\"; só dá para reagendar o que ainda não saiu.")
        _ok(zernio.put(f"{API}/posts/{estado[chave]['id']}", json={"scheduledFor": quando.isoformat()}, timeout=TIMEOUT))
        estado[chave]["publica_em"] = quando.isoformat()
        salvar_json(estado_arq, estado)
        log(f"  {chave} agora publica em {quando:%d/%m %H:%M}")
    for chave in sem_comentario:
        _incluir_comentario(zernio, estado[chave]["id"], comentario)
        estado[chave]["comentario"] = comentario
        salvar_json(estado_arq, estado)
        log(f"  {chave}: 1º comentário do manual incluído no post agendado")
    for item in itens:
        if item["chave"] in estado:
            continue
        log(f"Enviando {item['chave']}: {item['titulo']}…")
        post = _agendar(zernio, conta["_id"], projeto, item, comentario)
        estado[item["chave"]] = {"id": post["_id"], "status": post["status"], "publica_em": item["quando"].isoformat(),
                                 "titulo": item["titulo"]}
        if comentario:
            estado[item["chave"]]["comentario"] = comentario
        salvar_json(estado_arq, estado)
        if post["status"] == "failed":
            erro = "; ".join(p.get("errorMessage") or "" for p in post.get("platforms", []))
            raise RuntimeError(f"O Instagram recusou {item['chave']}: {erro}")
        log(f"  {post['status']} para {item['quando']:%d/%m %H:%M} (post {post['_id']} no Zernio)")
    log("Pronto. Os Reels aparecem como agendados no painel do Zernio (zernio.com/dashboard) e saem sozinhos "
        "na hora; rode sem --confirmar depois para ver o link de cada um.")


def agenda(config: dict, projeto: Path, inicio: str | None, estado: dict, apenas: list[str] | None = None) -> list[dict]:
    """Um Reel por Short, no horário do Short no YouTube; os que já passaram vão para a fila diária."""
    c = config["instagram"]
    fuso = ZoneInfo(config["youtube"]["fuso"])
    yt_arq = projeto / "youtube.json"
    shorts_yt = [i for i in youtube.agenda(config, projeto, inicio, ler_json(yt_arq) if yt_arq.exists() else {})
                 if i["tipo"] == "short" and (not apenas or i["chave"] in apenas or i["chave"] in estado)]
    dados = ler_json(projeto / "shorts.json")["shorts"]
    tags = (ler_json(projeto / "publicacao.json").get("tags", []) if (projeto / "publicacao.json").exists() else [])

    dia = datetime.fromisoformat(inicio).date() if inicio else (datetime.now(fuso) + timedelta(days=1)).date()
    h, m = (int(x) for x in c["hora"].split(":"))
    fila = (datetime(dia.year, dia.month, dia.day, h, m, tzinfo=fuso) + timedelta(days=d) for d in range(10_000))
    limite = datetime.now(fuso) + FOLGA

    fixos = {i["chave"]: datetime.fromisoformat(estado[i["chave"]]["publica_em"]) if i["chave"] in estado else i["quando"]
             for i in shorts_yt if i["chave"] in estado or i["quando"] >= limite}
    ocupados = {q.date() for q in fixos.values()}  # a fila pula os dias que já têm Reel

    itens = []
    for item in sorted(shorts_yt, key=lambda i: i["quando"]):
        chave = item["chave"]
        short = dados[int(chave.split("_")[1]) - 1]
        quando = fixos.get(chave)
        while quando is None or (chave not in fixos and quando.date() in ocupados):
            quando = next(fila)
        ocupados.add(quando.date())
        capa = projeto / "shorts" / f"{chave}_capa_{c['capa']}.jpg"
        itens.append({"chave": chave, "titulo": short["titulo"], "arquivo": item["arquivo"],
                      "capa": capa if capa.exists() else item["thumb"], "legenda": _legenda(c, short, tags),
                      "sintetico": item["sintetico"], "quando": quando})
    return sorted(itens, key=lambda i: i["quando"])


def _legenda(c: dict, short: dict, tags: list[str]) -> str:
    """Título, descrição, chamada para o vídeo completo e hashtags (sem repetir; legenda do Instagram não tem link)."""
    hashtags, vistas = [], set()
    proprias = short.get("hashtags_ig", "").split()  # hashtags do assunto escolhidas na etapa de Shorts
    for tag in (proprias or c["hashtags"] + ["#" + re.sub(r"[^\w]", "", t) for t in tags if " " not in t][:3]):
        if tag.lower() not in vistas:
            vistas.add(tag.lower())
            hashtags.append(tag)
    partes = [short["titulo"], short.get("descricao", ""), c["chamada"].strip(), " ".join(hashtags)]
    return "\n\n".join(p for p in partes if p)[:LIMITE_LEGENDA]


def _agendar(zernio: requests.Session, conta_id: str, projeto: Path, item: dict, comentario: str | None) -> dict:
    dados = {"shareToFeed": True, "isAiGenerated": item["sintetico"]}
    if comentario:  # o Zernio comenta logo depois de publicar; fixar é pelo app
        dados["firstComment"] = comentario
    if item["capa"] and item["capa"].exists():
        dados["instagramThumbnail"] = _subir_arquivo(zernio, item["capa"], "image/jpeg")
    video = _subir_arquivo(zernio, item["arquivo"], "video/mp4")
    corpo = {
        "content": item["legenda"],
        "mediaItems": [{"type": "video", "url": video}],
        "platforms": [{"platform": "instagram", "accountId": conta_id, "platformSpecificData": dados}],
        "scheduledFor": item["quando"].isoformat(),
    }
    # a mesma chave numa nova tentativa (rede caiu no meio) devolve o post já criado em vez de duplicar
    chave = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{projeto.name}/{item['chave']}/{item['quando'].isoformat()}"))
    resposta = zernio.post(f"{API}/posts", json=corpo, headers={"Idempotency-Key": chave}, timeout=TIMEOUT)
    return _ok(resposta)["post"]


def _incluir_comentario(zernio: requests.Session, post_id: str, comentario: str) -> None:
    """Põe o 1º comentário num post já agendado. A edição troca a lista de plataformas inteira: reenvia cada uma
    com os dados que já tinha (capa, aviso de IA…) mais o comentário."""
    post = _ok(zernio.get(f"{API}/posts/{post_id}", timeout=TIMEOUT))["post"]
    plataformas = []
    for p in post["platforms"]:
        conta = p["accountId"]["_id"] if isinstance(p["accountId"], dict) else p["accountId"]
        dados = dict(p.get("platformSpecificData") or {})
        if p["platform"] == "instagram":
            dados["firstComment"] = comentario
        plataformas.append({"platform": p["platform"], "accountId": conta, "platformSpecificData": dados})
    antes = post["scheduledFor"]
    post = _ok(zernio.put(f"{API}/posts/{post_id}", json={"platforms": plataformas, "scheduledFor": antes},
                          timeout=TIMEOUT))["post"]
    if not any((p.get("platformSpecificData") or {}).get("firstComment") == comentario for p in post["platforms"]):
        raise RuntimeError(f"O Zernio não guardou o comentário no post {post_id}; confira no painel.")
    if post["status"] != "scheduled" or post["scheduledFor"] != antes:
        raise RuntimeError(f"O post {post_id} mudou para {post['status']} em {post['scheduledFor']} depois da edição "
                           f"(era scheduled em {antes}); confira no painel do Zernio.")


def _subir_arquivo(zernio: requests.Session, arquivo: Path, tipo: str) -> str:
    """Envia o arquivo para o armazenamento do Zernio e devolve o endereço público que vai no post."""
    destino = _ok(zernio.post(f"{API}/media/presign", timeout=TIMEOUT, json={
        "filename": arquivo.name, "contentType": tipo, "size": arquivo.stat().st_size}))
    with arquivo.open("rb") as dados:  # sem o cabeçalho de autorização: a URL já vem assinada
        requests.put(destino["uploadUrl"], data=dados, headers={"Content-Type": tipo}, timeout=600).raise_for_status()
    log(f"  {arquivo.name} enviado ({arquivo.stat().st_size / 1e6:.0f} MB)")
    return destino["publicUrl"]


def _atualizar_situacao(zernio: requests.Session, estado: dict) -> None:
    """Traz do Zernio a situação de cada post (agendado, publicado, falhou) e o link do Reel publicado."""
    for feito in estado.values():
        if feito.get("status") in ("published", "cancelled"):
            continue
        post = _ok(zernio.get(f"{API}/posts/{feito['id']}", timeout=TIMEOUT))["post"]
        feito["status"] = post["status"]
        for plataforma in post.get("platforms", []):
            if plataforma.get("platformPostUrl"):
                feito["url"] = plataforma["platformPostUrl"]
            if plataforma.get("errorMessage"):
                feito["erro"] = plataforma["errorMessage"]


def _conta(zernio: requests.Session, usuario: str) -> dict:
    contas = _ok(zernio.get(f"{API}/accounts", params={"platform": "instagram"}, timeout=TIMEOUT))["accounts"]
    for conta in contas:
        if conta.get("username", "").lower() == usuario.lower():
            if conta.get("needsReconnection") or not conta.get("isActive", True):
                raise EtapaPendente(f"A conta @{usuario} precisa ser reconectada no painel do Zernio.")
            return conta
    achadas = ", ".join("@" + c.get("username", "?") for c in contas) or "nenhuma"
    raise EtapaPendente(f"A conta @{usuario} não está conectada no Zernio (conectadas: {achadas}). "
                        "Conecte em zernio.com/dashboard ou corrija instagram.conta no config.yaml.")


def _sessao(obrigatoria: bool) -> requests.Session | None:
    carregar_env()
    chave = os.environ.get("ZERNIO_API_KEY", "")
    if not chave:
        if obrigatoria:
            raise EtapaPendente("Falta ZERNIO_API_KEY no .env. Siga a seção \"Instagram pelo Zernio\" do WORKFLOW.md.")
        return None
    sessao = requests.Session()
    sessao.headers["Authorization"] = f"Bearer {chave}"
    return sessao


def _ok(resposta: requests.Response) -> dict:
    """JSON da resposta; erro do Zernio vira mensagem legível (207 é sucesso parcial e passa: quem chama confere o status)."""
    if resposta.status_code >= 400:
        try:
            corpo = resposta.json()
            motivo = corpo.get("error") or corpo
            if corpo.get("details"):
                motivo = f"{motivo} {corpo['details']}"
        except ValueError:
            motivo = resposta.text[:300]
        raise RuntimeError(f"Zernio respondeu {resposta.status_code}: {motivo}")
    return resposta.json()
