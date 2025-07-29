import streamlit as st
from PyPDF2 import PdfReader
import docx2txt
from openai import OpenAI
import google.generativeai as genai
from fpdf import FPDF
import sqlite3
from datetime import datetime
import os
import time
from dotenv import load_dotenv

# Configuração inicial
st.set_page_config(page_title="Analisador de Propostas IA", page_icon="📄", layout="wide")
load_dotenv()

# --- Constantes ---
MODEL_DISPLAY_NAMES = {
    "openai-gpt-4": "GPT-4 Turbo (OpenAI)",
    "openai-gpt-3.5": "GPT-3.5 Turbo (OpenAI)",
    "gemini-1.5": "Gemini 1.5 Pro (Google)",
    "llama3-70b": "Llama 3 70B (Ollama)"
}

# --- Inicialização de Serviços ---
def init_services():
    """Inicializa todos os serviços de IA com fallback"""
    services = {}
    
    # OpenAI
    try:
        if os.getenv("OPENAI_API_KEY") or st.secrets.get("openai", {}).get("api_key"):
            services["openai"] = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or st.secrets["openai"]["api_key"])
    except Exception as e:
        st.warning(f"OpenAI não configurada: {str(e)}")

    # Google Gemini
    try:
        if os.getenv("GEMINI_API_KEY") or st.secrets.get("gemini", {}).get("api_key"):
            genai.configure(api_key=os.getenv("GEMINI_API_KEY") or st.secrets["gemini"]["api_key"])
            services["gemini"] = genai
    except Exception as e:
        st.warning(f"Gemini não configurado: {str(e)}")

    return services

services = init_services()

# --- Funções de Análise ---
def analyze_with_openai(prompt, model="gpt-4-turbo-preview"):
    """Analisa texto usando OpenAI com fallback automático"""
    try:
        response = services["openai"].chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        return response.choices[0].message.content, f"openai-{model}"
    except Exception as e:
        if "gpt-4" in model:
            return analyze_with_openai(prompt, "gpt-3.5-turbo")  # Fallback para GPT-3.5
        raise e

def analyze_with_gemini(prompt):
    """Analisa texto usando Google Gemini"""
    try:
        model = services["gemini"].GenerativeModel('gemini-1.5-pro-latest')
        response = model.generate_content(prompt)
        return response.text, "gemini-1.5"
    except Exception as e:
        raise Exception(f"Erro no Gemini: {str(e)}")

def analyze_with_fallback(prompt, selected_model):
    """Orquestrador de análise com fallback automático"""
    try:
        if "openai" in selected_model:
            model_name = selected_model.split("-")[-1]
            return analyze_with_openai(prompt, model_name)
        
        elif "gemini" in selected_model:
            return analyze_with_gemini(prompt)
            
        else:
            raise Exception("Modelo não implementado")
            
    except Exception as e:
        st.error(f"Erro no modelo primário: {str(e)}")
        st.warning("Tentando fallback automático...")
        
        # Ordem de fallback
        fallback_sequence = [
            "openai-gpt-3.5",
            "gemini-1.5"
        ]
        
        for model in fallback_sequence:
            try:
                return analyze_with_fallback(prompt, model)
            except:
                continue
                
        raise Exception("Todos os fallbacks falharam")

# --- Interface ---
st.title("📊 Analisador Avançado de Propostas")
st.caption("Compare propostas com edital base usando diferentes modelos de IA")

# Seletor de Modelo
available_models = []
if "openai" in services:
    available_models.extend(["openai-gpt-4", "openai-gpt-3.5"])
if "gemini" in services:
    available_models.append("gemini-1.5")

selected_model = st.selectbox(
    "🔧 Selecione o modelo de IA:",
    options=available_models,
    format_func=lambda x: MODEL_DISPLAY_NAMES.get(x, x),
    help="GPT-4 oferece melhores análises mas custa mais"
)

# Upload de arquivos
with st.expander("📤 Upload de Documentos", expanded=True):
    edital_file = st.file_uploader("Edital Base (PDF/DOCX)", type=["pdf", "docx"])
    propostas_files = st.file_uploader("Propostas (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True)

# Processamento
if st.button("🔍 Analisar Propostas", type="primary") and edital_file and propostas_files:
    progress_bar = st.progress(0)
    edital_text = read_file(edital_file)
    
    for i, proposta_file in enumerate(propostas_files):
        try:
            proposta_text = read_file(proposta_file)
            prompt = f"""
            [ANÁLISE TÉCNICA] Compare esta proposta com o edital base:

            EDITAL:
            {edital_text[:10000]}... [continua]

            PROPOSTA ({proposta_file.name}):
            {proposta_text[:10000]}... [continua]

            Forneça:
            1. Itens atendidos ✔️
            2. Itens não atendidos ❌  
            3. Score (0-100%) 📊
            4. Recomendações 💡
            """
            
            with st.spinner(f"Analisando {proposta_file.name}..."):
                analysis, used_model = analyze_with_fallback(prompt, selected_model)
                
                with st.container():
                    st.subheader(f"📝 {proposta_file.name}")
                    st.markdown(analysis)
                    generate_pdf_report(proposta_file.name, analysis)
                    
            progress_bar.progress((i + 1) / len(propostas_files))
            
        except Exception as e:
            st.error(f"Falha ao analisar {proposta_file.name}: {str(e)}")

# --- Funções Auxiliares ---
def read_file(file):
    """Lê PDF ou DOCX com tratamento de erro"""
    if file.name.endswith(".pdf"):
        return read_pdf(file)
    elif file.name.endswith(".docx"):
        return read_docx(file)
    else:
        raise ValueError("Formato não suportado")

def generate_pdf_report(filename, content):
    """Gera PDF com o resultado"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, f"Relatório: {filename}\n\n{content}")
    
    pdf_bytes = pdf.output(dest="S").encode("latin1")
    st.download_button(
        label="⬇️ Baixar Relatório",
        data=pdf_bytes,
        file_name=f"relatorio_{filename.split('.')[0]}.pdf",
        mime="application/pdf"
    )

# Rodapé
st.divider()
st.caption("ℹ️ Use modelos GPT-4 para análises mais precisas. Configure billing na OpenAI para acesso completo.")

# Monitor de Uso
if "openai" in services:
    try:
        usage = services["openai"].usage.retrieve()
        st.sidebar.metric("Tokens usados (OpenAI)", f"{usage.total_tokens:,}")
    except:
        pass
