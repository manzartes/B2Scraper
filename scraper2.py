import streamlit as st
import requests
import json
import pandas as pd
from io import BytesIO
import time
import unicodedata
import re

# Configuração da página
st.set_page_config(page_title="Buscador de Funcionários", page_icon="🔍", layout="wide")

# --- GERENCIADOR DE MEMÓRIA (SESSION STATE) ---
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
    
    barra_progresso = st.progress(0, text="Iniciando extração...")
    
    try:
        for i, pagina in enumerate(range(pagina_inicial, pagina_inicial + qtd_paginas)):
            progresso = (i + 1) / qtd_paginas
            barra_progresso.progress(progresso, text=f"Lendo página {pagina} do Google (buscando {empresa_limpa})...")
            
            payload = json.dumps({
                "q": query, "page": pagina, "gl": "br", "hl": "pt-br"    
            })
            
            resposta = requests.post(url, headers=headers, data=payload)
            
            if not resposta.ok:
                st.error(f"Erro na API na página {pagina}: {resposta.text}")
                break
                
            dados = resposta.json()
            resultados_organicos = dados.get("organic", [])
            
            if not resultados_organicos:
                break 
                
            for resultado in resultados_organicos:
                titulo = resultado.get("title", "")
                link = resultado.get("link", "")
                snippet = resultado.get("snippet", "Sem descrição") 
                
                titulo_limpo = titulo.replace(" | LinkedIn", "").replace(" - LinkedIn", "")
                
                if "linkedin.com/in/" in link:
                    novos_funcionarios.append({
                        "Nome Bruto": titulo_limpo,
                        "Trecho Encontrado": snippet,
                        "Perfil": link
                    })
            
            time.sleep(0.5) 
        
        barra_progresso.empty()
        return novos_funcionarios
        
    except Exception as e:
        st.error(f"Erro inesperado no código: {e}")
        barra_progresso.empty()
        return []

# --- FUNÇÕES DE PROCESSAMENTO "ENTERPRISE" ---

def extrair_nome_cargo(texto):
    """Tenta separar o nome do cargo usando os hífens que o Google traz."""
    partes = texto.replace(" | ", " - ").split(" - ")
    nome = partes[0].strip()
    cargo = partes[1].strip() if len(partes) > 1 else "Não identificado"
    return pd.Series([nome, cargo])

def remover_acentos(texto):
    texto_normalizado = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    return re.sub(r'[^a-zA-Z\s]', '', texto_normalizado).lower()

def gerar_emails(nome, dominio):
    """Gera combinações lógicas de e-mail corporativo."""
    if not dominio:
        return ""
    nome_limpo = remover_acentos(nome)
    partes = nome_limpo.split()
    
    if len(partes) >= 2:
        primeiro = partes[0]
        ultimo = partes[-1]
        dominio_limpo = dominio.replace("@", "").strip()
        return f"{primeiro}.{ultimo}@{dominio_limpo}, {primeiro[0]}{ultimo}@{dominio_limpo}, {primeiro}@{dominio_limpo}"
    elif len(partes) == 1:
        dominio_limpo = dominio.replace("@", "").strip()
        return f"{partes[0]}@{dominio_limpo}"
    return ""

# --- Funcionalidades de Exportação ---
def converter_para_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def converter_para_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Leads')
    return output.getvalue()

# --- Interface Visual ---

st.title("🚀 Máquina de Leads Pro")
st.markdown("Busca avançada, extração de cargos, gerador de e-mails e dashboard analítico.")

with st.expander("⚙️ Configurações de API", expanded=not bool(st.session_state["api_key"])):
    nova_api_key = st.text_input("Sua API Key do Serper:", type="password", value=st.session_state["api_key"])
    if nova_api_key:
        st.session_state["api_key"] = nova_api_key

with st.form("busca_nova"):
    st.subheader("Nova Busca")
    col1, col2 = st.columns(2)
    with col1:
        empresa_alvo = st.text_input("🏢 Empresa:", placeholder='Ex: Nubank, PCH Americana...')
    with col2:
        localidade_alvo = st.text_input("📍 Localidade (Opcional):", placeholder='Ex: Brasil, São Paulo...')
    
    btn_nova_busca = st.form_submit_button("Iniciar Nova Busca", type="primary")

