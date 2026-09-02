from datetime import datetime, timezone
import os
from io import BytesIO
import json
import random
import re
import secrets
from flask import Flask, jsonify, render_template_string, request, send_file

app = Flask(__name__)

# Deliberately in-memory: this prototype keeps one journey per browser session.
sessions = {}

COMMERCIAL_WORDS = {
    "valor", "benefício", "beneficio", "resultado", "investimento", "economia",
    "necessidade", "ganha-ganha", "roi", "meta", "crescimento", "solução",
    "solucao", "problema", "cliente", "venda", "vender", "agendamento", "tempo",
    "custo", "processo", "objetivo", "dor", "conversão", "conversao"
}
RESILIENCE_WORDS = {
    "entendo", "mas", "por outro lado", "imagine", "que tal", "e se", "vamos pensar",
    "posso", "como", "alternativa", "opção", "opcao", "teste", "experimentar", "pergunta"
}

ACKS = {
    "strong": [
        "Boa! Mandou bem — você pensou no lado do cliente e no próximo passo.",
        "Massa! Você conectou a conversa com valor, não só com produto.",
        "Aí sim! Deu pra ver uma linha de raciocínio comercial bem clara.",
        "Boa demais. Você trouxe contexto e deixou a conversa bem objetiva.",
        "Show! Gostei de como você tentou entender a situação antes de avançar.",
    ],
    "medium": [
        "Entendi seu ponto. Valeu por responder de verdade, muita gente trava aqui.",
        "Boa, faz sentido. Você já trouxe uma ideia legal pra conversa.",
        "Valeu! Curti o caminho que você escolheu pra responder.",
        "Entendi. Tem um bom ponto de partida aí — bora seguir.",
        "Boa tentativa! Você entrou no clima e isso já ajuda bastante.",
    ],
    "weak": [
        "Curioso! Pode não ter sido o que eu esperava, mas valeu pela sinceridade.",
        "Tranquilo, valeu por responder. O importante é se jogar no treino.",
        "Entendi! Mesmo curtinha, sua resposta conta. Bora pra próxima.",
        "Valeu pela resposta. Sem pressão — a ideia aqui é praticar mesmo.",
        "De boa! Você participou, e é isso que importa nesse exercício.",
    ],
}

# Each new session samples one variation per stage so candidates going
# through the exercise around the same time don't see identical prompts.
STAGE1_QUESTIONS = [
    "Imagina que você liga pra um cliente e ele diz: ‘tô sem tempo agora, manda e-mail’. O que você faz?",
    "Você liga e a pessoa atende meio seca, dizendo: ‘já tenho um fornecedor, não preciso’. O que você faz?",
    "Você manda uma mensagem e a pessoa não responde há 3 dias. Qual sua próxima ação?",
    "No meio da ligação, o cliente pergunta ‘quanto custa?’ antes mesmo de você explicar o produto. Como você reage?",
]

STAGE2_QUIZ_QUESTIONS = [
    "Pergunta rápida: qual é a primeira coisa que você deve fazer ao abrir uma cold call?\nA) Falar do produto\nB) Confirmar se é bom momento\nC) Pedir orçamento\nD) Sair correndo",
    "Pergunta rápida: qual é o principal objetivo de uma cold call de qualificação (não de venda direta)?\nA) Fechar a venda\nB) Marcar uma próxima conversa\nC) Explicar todos os recursos do produto\nD) Pedir indicação",
    "Pergunta rápida: se o cliente começa a falar bastante sobre o problema dele, o que você deve fazer?\nA) Interromper e já oferecer a solução\nB) Deixar falar e fazer perguntas pra entender melhor\nC) Mudar de assunto\nD) Marcar outra ligação",
    "Pergunta rápida: qual é um sinal de que você deve encerrar a ligação educadamente?\nA) O cliente faz uma pergunta\nB) O cliente pede pra ligar em outro momento, repetidas vezes\nC) O cliente pede mais detalhes\nD) O cliente pergunta o preço",
]

