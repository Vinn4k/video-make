"""Avisos no Telegram: vídeo pronto, etapa parada e pergunta do Claude sem resposta.

Usa um bot do Telegram (TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env).
Nunca derruba quem chamou: sem token ou sem rede, só registra e segue.

Pela linha de comando:
  .venv/bin/python -m pipeline.telegram "texto"               # envia agora
  .venv/bin/python -m pipeline.telegram --foto thumb.png "legenda"
  .venv/bin/python -m pipeline.telegram --hook espera          # hooks do Claude Code (.claude/settings.json)
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

from pipeline.util import RAIZ, carregar_env, log

API = "https://api.telegram.org/bot{token}/{metodo}"
TIMEOUT = 20
# pergunta do Claude parada há mais que isso vira mensagem no celular
ESPERA_S = 90


def _credenciais() -> tuple[str, str]:
    carregar_env()
    return os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")


def enviar(texto: str, foto: Path | None = None) -> bool:
    """Manda texto (ou foto com legenda) para o chat configurado. Devolve se o Telegram aceitou."""
    token, chat = _credenciais()
    if not (token and chat):
        log("Telegram sem TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID no .env; aviso não enviado.")
        return False
    try:
        if foto:
            with open(foto, "rb") as f:
                r = requests.post(API.format(token=token, metodo="sendPhoto"), timeout=TIMEOUT,
                                  data={"chat_id": chat, "caption": texto[:1024]}, files={"photo": f})
        else:
            r = requests.post(API.format(token=token, metodo="sendMessage"), timeout=TIMEOUT,
                              data={"chat_id": chat, "text": texto[:4096]})
    except (requests.RequestException, OSError) as exc:
        log(f"Falha ao enviar para o Telegram: {exc}")
        return False
    if r.status_code != 200:
        log(f"Telegram recusou o envio: {r.status_code} {r.text[:200]}")
        return False
    return True


# --- hooks do Claude Code -------------------------------------------------------------------------------
# Stop / AskUserQuestion / pedido de permissão soltam uma espera; passados ESPERA_S, ela relê o transcript da
# sessão e só envia se nada chegou do usuário desde então. O transcript é a prova da resposta: vale para
# várias sessões ao mesmo tempo e para resposta dada enquanto um comando longo ainda roda.

def _hook_espera(evento: dict) -> None:
    """Anota onde o transcript está agora e solta um processo que confere depois de ESPERA_S."""
    texto = _texto_da_espera(evento)
    if not texto:
        return
    transcript = evento.get("transcript_path") or ""
    inicio = Path(transcript).stat().st_size if transcript and Path(transcript).exists() else 0
    subprocess.Popen([sys.executable, "-m", "pipeline.telegram", "--aguardar", transcript, str(inicio), texto],
                     cwd=RAIZ, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def _aguardar(transcript: str, inicio: int, texto: str) -> None:
    time.sleep(ESPERA_S)
    if _respondeu(transcript, inicio):
        return
    sessao = _titulo_da_sessao(transcript)
    enviar(f"⏳ video make{f' — {sessao}' if sessao else ''}: o Claude está esperando você há "
           f"{ESPERA_S // 60}min{ESPERA_S % 60:02d}\n\n{texto}")


def _respondeu(transcript: str, inicio: int) -> bool:
    """Chegou algo do usuário depois de `inicio`? (mensagem nova, resposta de pergunta, permissão dada)"""
    if not transcript or not Path(transcript).exists():
        return False
    with open(transcript, "rb") as f:
        f.seek(inicio)
        novas = f.read().decode(errors="ignore").splitlines()
    for linha in novas:
        try:
            tipo = json.loads(linha).get("type")
        except (json.JSONDecodeError, AttributeError):
            continue
        if tipo in ("user", "queue-operation"):
            return True
    return False


def _titulo_da_sessao(transcript: str) -> str:
    """Nome da sessão no app, para saber de qual conversa é a pergunta."""
    if not transcript or not Path(transcript).exists():
        return ""
    titulo = ""
    for linha in Path(transcript).read_text(errors="ignore").splitlines():
        if '"custom-title"' in linha:
            try:
                titulo = json.loads(linha).get("customTitle") or titulo
            except json.JSONDecodeError:
                pass
    return titulo


def _texto_da_espera(evento: dict) -> str:
    """O que mandar no celular, ou "" quando não há pergunta (fim de turno sem pergunta não avisa)."""
    nome = evento.get("hook_event_name")
    if nome == "PreToolUse":  # AskUserQuestion
        perguntas = (evento.get("tool_input") or {}).get("questions") or []
        return "\n\n".join(
            p.get("question", "") + "\n" + "\n".join(f"• {o.get('label', '')}" for o in p.get("options", []))
            for p in perguntas).strip()
    if nome == "Notification":
        return evento.get("message") or "Pedido de permissão aguardando."
    if nome == "Stop":
        return _pergunta_do_turno(evento.get("transcript_path"), evento.get("last_assistant_message"))
    return ""


def _pergunta_do_turno(transcript: str | None, ultima: str | None) -> str:
    """Pergunta deixada no fim do turno: a do quadro de próximo passo, ou a última fala se terminar com '?'."""
    textos, pergunta = [], ""
    if transcript and Path(transcript).exists():
        linhas = Path(transcript).read_text().splitlines()[-200:]
        for linha in linhas:
            try:
                item = json.loads(linha)
            except json.JSONDecodeError:
                continue
            msg = item.get("message") or {}
            if item.get("type") == "user" and isinstance(msg.get("content"), str):
                textos, pergunta = [], ""  # nova mensagem do usuário: começa outro turno
                continue
            if item.get("type") != "assistant" or not isinstance(msg.get("content"), list):
                continue
            for bloco in msg["content"]:
                if bloco.get("type") == "text" and bloco.get("text", "").strip():
                    textos.append(bloco["text"].strip())
                elif bloco.get("type") == "tool_use" and bloco.get("name", "").endswith("wrap_up"):
                    entrada = bloco.get("input") or {}
                    if entrada.get("ask"):
                        pergunta = f"{entrada.get('recap', '')}\n\n❓ {entrada['ask']}".strip()
    ultima = (ultima or (textos[-1] if textos else "")).strip()
    if pergunta:
        return pergunta
    return ultima[-1500:] if ultima.rstrip("*_` ").endswith("?") else ""


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["--hook"]:
        try:
            _hook_espera(json.load(sys.stdin))
        except Exception:  # hook nunca pode travar o Claude
            pass
    elif args[:1] == ["--aguardar"]:
        _aguardar(args[1], int(args[2]), args[3])
    elif args[:1] == ["--foto"]:
        sys.exit(0 if enviar(" ".join(args[2:]), Path(args[1])) else 1)
    elif args:
        sys.exit(0 if enviar(" ".join(args)) else 1)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
