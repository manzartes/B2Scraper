import streamlit as st
import requests
import json
import google.generativeai as genai
import time
import re
import pandas as pd
import streamlit.components.v1 as components
from io import BytesIO

st.set_page_config(page_title="B2Scraper LinkedIn PRO", page_icon="🚀", layout="wide")

# ==========================================
# 🔑 CONFIGURAÇÕES E SECRETS
# ==========================================
try:
    CHAVE_SERPER_PADRAO = st.secrets.get("CHAVE_SERPER", "902a25118f1f65d63bef8f294d747d3624642da1")
    CHAVE_GEMINI_PADRAO = st.secrets.get("CHAVE_GEMINI", "")
    URL_WEBHOOK_PLANILHA = st.secrets.get("WEBHOOK_PLANILHA", "")
except Exception:
    CHAVE_SERPER_PADRAO = "902a25118f1f65d63bef8f294d747d3624642da1"
    CHAVE_GEMINI_PADRAO = ""
    URL_WEBHOOK_PLANILHA = ""

# --- INICIALIZAÇÃO DE ESTADOS ---
for chave in ["historico_leads", "leads_aprovados_tela", "leads_reprovados_tela", "bons_exemplos", "maus_exemplos", "feedbacks_dados"]:
    if chave not in st.session_state:
        st.session_state[chave] = []

if "blacklist_arrobas" not in st.session_state:
    st.session_state["blacklist_arrobas"] = set()
if "proxima_pagina" not in st.session_state:
    st.session_state["proxima_pagina"] = 1

# ==========================================
# ⚙️ SIDEBAR (PAINEL DE CONTROLE)
# ==========================================
with st.sidebar:
    st.header("⚙️ Configurações LinkedIn")
    
    with st.expander("🎯 Destino CRM", expanded=True):
        url_webhook = st.text_input("Webhook URL:", type="password", value=st.session_state.get("url_webhook", URL_WEBHOOK_PLANILHA))
        nome_aba = st.text_input("Aba CRM:", value=st.session_state.get("nome_aba", "LEADS_LINKEDIN"))
        st.session_state["url_webhook"] = url_webhook
        st.session_state["nome_aba"] = nome_aba

    with st.expander("🚫 Blacklist", expanded=False):
        aba_blacklist = st.text_input("Aba Blacklist:", value=st.session_state.get("aba_blacklist", "BLACKLIST"))
        st.session_state["aba_blacklist"] = aba_blacklist

    with st.expander("🔑 API Keys", expanded=False):
        api_key_serper = st.text_input("Serper Key:", type="password", value=st.session_state.get("api_key_serper", CHAVE_SERPER_PADRAO))
        api_key_gemini = st.text_input("Gemini Key:", type="password", value=st.session_state.get("api_key_gemini", CHAVE_GEMINI_PADRAO))
        st.session_state["api_key_serper"] = api_key_serper
        st.session_state["api_key_gemini"] = api_key_gemini

    with st.expander("👤 Perfil de Abordagem", expanded=False):
        seu_nome = st.text_input("Seu Nome:", value="Henrique Durant")
        anos_exp = st.text_input("Anos Exp:", value="5")
    
    st.divider()
    st.caption(f"🧠 Memória IA: {len(st.session_state['bons_exemplos'])} L / {len(st.session_state['maus_exemplos'])} D")

# ==========================================
# 🧠 CÉREBRO DA IA E BUSCA
# ==========================================