STAGE3_PRODUCTS = [
    {"name": "AgendaFácil", "description": "sistema de agendamento online pra salões e clínicas.\nTem agendamento, lembretes por WhatsApp e controle de clientes.", "price": 49},
    {"name": "FinanceFácil", "description": "app de controle financeiro pra pequenos negócios.\nOrganiza entradas, saídas e gera relatórios simples.", "price": 39},
    {"name": "RecrutaZap", "description": "ferramenta de triagem de currículos via WhatsApp.\nJá filtra e ranqueia os melhores candidatos automaticamente.", "price": 79},
    {"name": "EstoqueSimples", "description": "sistema de controle de estoque pra lojas físicas.\nAvisa quando um produto tá acabando.", "price": 59},
]

STAGE4_FOLLOWUP_POOL = [
    "Entendi, mas eu não tenho tempo pra aprender sistema novo agora.\nQuem sabe ano que vem?",
    "Última dúvida: e se eu testar e não conseguir os resultados que eu quero?\nO que você me diria?",
    "Minha equipe já tá acostumada com o que a gente usa hoje, trocar dá trabalho.",
    "Isso parece bom, mas eu preciso conversar com meu sócio antes de decidir.",
    "Já tentei uma ferramenta parecida antes e não deu muito certo.",
]

