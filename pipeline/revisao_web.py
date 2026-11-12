"""Página local para o usuário aprovar à mão a mídia de cada cena e escolher substitutas, antes do render.

    .venv/bin/python -m pipeline.revisao_web servir <projeto> [porta]   # http://127.0.0.1:8765
    .venv/bin/python -m pipeline.revisao_web aplicar <projeto>           # apaga as reprovadas e prepara a nova busca

Cada cena mostra a narração, a mídia escolhida, uma caixa (ok, trocar, trocar por IA) e um campo de observação.
O botão "opções" busca no Pixabay, no Pexels e no YouTube; o usuário clica na que quer e ela vai direto para a cena.
Do YouTube baixa só o trecho escolhido (início e fim); o filtro Creative Commons é opcional.
Tudo é salvo na hora em revisao_midia.json, cenas.json e creditos.json.
"""

import json
import mimetypes
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .util import PROJETOS, RAIZ, carregar_env, ler_json, log, salvar_json

PAGINA = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Revisão da mídia</title>
<style>
body{margin:0;background:#0B0F14;color:#eee;font:14px system-ui,sans-serif}
header{position:sticky;top:0;z-index:2;background:#0B0F14;padding:12px 20px;border-bottom:1px solid #333;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header b{color:#F5C518}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;padding:16px}
.c{background:#151b23;border-radius:10px;overflow:hidden;border:3px solid transparent}
.c.trocar,.c.ia{border-color:#e5484d}.c.ok{border-color:#2f9e44}
.c.ultimo{outline:4px solid #F5C518;outline-offset:3px}.op.sel{outline:4px solid #F5C518}
.tag{display:inline-block;background:#F5C518;color:#000;font-weight:800;font-size:11px;padding:1px 6px;border-radius:4px;margin-left:6px}
.m{aspect-ratio:16/9;background:#000;display:flex;align-items:center;justify-content:center}
.m img,.m video{width:100%;height:100%;object-fit:cover}
.t{padding:8px 10px}.id{color:#F5C518;font-weight:700}.tipo{color:#999;font-size:12px}
.n{font-size:13px;line-height:1.35;margin:6px 0;color:#ddd}
select,input,textarea{width:100%;box-sizing:border-box;margin-top:4px;padding:6px;background:#0B0F14;color:#eee;border:1px solid #444;border-radius:6px;font:inherit}
button{background:#F5C518;border:0;border-radius:6px;padding:6px 12px;font-weight:700;cursor:pointer}
button.sec{background:#2b3440;color:#eee}
#modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:5;overflow:auto}
#caixa{max-width:1300px;margin:30px auto;background:#151b23;border-radius:12px;padding:16px}
#ops{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;margin-top:12px}
.op{background:#0B0F14;border-radius:8px;overflow:hidden}.op img,.op video{width:100%;aspect-ratio:16/9;object-fit:cover;display:block}
.op .t{font-size:12px}.selo{display:inline-block;padding:1px 6px;border-radius:4px;font-size:11px;font-weight:700;background:#2b3440}
.cc{background:#2f9e44}.risco{background:#e5484d}
.linha{display:flex;gap:6px;align-items:center}.linha input{width:70px}
</style></head><body>
<header><b>Revisão da mídia</b><span id="cont"></span>
<label><input type="checkbox" id="filtro" style="width:auto"> só as não revisadas</label>
<label><input type="checkbox" id="filtro2" style="width:auto"> só as para trocar</label>
<button onclick="tudoOk()">Marcar as não revisadas como ok</button><span id="salvo"></span></header>
<main id="g"></main>
<div id="lb" onclick="if(event.target.id=='lb')fecharLb()" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:6;align-items:center;justify-content:center">
 <button class="sec" onclick="fecharLb()" style="position:absolute;top:16px;right:20px">fechar ✕</button><div id="lbc" style="max-width:92vw;max-height:88vh"></div></div>
<div id="modal"><div id="caixa">
 <div class="linha" style="justify-content:space-between"><b id="mt"></b><button class="sec" onclick="fechar()">fechar</button></div>
 <div class="n" id="mn"></div>
 <div class="linha" style="flex-wrap:wrap"><input id="q" style="flex:1;min-width:280px;width:auto" placeholder="busca (em inglês para os bancos; pode ser em português no YouTube)">
 <select id="fonte" style="width:auto"><option value="bancos">Pixabay + Pexels</option><option value="youtube">YouTube</option></select>
 <select id="lic" style="width:auto"><option value="todas">YouTube: todas as licenças</option><option value="cc">YouTube: só Creative Commons</option></select>
 <button onclick="buscar()">buscar</button></div>
 <div style="margin-top:10px;padding:10px;border:1px dashed #555;border-radius:8px">
  <b>Mídia do computador</b> <input type="file" id="arq" accept="image/*,video/*" style="width:auto" onchange="previaLocal()">
  <div id="loc"></div></div>
 <div id="player"></div><div id="ops"></div>
</div></div>
<script>
let cenas=[],rev={},atual=null,ultimo=null;
async function carregar(){cenas=await (await fetch('cenas')).json();rev=await (await fetch('revisao')).json();desenhar()}
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function desenhar(){const g=document.getElementById('g');g.innerHTML='';const so=document.getElementById('filtro').checked,so2=document.getElementById('filtro2').checked;
 let n=0;for(const c of cenas){const r=rev[c.id]||{};if(r.estado)n++;if(so&&r.estado)continue;if(so2&&!(r.estado=='trocar'||r.estado=='ia'))continue;
 const d=document.createElement('div');d.className='c '+(r.estado||'')+(c.id==ultimo?' ultimo':'');d.id='card'+c.id;
 const src=c.src?'arquivo/'+c.src:'';
 const midia=!src?`<span class="tipo" style="padding:12px;text-align:center">tela de template (${c.tipo}), sem foto:<br><b style="color:#eee">${esc(c.template)}</b></span>`
  :`<div onclick="ver('${src}',${c.video},${c.id})" style="cursor:zoom-in;width:100%;height:100%;position:relative"><img loading="lazy" src="miniatura/${c.id}?v=${encodeURIComponent(c.origem)}">${c.video?'<span style="position:absolute;left:8px;bottom:8px;background:#F5C518;color:#000;font-weight:700;padding:2px 8px;border-radius:4px">▶ clipe</span>':''}</div>`;
 d.innerHTML=`<div class="m">${midia}</div><div class="t"><span class="id">#${c.id}</span>${c.id==ultimo?'<span class="tag">você estava aqui</span>':''} <span class="tipo">bloco ${c.capitulo} · ${c.tipo} · ${esc(c.origem)}</span>
 <div class="n">${esc(c.texto)}</div>
 <select onchange="mudar(${c.id},this.value)"><option value="">— revisar —</option><option value="ok">ok</option><option value="trocar">trocar (nova busca)</option><option value="ia">trocar por imagem de IA</option></select>
 <input placeholder="nova busca em inglês (opcional)" value="${esc(r.busca)}" onchange="campo(${c.id},'busca',this.value)">
 <textarea rows="2" placeholder="observação (ex.: é de outro país, não combina com a fala)" onchange="campo(${c.id},'obs',this.value)">${esc(r.obs)}</textarea>
 ${c.src||c.tipo=='midia'?`<button style="margin-top:6px" onclick="abrir(${c.id})">opções: escolher outra mídia</button>`:''}</div>`;
 d.querySelector('select').value=r.estado||'';g.appendChild(d)}
 document.getElementById('cont').textContent=`${n} de ${cenas.length} revisadas · ${Object.values(rev).filter(r=>r.estado&&r.estado!='ok').length} para trocar`}
async function salvar(){await fetch('revisao',{method:'POST',body:JSON.stringify(rev)});document.getElementById('salvo').textContent='salvo '+new Date().toLocaleTimeString()}
function mudar(id,v){rev[id]={...(rev[id]||{}),estado:v};salvar();desenhar()}
function campo(id,k,v){rev[id]={...(rev[id]||{}),[k]:v};salvar()}
function tudoOk(){for(const c of cenas){if(!(rev[c.id]||{}).estado)rev[c.id]={...(rev[c.id]||{}),estado:'ok'}}salvar();desenhar()}
document.getElementById('filtro').onchange=desenhar;document.getElementById('filtro2').onchange=desenhar;
function abrir(id){ultimo=id;marcarUltimo();atual=cenas.find(c=>c.id==id);document.getElementById('modal').style.display='block';
 document.getElementById('mt').textContent='Cena #'+id+' · bloco '+atual.capitulo;document.getElementById('mn').textContent=atual.texto;
 document.getElementById('q').value=(rev[id]||{}).busca||atual.busca||'';document.getElementById('ops').innerHTML='';document.getElementById('player').innerHTML='';buscar()}
function fechar(){document.getElementById('modal').style.display='none';document.getElementById('player').innerHTML='';
 document.querySelectorAll('#ops .tela').forEach(e=>e.remove());const vl=document.getElementById('vloc');if(vl)vl.pause();document.querySelectorAll('#ops video').forEach(v=>v.pause())}
let busca_n=0;
async function buscar(){const minha=++busca_n;const ops=document.getElementById('ops');ops.innerHTML='<span class="tipo">buscando…</span>';
 const f=document.getElementById('fonte').value,l=document.getElementById('lic').value,q=document.getElementById('q').value;
 const r=await (await fetch(`opcoes?fonte=${f}&lic=${l}&q=${encodeURIComponent(q)}`)).json();
 if(minha!==busca_n)return; // chegou depois de uma busca mais nova: descarta
 if(r.erro){ops.innerHTML='<span class="tipo">'+esc(r.erro)+'</span>';return}
 ops.innerHTML='';window._ops=r.opcoes;r.opcoes.forEach((o,i)=>{const d=document.createElement('div');d.className='op';d.id='op'+i;
  if(o.fonte=='youtube'){d.innerHTML=`<img src="${o.previa}"><div class="t"><span class="selo ${o.cc?'cc':'risco'}">${o.cc?'Creative Commons':'sem licença livre'}</span> ${esc(o.duracao)}<br><b>${esc(o.titulo)}</b><br><span class="tipo">${esc(o.autor)}</span>
   <div class="linha" style="margin-top:6px"><button class="sec" onclick="assistir('${o.id}',document.getElementById('ini${i}').value,${i})">assistir</button>
   início <input id="ini${i}" placeholder="0:30"> fim <input id="fim${i}" placeholder="0:45"></div>
   <button style="margin-top:6px;width:100%" onclick="usarYt(${i})">baixar este trecho para a cena</button></div>`}
  else{d.innerHTML=`${o.tipo=='video'?`<video src="${o.previa_video||''}" poster="${o.previa}" muted loop preload="none" onmouseenter="this.play()" onmouseleave="this.pause()"></video>`:`<img src="${o.previa}">`}
   <div class="t"><span class="selo">${o.fonte} · ${o.tipo=='video'?'clipe':'foto'}</span> <span class="tipo">${esc(o.autor)}</span>
   <button style="margin-top:6px;width:100%" onclick="usar(${i})">usar nesta cena</button></div>`}
  ops.appendChild(d)})}
function previaLocal(){const f=document.getElementById('arq').files[0];const d=document.getElementById('loc');if(!f){d.innerHTML='';return}
 const url=URL.createObjectURL(f);
 if(f.type.startsWith('video')){d.innerHTML=`<video id="vloc" src="${url}" controls style="width:100%;max-height:420px;margin-top:8px;background:#000"></video>
  <div class="linha" style="margin-top:6px;flex-wrap:wrap">início <input id="lini" placeholder="0:10"> <button class="sec" onclick="document.getElementById('lini').value=fmt(document.getElementById('vloc').currentTime)">marcar início</button>
  fim <input id="lfim" placeholder="0:20"> <button class="sec" onclick="document.getElementById('lfim').value=fmt(document.getElementById('vloc').currentTime)">marcar fim</button>
  <button onclick="usarLocal()">usar este trecho na cena</button></div>`}
 else{d.innerHTML=`<img src="${url}" style="max-width:100%;max-height:420px;margin-top:8px"><div><button style="margin-top:6px" onclick="usarLocal()">usar esta foto na cena</button></div>`}}
function fmt(t){t=Math.round(t*10)/10;return Math.floor(t/60)+':'+String((t%60).toFixed(1)).padStart(4,'0')}
async function usarLocal(){const f=document.getElementById('arq').files[0];if(!f)return;let q=`cena=${atual.id}&nome=${encodeURIComponent(f.name)}`;
 if(f.type.startsWith('video')){const a=seg(document.getElementById('lini').value),b=seg(document.getElementById('lfim').value);
  if(a==null||b==null||b<=a||b-a>60){alert('Preencha início e fim do trecho (ex.: 0:10 e 0:20), no máximo 60 s');return}q+=`&inicio=${a}&fim=${b}`}
 document.getElementById('loc').innerHTML='<span class="tipo">enviando e cortando…</span>';
 const r=await (await fetch('enviar?'+q,{method:'POST',body:f})).json();
 if(r.erro){alert(r.erro);previaLocal();return}
 rev[atual.id]={...(rev[atual.id]||{}),estado:'ok',trocada:true};await salvar();document.getElementById('arq').value='';document.getElementById('loc').innerHTML='';
 cenas=await (await fetch('cenas')).json();fechar();desenhar();const e=document.getElementById('card'+atual.id);if(e)e.scrollIntoView({block:'center'})}
function seg(s){if(!s)return null;const p=s.split(':').map(Number);return p.length==2?p[0]*60+p[1]:p[0]}
function assistir(id,ini,i){document.querySelectorAll('.op').forEach(o=>{o.classList.remove('sel');const t=o.querySelector('.tela');if(t)t.remove();const g=o.querySelector('.tag');if(g)g.remove()});
 const op=document.getElementById('op'+i);op.classList.add('sel');
 op.insertAdjacentHTML('afterbegin',`<div class="tela"><iframe width="100%" style="aspect-ratio:16/9;border:0;display:block" src="https://www.youtube-nocookie.com/embed/${id}?start=${seg(ini)||0}&autoplay=1" allow="autoplay"></iframe></div>`);
 op.querySelector('.t').insertAdjacentHTML('afterbegin','<span class="tag">▶ assistindo</span> ');op.scrollIntoView({behavior:'smooth',block:'center'})}
async function enviar(corpo){const st=document.getElementById('ops');const r=await (await fetch('usar',{method:'POST',body:JSON.stringify(corpo)})).json();
 if(r.erro){alert(r.erro);return}rev[atual.id]={...(rev[atual.id]||{}),estado:'ok',trocada:true};await salvar();
 cenas=await (await fetch('cenas')).json();fechar();desenhar();const e=document.getElementById('card'+atual.id);if(e)e.scrollIntoView({block:'center'})}
function usar(i){const o=window._ops[i];document.getElementById('ops').innerHTML='<span class="tipo">baixando…</span>';enviar({cena:atual.id,...o})}
function usarYt(i){const o=window._ops[i];const a=seg(document.getElementById('ini'+i).value),b=seg(document.getElementById('fim'+i).value);
 if(a==null||b==null||b<=a||b-a>40){alert('Preencha início e fim (ex.: 0:30 e 0:45), no máximo 40 s');return}
 document.getElementById('ops').innerHTML='<span class="tipo">baixando o trecho do YouTube…</span>';enviar({cena:atual.id,...o,inicio:a,fim:b})}
function ver(src,video,id){if(id){ultimo=id;marcarUltimo()}const c=document.getElementById('lbc');c.innerHTML=video?`<video src="${src}" controls autoplay muted loop style="max-width:92vw;max-height:88vh"></video>`:`<img src="${src}" style="max-width:92vw;max-height:88vh">`;document.getElementById('lb').style.display='flex'}
function fecharLb(){document.getElementById('lb').style.display='none';document.getElementById('lbc').innerHTML=''}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){fecharLb();fechar()}});
function marcarUltimo(){document.querySelectorAll('.c.ultimo').forEach(e=>{e.classList.remove('ultimo');const t=e.querySelector('.tag');if(t)t.remove()});
 const e=document.getElementById('card'+ultimo);if(e){e.classList.add('ultimo');e.querySelector('.id').insertAdjacentHTML('afterend','<span class="tag">você estava aqui</span>')}}
carregar();
</script></body></html>"""


def _resumo(projeto: Path) -> list[dict]:
    lista = []
    for c in ler_json(projeto / "cenas.json"):
        m = c.get("midia") or {}
        template = (c.get("frase") or {}).get("texto") or (c.get("grafico") or {}).get("titulo") or (c.get("fluxo") or {}).get("titulo", "")
        lista.append({"id": c["id"], "capitulo": c["capitulo"], "tipo": c["tipo"], "texto": c["texto"], "template": template,
                      "busca": (c.get("busca") or [""])[0], "src": m.get("src", ""), "video": m.get("tipo") == "video",
                      "origem": m.get("origem_id", "")})
    return lista


def _miniatura(projeto: Path, cena_id: int) -> Path | None:
    """JPEG pequeno de cada mídia (no clipe, o quadro de 1 s): a página carrega rápido mesmo com centenas de clipes."""
    cena = next((c for c in ler_json(projeto / "cenas.json") if c["id"] == cena_id), None)
    midia = (cena or {}).get("midia") or {}
    origem = projeto / midia["src"] if midia.get("src") else None
    if not origem or not origem.exists():
        return None
    destino = projeto / "media" / ".miniaturas" / f"{origem.stem}.jpg"
    if not destino.exists() or destino.stat().st_mtime < origem.stat().st_mtime:
        destino.parent.mkdir(exist_ok=True)
        inicio = ["-ss", "1"] if midia.get("tipo") == "video" else []
        subprocess.run(["ffmpeg", "-v", "error", "-y", *inicio, "-i", str(origem), "-frames:v", "1", "-vf", "scale=480:-2",
                        "-q:v", "4", str(destino)], check=False)
    return destino if destino.exists() else None


def _opcoes_bancos(q: str) -> list[dict]:
    from . import midia
    lista = []
    for nome in ("pixabay", "pexels"):
        try:
            for o in midia.PROVEDORES[nome](q, 12):
                lista.append({**o, "fonte": nome, "previa_video": _previa_video(o)})
        except Exception as erro:  # o Pexels trava quando estoura o limite por hora; segue com o que veio
            log(f"{nome}: {erro}")
    return sorted(lista, key=lambda o: o["tipo"] != "video")


def _previa_video(o: dict) -> str:
    return o["url"] if o["tipo"] == "video" else ""


def _opcoes_youtube(q: str, so_cc: bool) -> list[dict]:
    from . import youtube
    yt = youtube._servico()
    filtro = {"videoLicense": "creativeCommon"} if so_cc else {}
    r = yt.search().list(part="snippet", q=q, type="video", maxResults=12, **filtro).execute()
    ids = [it["id"]["videoId"] for it in r.get("items", [])]
    if not ids:
        return []
    detalhes = yt.videos().list(part="contentDetails,status,snippet", id=",".join(ids)).execute()
    lista = []
    for v in detalhes.get("items", []):
        dur = re.findall(r"(\d+)([HMS])", v["contentDetails"]["duration"])
        seg = sum(int(n) * {"H": 3600, "M": 60, "S": 1}[u] for n, u in dur)
        lista.append({"fonte": "youtube", "id": v["id"], "titulo": v["snippet"]["title"], "autor": v["snippet"]["channelTitle"],
                      "previa": v["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
                      "duracao": f"{seg // 60}:{seg % 60:02d}", "cc": v["status"].get("license") == "creativeCommon"})
    return lista


def _usar(projeto: Path, pedido: dict) -> None:
    """Baixa a opção escolhida para media/cena_XXX e atualiza cenas.json e creditos.json."""
    from . import midia
    cenas = ler_json(projeto / "cenas.json")
    cena = next(c for c in cenas if c["id"] == int(pedido["cena"]))
    creditos_arq, rejeitadas_arq = projeto / "creditos.json", projeto / "midia_rejeitadas.json"
    creditos = ler_json(creditos_arq) if creditos_arq.exists() else {}
    rejeitadas = ler_json(rejeitadas_arq) if rejeitadas_arq.exists() else []
    antiga = cena.get("midia") or {}
    if antiga.get("src"):
        rejeitadas.append(antiga["origem_id"])
        (projeto / antiga["src"]).unlink(missing_ok=True)
        creditos.pop(Path(antiga["src"]).name, None)

    if pedido["fonte"] == "youtube":
        destino = projeto / "media" / f"cena_{cena['id']:03d}.mp4"
        rodar_ytdlp(pedido["id"], float(pedido["inicio"]), float(pedido["fim"]), destino)
        tipo, origem = "video", f"youtube-{pedido['id']}-{int(pedido['inicio'])}"
        credito = {"origem_id": origem, "pagina": f"https://www.youtube.com/watch?v={pedido['id']}", "autor": pedido["autor"],
                   "licenca": "CC BY (YouTube)" if pedido.get("cc") else "trecho do YouTube"}
    else:
        tipo = pedido["tipo"]
        destino = projeto / "media" / f"cena_{cena['id']:03d}{'.mp4' if tipo == 'video' else '.jpg'}"
        midia._baixar(pedido["url"], destino)
        origem = pedido["origem_id"]
        credito = {k: pedido[k] for k in ("origem_id", "pagina", "autor", "licenca")}
    cena["midia"] = {"tipo": tipo, "src": f"media/{destino.name}", "origem_id": origem, "nota": None,
                     "descricao": "escolhida na revisão manual"}
    if pedido["fonte"] == "youtube":  # trecho de outro canal: crédito pequeno na própria tela
        cena["midia"]["credito"] = f"Vídeo: {pedido['autor']} / YouTube"
    creditos[destino.name] = credito
    salvar_json(projeto / "cenas.json", cenas)
    salvar_json(creditos_arq, creditos)
    salvar_json(rejeitadas_arq, sorted(set(rejeitadas)))
    log(f"cena {cena['id']}: {origem}")


def _receber(projeto: Path, p: dict, corpo, tamanho: int) -> None:
    """Arquivo do computador do usuário: foto entra como está; vídeo é cortado no trecho pedido, até 1080p e sem som."""
    cenas = ler_json(projeto / "cenas.json")
    cena = next(c for c in cenas if c["id"] == int(p["cena"]))
    nome = Path(p["nome"]).name
    bruto = projeto / "media" / f".envio_{cena['id']:03d}{Path(nome).suffix.lower()}"
    with open(bruto, "wb") as f:
        resto = tamanho
        while resto > 0:
            parte = corpo.read(min(resto, 1 << 20))
            if not parte:
                break
            f.write(parte)
            resto -= len(parte)
    video = "inicio" in p
    destino = projeto / "media" / f"cena_{cena['id']:03d}_local{'.mp4' if video else '.jpg'}"
    if video:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", p["inicio"], "-to", p["fim"], "-i", str(bruto), "-an",
                        "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-vf", "scale=-2:'min(1080,ih)'", str(destino)],
                       check=True, capture_output=True)
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(bruto), "-vf", "scale='min(2400,iw)':-2", "-q:v", "2",
                        str(destino)], check=True, capture_output=True)
    bruto.unlink(missing_ok=True)
    antiga = cena.get("midia") or {}
    if antiga.get("src") and antiga["src"] != f"media/{destino.name}":
        (projeto / antiga["src"]).unlink(missing_ok=True)
    origem = f"local-{Path(nome).stem[:40]}" + (f"-{p['inicio']}" if video else "")
    cena["midia"] = {"tipo": "video" if video else "imagem", "src": f"media/{destino.name}", "origem_id": origem, "nota": None,
                     "descricao": f"arquivo do canal: {nome}", "credito": ("Vídeo" if video else "Imagem") + ": Divulgação"}
    salvar_json(projeto / "cenas.json", cenas)
    creditos = ler_json(projeto / "creditos.json") if (projeto / "creditos.json").exists() else {}
    creditos[destino.name] = {"origem_id": origem, "pagina": "", "autor": "Divulgação (enviadas ao canal)", "licenca": "uso com crédito"}
    salvar_json(projeto / "creditos.json", creditos)
    log(f"cena {cena['id']}: arquivo local {nome}")


def rodar_ytdlp(video_id: str, inicio: float, fim: float, destino: Path) -> None:
    """Só o trecho pedido, em até 1080p e sem som (a trilha do vídeo é a narração)."""
    bruto = destino.with_name(destino.stem + ".yt.mp4")
    subprocess.run([str(RAIZ / ".venv/bin/yt-dlp"), "--js-runtimes", "node", "-f", "bv*[height<=1080][ext=mp4]/bv*[height<=1080]/b",
                    "--download-sections", f"*{inicio}-{fim}", "--force-keyframes-at-cuts", "-o", str(bruto),
                    f"https://www.youtube.com/watch?v={video_id}"], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(bruto), "-an", "-c:v", "libx264", "-crf", "18", "-preset", "fast",
                    "-vf", "scale=-2:1080", str(destino)], check=True)
    bruto.unlink(missing_ok=True)


def servir(projeto: Path, porta: int = 8765) -> None:
    carregar_env()
    arq_rev = projeto / "revisao_midia.json"

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _enviar(self, corpo: bytes, tipo: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def _json(self, dados):
            self._enviar(json.dumps(dados, ensure_ascii=False).encode(), "application/json")

        def do_GET(self):
            url = urlparse(self.path)
            caminho = unquote(url.path).lstrip("/")
            if caminho in ("", "index.html"):
                return self._enviar(PAGINA.encode(), "text/html; charset=utf-8")
            if caminho == "cenas":
                return self._json(_resumo(projeto))
            if caminho == "revisao":
                return self._json(ler_json(arq_rev) if arq_rev.exists() else {})
            if caminho == "opcoes":
                p = {k: v[0] for k, v in parse_qs(url.query).items()}
                try:
                    if p.get("fonte") == "youtube":
                        return self._json({"opcoes": _opcoes_youtube(p.get("q", ""), p.get("lic") != "todas")})
                    return self._json({"opcoes": _opcoes_bancos(p.get("q", ""))})
                except Exception as erro:
                    return self._json({"erro": f"busca falhou: {erro}"[:300]})
            if caminho.startswith("miniatura/"):
                miniatura = _miniatura(projeto, int(caminho.split("/")[1]))
                if miniatura:
                    return self._enviar(miniatura.read_bytes(), "image/jpeg")
            if caminho.startswith("arquivo/"):
                alvo = (projeto / caminho[len("arquivo/"):]).resolve()
                if projeto.resolve() in alvo.parents and alvo.exists():
                    return self._enviar(alvo.read_bytes(), mimetypes.guess_type(alvo.name)[0] or "application/octet-stream")
            self.send_error(404)

        def do_POST(self):
            if self.path.split("?")[0].rstrip("/").endswith("enviar"):
                corpo = None
            else:
                corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path.rstrip("/").endswith("revisao"):
                arq_rev.write_text(json.dumps(corpo, ensure_ascii=False, indent=1))
                return self._json({})
            if self.path.split("?")[0].rstrip("/").endswith("enviar"):
                try:
                    _receber(projeto, {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}, self.rfile,
                             int(self.headers["Content-Length"]))
                    return self._json({})
                except Exception as erro:
                    detalhe = getattr(erro, "stderr", b"") or b""
                    return self._json({"erro": f"não deu: {erro} {detalhe[-300:].decode(errors='ignore')}"[:500]})
            if self.path.rstrip("/").endswith("usar"):
                try:
                    _usar(projeto, corpo)
                    return self._json({})
                except Exception as erro:
                    detalhe = getattr(erro, "stderr", b"") or b""
                    return self._json({"erro": f"não deu: {erro} {detalhe[-300:].decode(errors='ignore')}"[:500]})
            self.send_error(404)

    log(f"Revisão em http://127.0.0.1:{porta} (Ctrl+C para parar)")
    ThreadingHTTPServer(("127.0.0.1", porta), H).serve_forever()


def aplicar(projeto: Path) -> None:
    """Cenas reprovadas: a mídia vai para midia_rejeitadas.json e o arquivo sai, para o --so midia buscar outra."""
    rev = ler_json(projeto / "revisao_midia.json")
    cenas = ler_json(projeto / "cenas.json")
    arq_rej = projeto / "midia_rejeitadas.json"
    rejeitadas = ler_json(arq_rej) if arq_rej.exists() else []
    trocadas = 0
    for c in cenas:
        r = rev.get(str(c["id"])) or {}
        if r.get("estado") not in ("trocar", "ia") or not c.get("midia"):
            continue
        rejeitadas.append(c["midia"]["origem_id"])
        (projeto / c["midia"]["src"]).unlink(missing_ok=True)
        c["midia"] = None
        if r["estado"] == "ia":
            c["preferencia"] = "ia"
        if r.get("busca"):
            c["busca"] = [r["busca"]] + [b for b in c.get("busca", []) if b != r["busca"]]
        trocadas += 1
    salvar_json(arq_rej, sorted(set(rejeitadas)))
    salvar_json(projeto / "cenas.json", cenas)
    log(f"{trocadas} cena(s) para trocar: rode run.py --projeto {projeto.name} --so midia")


if __name__ == "__main__":
    acao, nome = sys.argv[1], sys.argv[2]
    if acao == "servir":
        servir(PROJETOS / nome, int(sys.argv[3]) if len(sys.argv) > 3 else 8765)
    else:
        aplicar(PROJETOS / nome)