def analisar_lead_linkedin(nome_bruto, snippet, api_gemini, nome_bdr, exp_bdr):
    try:
        genai.configure(api_key=api_gemini)
        modelo = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Você é {nome_bdr}, BDR High-Ticket. O lead foi encontrado no LinkedIn.
        Lead: {nome_bruto}
        Bio/Snippet: {snippet}

        REGRAS:
        1. Identifique o Nome Próprio e o Cargo.
        2. Avalie se é um tomador de decisão (Sócio, Diretor, Gerente, Profissional Liberal).
        3. Se for estagiário ou cargo muito operacional, REPROVE.
        
        SCRIPT (Se aprovado):
        Use um tom profissional de LinkedIn. 
        "Olá, [NOME]. Notei sua atuação como [CARGO] e decidi entrar em contato..."
        Mantenha as quebras de linha com \\n\\n.

        Retorne APENAS JSON:
        {{
            "status": "APROVADO" ou "REPROVADO",
            "motivo": "...",
            "nome_limpo": "Primeiro Nome",
            "cargo": "Cargo Identificado",
            "script": "Texto do script"
        }}
        """
        res = modelo.generate_content(prompt)
        return json.loads(res.text.replace("```json", "").replace("```", "").strip())
    except:
        return {"status": "ERRO", "motivo": "Falha na IA"}

def buscar_linkedin(empresa, localidade, api_key, pagina=1):
    url = "https://google.serper.dev/search"
    query = f'site:linkedin.com/in "{empresa}"'
    if localidade: query += f' "{localidade}"'
    
    payload = json.dumps({"q": query, "page": pagina, "num": 10})
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}
    
    try:
        res = requests.post(url, headers=headers, data=payload)
        return res.json().get("organic", [])
    except:
        return []

# ==========================================
# 🛠️ COMPONENTES DE INTERFACE
# ==========================================

def enviar_para_planilha(dados):
    webhook = st.session_state.get("url_webhook")
    if not webhook: return False
    try:
        res = requests.post(webhook, json=dados)
        return res.ok
    except: return False

def botao_magico_linkedin(perfil_url, script, nome_id):
    uid = re.sub(r'[^a-zA-Z0-9]', '', nome_id)
    script_safe = json.dumps(script)
    
    html = f"""
    <div style="width:100%;">
        <button id="btn_{uid}" onclick="executar_{uid}()" style="width:100%; background:#0077b5; color:white; border:none; border-radius:5px; padding:10px; cursor:pointer; font-weight:bold;">
            🔵 Copiar + Abrir LinkedIn
        </button>
    </div>
    <script>
    function executar_{uid}() {{
        const el = document.createElement('textarea');
        el.value = {script_safe};
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        
        window.open('{perfil_url}', '_blank');
        
        const btn = document.getElementById('btn_{uid}');
        btn.innerHTML = '✅ Copiado!';
        btn.style.background = '#28a745';
    }}
    </script>
    """
    components.html(html, height=50)

def desenhar_card_linkedin(lead, contexto="geral"):
    with st.expander(f"👤 {lead['nome_bruto']}", expanded=True):
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.markdown(f"**Cargo:** {lead.get('cargo', 'N/A')}")
            st.caption(f"**Motivo IA:** {lead.get('motivo', '')}")
            st.code(lead.get('script', ''), language="markdown")
            
        with col2:
            botao_magico_linkedin(lead['perfil'], lead.get('script', ''), lead['nome_bruto'])
            
        with col3:
            if st.button("✅ CRM", key=f"crm_{lead['perfil']}_{contexto}"):
                dados = {**lead, "sheet_name": st.session_state["nome_aba"], "status": "Abordado"}
                if enviar_para_planilha(dados):
                    st.toast("Enviado ao CRM!")
                    
            if st.button("🚫 Blacklist", key=f"bl_{lead['perfil']}_{contexto}"):
                dados = {**lead, "sheet_name": st.session_state["aba_blacklist"], "status": "Blacklist"}
                enviar_para_planilha(dados)
                st.toast("Na Blacklist!")

# ==========================================
# 🚀 FLUXO PRINCIPAL
# ==========================================

st.title("🚀 B2Scraper LinkedIn PRO")

aba_busca, aba_historico, aba_crm = st.tabs(["🔍 Garimpo de Funcionários", "📚 Histórico", "📊 Planilha"])

with aba_busca:
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1: empresa = st.text_input("Nome da Empresa:", placeholder="Ex: Nubank")
    with col2: local = st.text_input("Localidade:", placeholder="Ex: São Paulo")
    with col3: qtd = st.number_input("Páginas:", 1, 10, 1)

    if st.button("Iniciar Varredura IA", type="primary", use_container_width=True):
        if not empresa: st.error("Digite uma empresa!")
        else:
            st.session_state["leads_aprovados_tela"] = []
            st.session_state["leads_reprovados_tela"] = []
            
            resultados = buscar_linkedin(empresa, local, st.session_state["api_key_serper"])
            
            prog = st.progress(0)
            for i, res in enumerate(resultados):
                prog.progress((i+1)/len(resultados), text=f"Analisando {res['title']}...")
                
                analise = analisar_lead_linkedin(
                    res['title'], res['snippet'], 
                    st.session_state["api_key_gemini"], 
                    seu_nome, anos_exp
                )
                
                lead_completo = {
                    "nome_bruto": res['title'],
                    "perfil": res['link'],
                    "snippet": res['snippet'],
                    **analise
                }
                
                if analise.get("status") == "APROVADO":
                    st.session_state["leads_aprovados_tela"].append(lead_completo)
                    st.session_state["historico_leads"].insert(0, lead_completo)
                else:
                    st.session_state["leads_reprovados_tela"].append(lead_completo)
            prog.empty()

    # Renderizar Resultados
    if st.session_state["leads_aprovados_tela"]:
        st.subheader("✅ Leads Qualificados")
        for lead in st.session_state["leads_aprovados_tela"]:
            desenhar_card_linkedin(lead, "busca")
            
    if st.session_state["leads_reprovados_tela"]:
        with st.expander("❌ Leads Descartados"):
            for l in st.session_state["leads_reprovados_tela"]:
                st.write(f"- {l['nome_bruto']}: {l['motivo']}")

with aba_historico:
    for lead in st.session_state["historico_leads"]:
        desenhar_card_linkedin(lead, "hist")

with aba_crm:
    st.info("Visualização da Planilha de Controle")
    components.iframe("https://docs.google.com/spreadsheets/d/1Ru4E7ArF3UKiPhkqjy0OkrCkdSKzcjHHchQm5v-836g/edit?rm=minimal", height=800)