CHAT_TEMPLATE = r'''
<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Treino SDR</title>
<style>
:root{--green:#128c7e;--bright:#25d366;--bg:#efeae2;--ink:#19312d}*{box-sizing:border-box}body{margin:0;background:#d9dbd5;font-family:Arial,Helvetica,sans-serif;color:var(--ink);min-height:100vh;display:flex;justify-content:center}.phone{width:min(100%,540px);height:100vh;background:var(--bg);display:flex;flex-direction:column;box-shadow:0 0 28px #0002;overflow:hidden}.top{height:66px;background:var(--green);color:white;display:flex;align-items:center;padding:10px 16px;gap:12px;flex:none}.avatar{width:43px;height:43px;border-radius:50%;background:#d9fdd3;color:#087568;display:grid;place-items:center;font-size:22px}.top h1{font-size:16px;margin:0 0 4px}.status{font-size:12px;opacity:.85}.restart{margin-left:auto;border:0;background:transparent;color:#d9fdd3;font-size:11px;text-decoration:underline;cursor:pointer;padding:6px}.progress{height:4px;background:#0a7065;flex:none}.progress i{display:block;height:100%;background:var(--bright);width:0;transition:width .3s}.messages{padding:15px 12px 18px;overflow:auto;flex:1;background-color:#efeae2;background-image:radial-gradient(#d8d0c5 1px,transparent 1px);background-size:18px 18px}.row{display:flex;margin:5px 0}.row.me{justify-content:flex-end}.bubble{max-width:84%;padding:9px 11px 7px;border-radius:8px;background:#fff;box-shadow:0 1px 1px #0001;font-size:14px;line-height:1.42;white-space:pre-wrap;word-break:break-word}.me .bubble{background:#d9fdd3;border-top-right-radius:2px}.mentor .bubble{border-top-left-radius:2px}.time{display:block;text-align:right;color:#81908b;font-size:10px;margin-top:4px}.composer{background:#f0f2f5;padding:9px 10px calc(9px + env(safe-area-inset-bottom));display:flex;gap:8px;align-items:flex-end}.composer textarea{border:0;resize:none;border-radius:22px;padding:12px 15px;font:14px Arial;line-height:1.25;min-height:44px;max-height:100px;flex:1;outline:none}.send{border:0;width:44px;height:44px;border-radius:50%;background:var(--bright);color:white;font-size:20px;cursor:pointer}.send:disabled{background:#9acbb1;cursor:default}.typing{display:none;padding:8px 14px}.typing.show{display:flex;gap:4px}.typing b{width:6px;height:6px;border-radius:50%;background:#87928d;animation:blink 1s infinite}.typing b:nth-child(2){animation-delay:.15s}.typing b:nth-child(3){animation-delay:.3s}@keyframes blink{0%,60%,100%{opacity:.25}30%{opacity:1}}.notice{font-size:12px;text-align:center;color:#6b7770;padding:7px}.done{padding:14px;text-align:center;background:#f0f2f5;font-size:13px;color:#53635d}.done strong{display:block;color:var(--green);margin-bottom:4px}@media(min-width:600px){.phone{height:calc(100vh - 24px);margin:12px 0;border-radius:12px}.top{border-radius:12px 12px 0 0}}
</style></head><body><main class="phone"><header class="top"><div class="avatar">👊</div><div><h1>Treino SDR</h1><div class="status" id="status">mentor de prospecção</div></div><button class="restart" id="restart" type="button">Recomeçar</button></header><div class="progress"><i id="progress"></i></div><section class="messages" id="messages"></section><div class="typing" id="typing"><b></b><b></b><b></b></div><div id="done"></div><form class="composer" id="composer"><textarea id="input" rows="1" placeholder="Digite uma mensagem..." autocomplete="off"></textarea><button class="send" aria-label="Enviar">➤</button></form></main>
<script>
const messagesEl=document.getElementById('messages'), input=document.getElementById('input'), form=document.getElementById('composer'), typing=document.getElementById('typing'), doneEl=document.getElementById('done'), progress=document.getElementById('progress'), statusEl=document.getElementById('status'), restartEl=document.getElementById('restart');
let busy=false, rendered=0, sid=localStorage.getItem('treino_sdr_sid')||'';
function bubble(text, mine, time){const row=document.createElement('div');row.className='row '+(mine?'me':'mentor');const b=document.createElement('div');b.className='bubble';b.textContent=text;const t=document.createElement('span');t.className='time';t.textContent=time||'agora';b.appendChild(t);row.appendChild(b);messagesEl.appendChild(row);messagesEl.scrollTop=messagesEl.scrollHeight;}
function showTyping(on){typing.classList.toggle('show',on);messagesEl.scrollTop=messagesEl.scrollHeight;}
function wait(ms){return new Promise(r=>setTimeout(r,ms));}
function sessionHeaders(json=false){const headers=json?{'Content-Type':'application/json'}:{};if(sid)headers['X-Session-Id']=sid;return headers;}
function rememberSession(d){if(d.session_id){sid=d.session_id;localStorage.setItem('treino_sdr_sid',sid);}}
async function renderNew(items){for(const m of items){if(m.sender==='mentor'){showTyping(true);await wait(800+Math.floor(Math.random()*701));showTyping(false)}bubble(m.text,m.sender==='candidate',m.time);rendered++;}}
async function load(){const r=await fetch('/api/state',{headers:sessionHeaders()});const d=await r.json();rememberSession(d);messagesEl.innerHTML='';rendered=0;await renderNew(d.messages);update(d)}
function update(d){progress.style.width=(Math.min(d.stage_number,4)/4*100)+'%';statusEl.textContent=d.complete?'treino concluído':('etapa '+d.stage_number+' de 4');if(d.complete){doneEl.innerHTML='<div class="done"><strong>Treino concluído ✅</strong>Valeu por participar!<br>A equipe de recrutamento vai analisar seu resultado.</div>';input.disabled=true;form.querySelector('button').disabled=true;input.placeholder='Treino encerrado';}}
restartEl.addEventListener('click',()=>{localStorage.removeItem('treino_sdr_sid');window.location.reload();});
form.addEventListener('submit',async e=>{e.preventDefault();if(busy||!input.value.trim())return;const text=input.value.trim();input.value='';input.style.height='auto';busy=true;form.querySelector('button').disabled=true;try{const r=await fetch('/api/message',{method:'POST',headers:sessionHeaders(true),body:JSON.stringify({text})});const d=await r.json();rememberSession(d);if(!r.ok){throw new Error(d.error||'Não foi possível enviar.')}await renderNew(d.new_messages||[]);update(d)}catch(err){bubble('Ops, não consegui enviar agora. Tenta de novo?',false)}finally{busy=false;if(!input.disabled)form.querySelector('button').disabled=false;input.focus();}});input.addEventListener('input',()=>{input.style.height='auto';input.style.height=Math.min(input.scrollHeight,100)+'px'});input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();form.requestSubmit()}});load();
</script></body></html>
'''