if btn_nova_busca:
    if not st.session_state["api_key"]:
        st.error("Insira sua API Key do Serper acima.")
    elif not empresa_alvo:
        st.warning("Digite o nome de uma empresa.")
    else:
        st.session_state["leads_salvos"] = []
        st.session_state["proxima_pagina"] = 1
        st.session_state["ultima_empresa"] = empresa_alvo
        st.session_state["ultima_localidade"] = localidade_alvo
        
        with st.spinner("Realizando varredura inicial..."):
            novos = buscar_funcionarios_serper(empresa_alvo, st.session_state["api_key"], localidade_alvo, 1)
            if novos:
                st.session_state["leads_salvos"].extend(novos)
                st.session_state["proxima_pagina"] = 6

# --- ÁREA DE RESULTADOS, FILTROS E DASHBOARD ---

if len(st.session_state["leads_salvos"]) > 0:
    st.divider()
    
    # Removemos duplicatas da memória bruta
    leads_unicos = [dict(t) for t in {tuple(d.items()) for d in st.session_state["leads_salvos"]}]
    df_base = pd.DataFrame(leads_unicos)
    
    # Processamento Automático (Separar Nome e Cargo)
    df_base[['Nome', 'Cargo']] = df_base['Nome Bruto'].apply(extrair_nome_cargo)
    
    st.subheader("🎛️ Refinar e Enriquecer Dados")
    col_filtro, col_dominio = st.columns(2)
    with col_filtro:
        filtro_cargo = st.text_input("🔎 Filtrar por Cargo:", placeholder="Ex: Diretor, Engenheiro, Marketing...")
    with col_dominio:
        dominio_email = st.text_input("📧 Gerar E-mails (Digite o domínio):", placeholder="Ex: nubank.com.br")

    # Aplicando o Filtro Dinâmico
    df_filtrado = df_base.copy()
    if filtro_cargo:
        # Filtra ignorando letras maiúsculas/minúsculas
        df_filtrado = df_filtrado[df_filtrado['Cargo'].str.contains(filtro_cargo, case=False, na=False) | 
                                  df_filtrado['Nome Bruto'].str.contains(filtro_cargo, case=False, na=False)]
    
    # Gerador de Emails
    if dominio_email:
        df_filtrado['E-mails Sugeridos'] = df_filtrado['Nome'].apply(lambda x: gerar_emails(x, dominio_email))
    
    # Reorganizando as colunas para ficar bonito
    colunas_finais = ['Nome', 'Cargo']
    if dominio_email:
        colunas_finais.append('E-mails Sugeridos')
    colunas_finais.extend(['Perfil', 'Trecho Encontrado'])
    df_final = df_filtrado[colunas_finais]

    # --- DASHBOARD E MÉTRICAS ---
    st.divider()
    col_metricas, col_grafico = st.columns([1, 2])
    
    with col_metricas:
        st.metric(label="Total de Leads Encontrados", value=len(df_base))
        st.metric(label="Leads Após Filtro", value=len(df_final))
        
        if st.button("➕ Pesquisar Mais 50 Leads no Google", type="secondary", use_container_width=True):
            with st.spinner("Minerando mais fundo..."):
                mais_leads = buscar_funcionarios_serper(
                    st.session_state["ultima_empresa"], 
                    st.session_state["api_key"], 
                    st.session_state["ultima_localidade"], 
                    pagina_inicial=st.session_state["proxima_pagina"]
                )
                if mais_leads:
                    st.session_state["leads_salvos"].extend(mais_leads)
                    st.session_state["proxima_pagina"] += 5
                    st.rerun()

    with col_grafico:
        st.caption("Top 10 Cargos Encontrados")
        # Conta os cargos (ignorando os "Não identificados") para fazer o gráfico
        cargos_validos = df_base[df_base['Cargo'] != "Não identificado"]
        top_cargos = cargos_validos['Cargo'].value_counts().head(10)
        st.bar_chart(top_cargos)

    # --- TABELA E DOWNLOADS ---
    col_csv, col_xlsx, _ = st.columns([1, 1, 4])
    with col_csv:
        st.download_button("📥 Baixar Planilha CSV", converter_para_csv(df_final), f"leads_{st.session_state['ultima_empresa']}.csv", "text/csv")
    with col_xlsx:
        st.download_button("📊 Baixar Planilha Excel", converter_para_excel(df_final), f"leads_{st.session_state['ultima_empresa']}.xlsx")
    
    st.dataframe(
        df_final, 
        column_config={
            "Perfil": st.column_config.LinkColumn("Link do LinkedIn"),
            "Trecho Encontrado": st.column_config.TextColumn(width="medium")
        },
        hide_index=True,
        use_container_width=True
    )
