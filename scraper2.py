import streamlit as st
import requests
import json
import pandas as pd
from io import BytesIO
import time

# Configuração da página
st.set_page_config(page_title="Buscador de Funcionários", page_icon="🔍", layout="wide")

# --- GERENCIADOR DE MEMÓRIA (SESSION STATE) ---
# Aqui ensinamos o aplicativo a não esquecer os dados entre um clique e outro
if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""
if "leads_salvos" not in st.session_state:
    st.session_state["leads_salvos"] = []
if "proxima_pagina" not in st.session_state:
    st.session_state["proxima_pagina"] = 1
if "ultima_empresa" not in st.session_state:
    st.session_state["ultima_empresa"] = ""
if "ultima_localidade" not in st.session_state:
    st.session_state["ultima_localidade"] = ""

def buscar_funcionarios_serper(empresa, api_key, localidade="", pagina_inicial=1, qtd_paginas=5):
    url = "https://google.serper.dev/search"
    empresa_limpa = empresa.replace('"', '').strip()
    query = f'site:linkedin.com/in "{empresa_limpa}"'
    
    if localidade:
        localidade_limpa = localidade.replace('"', '').strip()
        query += f' "{localidade_limpa}"'
    
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    
    novos_funcionarios = []
    pagina_final = pagina_inicial + qtd_paginas - 1
    
    barra_progresso = st.progress(0, text="Iniciando extração...")
    
    try:
        # Loop que começa de onde parou na última vez
        for i, pagina in enumerate(range(pagina_inicial, pagina_inicial + qtd_paginas)):
            progresso = (i + 1) / qtd_paginas
            barra_progresso.progress(progresso, text=f"Lendo página {pagina} do Google (buscando {empresa_limpa})...")
            
            payload = json.dumps({
                "q": query,
                "page": pagina, 
                "gl": "br",      
                "hl": "pt-br"    
            })
            
            resposta = requests.post(url, headers=headers, data=payload)
            
            if not resposta.ok:
                st.error(f"Erro na API na página {pagina}: {resposta.text}")
                break
                
            dados = resposta.json()
            resultados_organicos = dados.get("organic", [])
            
            if not resultados_organicos:
                st.info("O Google avisou que não há mais resultados para esta pesquisa.")
                break 
                
            for resultado in resultados_organicos:
                titulo = resultado.get("title", "")
                link = resultado.get("link", "")
                snippet = resultado.get("snippet", "Sem descrição") 
                
                titulo_limpo = titulo.replace(" | LinkedIn", "").replace(" - LinkedIn", "")
                
                if "linkedin.com/in/" in link:
                    novos_funcionarios.append({
                        "Nome / Cargo": titulo_limpo,
                        "Trecho Encontrado": snippet,
                        "Perfil": link
                    })
            
            time.sleep(0.5) # Pausa dramática para não ser bloqueado
        
        barra_progresso.empty()
        return novos_funcionarios
        
    except Exception as e:
        st.error(f"Erro inesperado no código: {e}")
        barra_progresso.empty()
        return []

# --- Funcionalidades de Exportação ---
def converter_para_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def converter_para_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Leads')
    return output.getvalue()

# --- Interface Visual ---

st.title("🔍 Máquina de Leads do LinkedIn")
st.markdown("Busque, acumule resultados e baixe tudo em uma única planilha. Chave API Serper: 902a25118f1f65d63bef8f294d747d3624642da1")

with st.expander("⚙️ Configurações de API", expanded=not bool(st.session_state["api_key"])):
    nova_api_key = st.text_input("Sua API Key do Serper:", type="password", value=st.session_state["api_key"])
    if nova_api_key:
        st.session_state["api_key"] = nova_api_key

# Formulário de Busca Inicial
with st.form("busca_nova"):
    st.subheader("Nova Busca")
    col1, col2 = st.columns(2)
    with col1:
        empresa_alvo = st.text_input("🏢 Empresa:", placeholder='Ex: Nubank, PCH Americana...')
    with col2:
        localidade_alvo = st.text_input("📍 Localidade (Opcional):", placeholder='Ex: Brasil, São Paulo...')
    
    btn_nova_busca = st.form_submit_button("Iniciar Nova Busca", type="primary")

# Lógica da Nova Busca (Zera a memória e começa de novo)
if btn_nova_busca:
    if not st.session_state["api_key"]:
        st.error("Insira sua API Key do Serper acima.")
    elif not empresa_alvo:
        st.warning("Digite o nome de uma empresa.")
    else:
        # Resetando a memória para a nova busca
        st.session_state["leads_salvos"] = []
        st.session_state["proxima_pagina"] = 1
        st.session_state["ultima_empresa"] = empresa_alvo
        st.session_state["ultima_localidade"] = localidade_alvo
        
        with st.spinner("Realizando varredura inicial..."):
            novos = buscar_funcionarios_serper(
                empresa_alvo, 
                st.session_state["api_key"], 
                localidade_alvo, 
                pagina_inicial=1
            )
            
            if novos:
                st.session_state["leads_salvos"].extend(novos)
                st.session_state["proxima_pagina"] = 6 # Próximo clique começa na pág 6

# --- ÁREA DE RESULTADOS E BOTÃO CARREGAR MAIS ---

# Só mostramos a tabela e o botão extra se houver dados na memória
if len(st.session_state["leads_salvos"]) > 0:
    st.divider()
    
    # Removemos duplicatas da memória caso o Google tenha repetido pessoas
    leads_unicos = [dict(t) for t in {tuple(d.items()) for d in st.session_state["leads_salvos"]}]
    
    col_header, col_btn_mais = st.columns([3, 1])
    with col_header:
        st.success(f"🔥 Temos **{len(leads_unicos)} leads únicos** acumulados para '{st.session_state['ultima_empresa']}'.")
    
    # O Botão Mágico de Carregar Mais
    with col_btn_mais:
        if st.button("➕ Pesquisar Mais 50", use_container_width=True):
            with st.spinner("Minerando mais fundo no Google..."):
                mais_leads = buscar_funcionarios_serper(
                    st.session_state["ultima_empresa"], 
                    st.session_state["api_key"], 
                    st.session_state["ultima_localidade"], 
                    pagina_inicial=st.session_state["proxima_pagina"]
                )
                
                if mais_leads:
                    st.session_state["leads_salvos"].extend(mais_leads)
                    st.session_state["proxima_pagina"] += 5
                    st.rerun() # Atualiza a tela para mostrar os novos números

    # Converte tudo para tabela e prepara os downloads
    df_resultados = pd.DataFrame(leads_unicos)
    
    col_csv, col_xlsx, _ = st.columns([1, 1, 4])
    with col_csv:
        st.download_button("📥 Baixar tudo em CSV", converter_para_csv(df_resultados), f"leads_{st.session_state['ultima_empresa']}.csv", "text/csv")
    with col_xlsx:
        st.download_button("📊 Baixar tudo em Excel", converter_para_excel(df_resultados), f"leads_{st.session_state['ultima_empresa']}.xlsx")
    
    st.dataframe(
        df_resultados, 
        column_config={
            "Perfil": st.column_config.LinkColumn("Link do LinkedIn"),
            "Trecho Encontrado": st.column_config.TextColumn(width="large")
        },
        hide_index=True,
        use_container_width=True
    )