ADMIN_TEMPLATE = r'''
<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Treino SDR — Admin</title><style>body{font-family:Arial,sans-serif;margin:0;padding:28px;background:#f5f7f6;color:#21332f}main{max-width:1400px;margin:auto}h1{color:#128c7e;margin:0 0 8px}.sub{color:#60716a;margin:0 0 22px}.cards{display:flex;gap:12px;margin-bottom:20px}.card{background:white;border:1px solid #dce5e0;border-radius:10px;padding:15px 20px;min-width:180px}.num{font-size:27px;font-weight:bold;color:#128c7e;display:block}.label{font-size:12px;color:#677770}a.button{display:inline-block;background:#128c7e;color:#fff;text-decoration:none;border-radius:7px;padding:10px 14px;font-size:13px;margin-bottom:14px} .table-wrap{background:#fff;border:1px solid #dce5e0;border-radius:10px;overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px;min-width:1060px}th,td{text-align:left;padding:11px 12px;border-bottom:1px solid #edf1ef;vertical-align:top}th{background:#eef7f3;color:#42655b;font-size:11px;text-transform:uppercase;letter-spacing:.03em;white-space:nowrap}tr:last-child td{border-bottom:0}.score{font-weight:bold;color:#128c7e}.obs{max-width:280px;white-space:pre-line;line-height:1.35}.pill{padding:4px 7px;border-radius:12px;background:#fff3d6;color:#916b13;font-size:11px;white-space:nowrap}.pill.done{background:#d9f7e5;color:#197247}</style></head><body><main><h1>Treino SDR</h1><p class="sub">Painel de pré-qualificação · dados mantidos em memória nesta execução</p><div class="cards"><div class="card"><span class="num">{{ evaluated }}</span><span class="label">candidatos avaliados</span></div><div class="card"><span class="num">{{ ongoing }}</span><span class="label">em andamento</span></div></div><a class="button" href="/admin/export.json">Exportar JSON</a><div class="table-wrap"><table><thead><tr><th>Nome</th><th>Contato</th><th>Etapa</th><th>Status</th><th>Clareza</th><th>Raciocínio</th><th>Resiliência</th><th>Engajamento</th><th>Geral</th><th>Observações</th><th>Início</th><th>Conclusão</th></tr></thead><tbody>{% for c in candidates %}<tr><td>{{ c.name or '—' }}</td><td>{{ c.contact or '—' }}</td><td>{{ c.stage_label }}</td><td><span class="pill {{ 'done' if c.complete else '' }}">{{ 'Concluído' if c.complete else 'Em andamento' }}</span></td><td class="score">{{ c.scores.clareza }}</td><td class="score">{{ c.scores.raciocinio }}</td><td class="score">{{ c.scores.resiliencia }}</td><td class="score">{{ c.scores.engajamento }}</td><td class="score">{{ c.overall }}</td><td class="obs">{{ c.observations or 'Aguardando mais respostas.' }}</td><td>{{ c.started_at }}</td><td>{{ c.completed_at or '—' }}</td></tr>{% else %}<tr><td colspan="12">Nenhum candidato nesta execução.</td></tr>{% endfor %}</tbody></table></div></main></body></html>
'''


def now():
    return datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")


def new_session():
    sid = secrets.token_urlsafe(18)
    sessions[sid] = {
        "name": "", "contact": "", "stage": "onboarding", "messages": [],
        "score_history": {k: [] for k in ("clareza", "raciocinio", "resiliencia", "engajamento")},
        "scores": {k: 0.0 for k in ("clareza", "raciocinio", "resiliencia", "engajamento")},
        "started_at": now(), "completed_at": None, "complete": False, "observations": "",
        "objection_round": 0,
        "temp_name": "",
        "temp_contact": "",
        "stage1_question": random.choice(STAGE1_QUESTIONS),
        "stage2_quiz": random.choice(STAGE2_QUIZ_QUESTIONS),
        "stage3_product": random.choice(STAGE3_PRODUCTS),
        "objection_followups": random.sample(STAGE4_FOLLOWUP_POOL, 2),
    }
    add_mentor(sessions[sid], "Fala! 👊 Sou seu mentor de prospecção.\nVamos fazer um treino rápido de SDR? Leva uns 15 minutos. Bora?")
    return sid


def get_current():
    """Return the journey identified by the client-supplied session header."""
    sid = request.headers.get("X-Session-Id", "").strip()
    if not sid or sid not in sessions:
        sid = new_session()
    return sid, sessions[sid]


