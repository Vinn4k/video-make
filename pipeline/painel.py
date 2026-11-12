"""Painel do canal: vídeos em alta no nicho (para escolher temas) e a evolução das métricas do canal.

    .venv/bin/python -m pipeline.painel [porta]   # http://127.0.0.1:8770

Lê o que já está gravado, sem gastar cota da API:
- projetos/canal/tendencias/*.json (run.py --projeto canal --so tendencias). Quando a rodada tem o _brutos.json,
  a página mostra tudo o que a busca trouxe e refiltra ali mesmo (views, minutos, dias, idioma);
- projetos/*/metricas/*.json (run.py --projeto <nome> --so metricas). Cada rodada é um ponto do gráfico.
Os botões "atualizar" rodam essas mesmas etapas do run.py no projeto canal e recarregam a página quando terminam.
"""

import json
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import tendencias
from .util import PROJETOS, RAIZ, carregar_config, ler_json

PAGINA = Path(__file__).with_name("painel.html")
CANAL = PROJETOS / "canal"
TAREFA = {"etapa": None, "rodando": False, "codigo": None, "inicio": None, "fim": None}


def _rodadas_tendencias() -> list[str]:
    return sorted((p.stem for p in (CANAL / "tendencias").glob("????-??-??_????.json")), reverse=True)


def _tendencias(rodada: str | None) -> dict:
    rodadas = _rodadas_tendencias()
    c = carregar_config()["tendencias"]
    if not rodadas:
        return {"rodadas": [], "config": c, "videos": []}
    rodada = rodada if rodada in rodadas else rodadas[0]
    filtrados = ler_json(CANAL / "tendencias" / f"{rodada}.json")
    termos = {v["id"]: v.get("termos", []) for v in filtrados}
    brutos_arq = CANAL / "tendencias" / f"{rodada}_brutos.json"
    if not brutos_arq.exists():  # rodada antiga: só os que passaram no filtro daquele dia
        videos = [{**v, "pt": True, "fora": False, "aprovado": True} for v in filtrados]
        return {"rodadas": rodadas, "rodada": rodada, "config": c, "brutos": False, "videos": videos}

    quando = datetime.strptime(rodada, "%Y-%m-%d_%H%M").astimezone(timezone.utc)
    videos = []
    for v in ler_json(brutos_arq):
        s = v["snippet"]
        views = int(v["statistics"].get("viewCount", 0))
        publicado = datetime.fromisoformat(s["publishedAt"].replace("Z", "+00:00"))
        dias = max((quando - publicado).total_seconds() / 86400, 0.25)
        videos.append({
            "id": v["id"], "url": f"https://youtu.be/{v['id']}", "titulo": s["title"], "canal": s["channelTitle"],
            "publicado": s["publishedAt"], "dias": round(dias, 1), "views": views, "views_dia": round(views / dias),
            "likes": int(v["statistics"].get("likeCount", 0)), "comentarios": int(v["statistics"].get("commentCount", 0)),
            "minutos": round(tendencias._minutos(v["contentDetails"].get("duration", "PT0S"))),
            "termos": termos.get(v["id"], []), "descricao": s.get("description", "")[:300],
            "pt": tendencias._em_portugues(s), "fora": int(s.get("categoryId", 0)) in c.get("categorias_fora", []),
            "aprovado": v["id"] in termos,
        })
    return {"rodadas": rodadas, "rodada": rodada, "config": c, "brutos": True, "videos": videos}


def _metricas() -> dict:
    """Todas as rodadas de métricas de todos os projetos; o canal inteiro vem de projetos/canal."""
    rodadas = []
    for arq in sorted(PROJETOS.glob("*/metricas/????-??-??_????.json")):
        dados = ler_json(arq)
        videos = []
        for v in dados.get("videos", []):
            a = v.get("analytics") or {}
            videos.append({
                "id": v["id"], "url": v.get("url"), "titulo": v.get("titulo"), "status": v.get("status"),
                "publicado": v.get("publicado") or v.get("publica_em"), "duracao": v.get("duracao"),
                "views": v.get("views", 0), "likes": v.get("likes", 0), "comentarios": v.get("comentarios", 0),
                "minutos": a.get("estimatedMinutesWatched"), "inscritos": a.get("subscribersGained"),
                "compart": a.get("shares"), "media_seg": a.get("averageViewDuration"),
                "pct": a.get("averageViewPercentage"),
            })
        rodadas.append({"projeto": arq.parent.parent.name, "quando": dados.get("gerado_em"), "videos": videos})
    return {"rodadas": rodadas}


def _atualizar(etapa: str) -> bool:
    if TAREFA["rodando"]:
        return False
    log = CANAL / f"painel_{etapa}.log"

    def rodar():
        with open(log, "w") as saida:
            codigo = subprocess.call([sys.executable, "run.py", "--projeto", "canal", "--so", etapa],
                                     cwd=RAIZ, stdout=saida, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        TAREFA.update(rodando=False, codigo=codigo, fim=datetime.now().isoformat(timespec="seconds"))

    TAREFA.update(etapa=etapa, rodando=True, codigo=None, inicio=datetime.now().isoformat(timespec="seconds"), fim=None)
    threading.Thread(target=rodar, daemon=True).start()
    return True


def _estado_tarefa() -> dict:
    saida = dict(TAREFA)
    log = CANAL / f"painel_{TAREFA['etapa']}.log" if TAREFA["etapa"] else None
    saida["log"] = log.read_text(errors="replace")[-3000:] if log and log.exists() else ""
    return saida


def servir(porta: int = 8770) -> None:
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _enviar(self, corpo: bytes, tipo: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def _json(self, dados, status: int = 200):
            self._enviar(json.dumps(dados, ensure_ascii=False).encode(), "application/json", status)

        def do_GET(self):
            url = urlparse(self.path)
            caminho = unquote(url.path).strip("/")
            p = {k: v[0] for k, v in parse_qs(url.query).items()}
            if caminho in ("", "index.html"):
                return self._enviar(PAGINA.read_bytes(), "text/html; charset=utf-8")
            if caminho == "api/tendencias":
                return self._json(_tendencias(p.get("rodada")))
            if caminho == "api/metricas":
                return self._json(_metricas())
            if caminho == "api/tarefa":
                return self._json(_estado_tarefa())
            self._enviar(b"nao encontrado", "text/plain", 404)

        def do_POST(self):
            caminho = unquote(urlparse(self.path).path).strip("/")
            etapa = caminho.removeprefix("api/atualizar/")
            if etapa not in ("tendencias", "metricas"):
                return self._enviar(b"nao encontrado", "text/plain", 404)
            if not _atualizar(etapa):
                return self._json({"erro": f"já está rodando: {TAREFA['etapa']}"}, 409)
            self._json({"ok": True})

    print(f"  Painel do canal em http://127.0.0.1:{porta}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", porta), H).serve_forever()


if __name__ == "__main__":
    servir(int(sys.argv[1]) if len(sys.argv) > 1 else 8770)