def add_mentor(data, text):
    data["messages"].append({"sender": "mentor", "text": text, "time": datetime.now().strftime("%H:%M")})


def add_candidate(data, text):
    data["messages"].append({"sender": "candidate", "text": text, "time": datetime.now().strftime("%H:%M")})


def contains_yes(text):
    return bool(re.search(r"\b(sim|s|bora|vamos|quero|claro|partiu|topo|pode|ok|okay|beleza|blz|yes)\b", text.lower()))


def contains_no(text):
    return bool(re.search(r"\b(não|nao|n|negativo|depois|agora não|agora nao)\b", text.lower()))


def tier_for(text):
    clean = text.lower()
    words = set(re.findall(r"[\wÀ-ÿ-]+", clean))
    has_commercial = bool(words & COMMERCIAL_WORDS) or any(k in clean for k in ("ganha-ganha", "por outro lado"))
    if len(text) > 100 and has_commercial:
        return "strong"
    if 20 <= len(text) <= 100:
        return "medium"
    return "weak"


def acknowledge(text):
    # Sampling is deterministic within a response while still giving variety across journeys.
    return random.choice(ACKS[tier_for(text)])


def score_response(text, stage):
    value = text.strip()
    n = len(value)
    words = set(re.findall(r"[\wÀ-ÿ-]+", value.lower()))
    commercial_hits = len(words & COMMERCIAL_WORDS)
    resilience_hits = len(words & RESILIENCE_WORDS) + sum(1 for p in RESILIENCE_WORDS if " " in p and p in value.lower())
    clear = 2 if n < 10 else 5 if n < 30 else 8 if n <= 200 else 7 if n <= 500 else 6
    clear += 1 if ("." in value or "," in value) and n >= 20 else 0
    clear += 1 if n >= 30 and len(re.findall(r"\s+", value)) >= 5 else 0
    reasoning = min(10, 2 + commercial_hits * 1.2)
    if any(k in value.lower() for k in ("porque", "para que", "assim", "então", "entao")):
        reasoning += 1
    if commercial_hits >= 2 and any(k in value.lower() for k in ("cliente", "problema", "necessidade", "benefício", "beneficio")):
        reasoning += 1
    reasoning = min(10, reasoning)
    resilience = min(10, 3 + resilience_hits * 1.4)
    if stage == "stage4":
        resilience = min(10, resilience + 1.5)
    elif n >= 30:
        resilience = min(10, resilience + 0.5)
    engagement = 2 if n < 10 else 5 if n < 30 else 7 if n <= 200 else 8
    if "?" in value:
        engagement += 1
    if "!" in value or any(k in value.lower() for k in ("gosto", "quero", "massa", "vamos", "posso")):
        engagement += 1
    return {"clareza": round(min(10, clear), 1), "raciocinio": round(reasoning, 1), "resiliencia": round(min(10, resilience), 1), "engajamento": round(min(10, engagement), 1)}


def record_scores(data, text, stage):
    current = score_response(text, stage)
    for criterion, value in current.items():
        data["score_history"][criterion].append(value)
        data["scores"][criterion] = round(sum(data["score_history"][criterion]) / len(data["score_history"][criterion]), 1)


def overall(data):
    s = data["scores"]
    return round(s["clareza"] * .25 + s["raciocinio"] * .25 + s["resiliencia"] * .30 + s["engajamento"] * .20, 1)


def observations(data):
    s = data["scores"]
    lines = []
    if s["resiliencia"] >= 7:
        lines.append("Resiliente, não desiste facilmente diante de objeções.")
    elif s["resiliencia"] < 5:
        lines.append("Precisa desenvolver resiliência a objeções.")
    else:
        lines.append("Mostrou abertura para praticar respostas a objeções.")
    if s["clareza"] >= 7 and s["raciocinio"] >= 7:
        lines.append("Perfil comunicativo, com boa argumentação comercial.")
    elif s["clareza"] < 5:
        lines.append("Comunicação pode ser mais estruturada e direta.")
    else:
        lines.append("Raciocínio comercial em desenvolvimento, com espaço para ganhar estrutura.")
    if s["engajamento"] >= 7:
        lines.append("Engajamento alto e boa disposição para o treino.")
    return "\n".join(lines[:3])


def start_stage1(data):
    data["stage"] = "stage1"
    add_mentor(data, "Fechou! Pra aquecer:\n" + data["stage1_question"])


def handle_message(data, text):
    stage = data["stage"]
    # Keep operational questions out of the exercise without advancing its state.
    lower = text.lower()
    if any(term in lower for term in ("salário", "salario", "empresa", "processo seletivo", "vaga", "benefícios", "beneficios")):
        add_mentor(data, "Boa pergunta! A equipe de recrutamento entra em contato com esses detalhes.\nBora continuar o treino?")
        return
    if data["complete"]:
        return
    if stage == "onboarding":
        if contains_no(text) and not contains_yes(text):
            add_mentor(data, "Tranquilo! Se mudar de ideia, é só chamar. 👋")
            data["stage"] = "declined"
        elif contains_yes(text):
            add_mentor(data, "Boa! Primeiro: como você se chama e qual seu WhatsApp?")
            data["stage"] = "identity"
        else:
            add_mentor(data, "Me diz se bora ou não, sem pressão 😄")
        return
    if stage == "declined":
        if contains_yes(text):
            add_mentor(data, "Aí sim! Como você se chama e qual seu WhatsApp?")
            data["stage"] = "identity"
        else:
            add_mentor(data, "Tranquilo! Se mudar de ideia, é só chamar. 👋")
        return
    if stage == "identity":
        # Keep partial identity data so a name and WhatsApp can arrive in
        # separate messages (common when the candidate is on mobile).
        contact_match = re.search(
            r"(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4,5}[-\s]?\d{4}",
            text,
        )
        contact = contact_match.group(0).strip() if contact_match else ""
        name_part = text
        if contact:
            name_part = name_part.replace(contact, "")
        # Remove labels and common self-introductions without treating them
        # as part of the candidate's name.
        name_part = re.sub(
            r"\b(?:meu\s+nome\s+é|meu\s+nome|me\s+chamo|sou\s+(?:o|a)|sou)\b\s*",
            "",
            name_part,
            flags=re.I,
        )
        name_part = re.sub(
            r"\b(?:meu\s+)?(?:whatsapp|whats?app|zap|telefone|contato)\b\s*(?:é|:)?\s*",
            "",
            name_part,
            flags=re.I,
        )
        name_part = re.sub(r"^[\s,;:/-]+|[\s,;:/-]+$", "", name_part).strip()
        name_part = name_part.split("\n")[0].strip()
        if len(name_part) < 2 or len(name_part) > 80:
            name_part = ""

        if name_part:
            data["temp_name"] = name_part
        if contact:
            data["temp_contact"] = contact

        name = data.get("temp_name", "")
        saved_contact = data.get("temp_contact", "")
        if name and saved_contact:
            data["name"] = name
            data["contact"] = saved_contact
            data["temp_name"] = ""
            data["temp_contact"] = ""
            add_mentor(data, f"Prazer, {data['name']}! Valeu por chegar junto 👊")
            start_stage1(data)
        elif name:
            add_mentor(data, "E qual seu WhatsApp? Pode mandar só o número, tipo: (11) 99999-9999")
        elif saved_contact:
            add_mentor(data, "E como você se chama?")
        else:
            add_mentor(data, "Manda seu nome e WhatsApp, tipo: Ana, (11) 99999-9999")
        return
    if stage == "stage1":
        record_scores(data, text, stage)
        add_mentor(data, acknowledge(text))
        add_mentor(data, "Dica rápida: numa cold call, você tem poucos segundos pra prender atenção.\nComece pelo nome, confirme se é um bom momento e diga em uma frase o valor que você traz.")
        add_mentor(data, "Exemplo: ‘João, tranquilo? Sou da X. Posso tomar 30 segundos? É sobre reduzir seu tempo de agendamento.’")
        add_mentor(data, data["stage2_quiz"])
        data["stage"] = "stage2"
        return
    if stage == "stage2":
        record_scores(data, text, stage)
        add_mentor(data, acknowledge(text))
        product = data["stage3_product"]
        add_mentor(data, f"Agora a parte boa 😄\nProduto fictício: {product['name']}, {product['description']}")
        add_mentor(data, f"Custa R${product['price']}/mês. Me vende isso como se fosse uma cold call!")
        data["stage"] = "stage3"
        return
    if stage == "stage3":
        record_scores(data, text, stage)
        add_mentor(data, acknowledge(text))
        price = data["stage3_product"]["price"]
        add_mentor(data, f"Fechou, vamos simular de verdade.\nHmm, parece interessante, mas eu resolvo isso de outro jeito hoje. R${price}/mês parece caro pro que é.")
        data["stage"] = "stage4_1"
        data["objection_round"] = 1
        return
    if stage.startswith("stage4"):
        record_scores(data, text, "stage4")
        round_no = data.get("objection_round", 1)
        add_mentor(data, acknowledge(text))
        followups = data["objection_followups"]
        if round_no == 1:
            add_mentor(data, followups[0])
            data["stage"] = "stage4_2"
            data["objection_round"] = 2
        elif round_no == 2:
            add_mentor(data, followups[1])
            data["stage"] = "stage4_3"
            data["objection_round"] = 3
        else:
            add_mentor(data, "Haha, ok, ok… você me deixou curioso. Vou pensar com carinho.")
            add_mentor(data, f"{data['name']}, valeu demais pela disposição!\nVocê topou todos os desafios, isso já diz muito.")
            add_mentor(data, "A equipe de recrutamento vai analisar seu resultado e entra em contato. 🙏")
            data["stage"] = "complete"
            data["complete"] = True
            data["completed_at"] = now()
            data["observations"] = observations(data)


def public_state(data, sid):
    stage_numbers = {"onboarding": 0, "declined": 0, "identity": 0, "stage1": 1, "stage2": 2, "stage3": 3, "stage4_1": 4, "stage4_2": 4, "stage4_3": 4, "complete": 4}
    return {"session_id": sid, "messages": data["messages"], "stage_number": stage_numbers.get(data["stage"], 0), "complete": data["complete"]}


def admin_record(data):
    labels = {"onboarding": "Onboarding", "declined": "Recusou", "identity": "Identidade", "stage1": "1 · Aquecimento", "stage2": "2 · Quiz", "stage3": "3 · Venda", "stage4_1": "4 · Objeção 1", "stage4_2": "4 · Objeção 2", "stage4_3": "4 · Objeção 3", "complete": "Concluído"}
    return {"name": data["name"], "contact": data["contact"], "stage": data["stage"], "stage_label": labels.get(data["stage"], data["stage"]), "complete": data["complete"], "scores": data["scores"], "overall": overall(data), "observations": data["observations"], "started_at": data["started_at"], "completed_at": data["completed_at"]}


@app.get("/")
def index():
    return render_template_string(CHAT_TEMPLATE)


@app.get("/api/state")
def state():
    sid, data = get_current()
    return jsonify(public_state(data, sid))


@app.post("/api/message")
def message():
    sid, data = get_current()
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text", "")).strip()
    if not text:
        return jsonify({"session_id": sid, "error": "Mensagem vazia."}), 400
    if len(text) > 2000:
        return jsonify({"session_id": sid, "error": "Mensagem muito longa."}), 400
    before = len(data["messages"])
    add_candidate(data, text)
    handle_message(data, text)
    return jsonify({**public_state(data, sid), "new_messages": data["messages"][before:]})


@app.get("/admin")
def admin():
    records = [admin_record(d) for d in sessions.values()]
    records.sort(key=lambda item: item["started_at"], reverse=True)
    return render_template_string(ADMIN_TEMPLATE, candidates=records, evaluated=sum(1 for r in records if r["complete"]), ongoing=sum(1 for r in records if not r["complete"]))


@app.get("/admin/export.json")
def export_json():
    records = [admin_record(d) for d in sessions.values()]
    body = json.dumps({"exported_at": now(), "candidates": records}, ensure_ascii=False, indent=2).encode("utf-8")
    return send_file(BytesIO(body), mimetype="application/json", as_attachment=True, download_name="treino-sdr-candidatos.json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=False)
