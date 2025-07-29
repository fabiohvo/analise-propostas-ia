import streamlit as st
import sqlite3
from datetime import datetime
import os
import time
from dotenv import load_dotenv
import sys
import subprocess

# --- Verificação e Instalação de Dependências ---
def install_if_missing(package):
    try:
        _import_(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Lista de pacotes necessários
REQUIRED_PACKAGES = [
    "PyPDF2>=3.0.0",
    "docx2txt>=0.9",
    "openai>=1.12.0",
    "google-generativeai>=0.3.0",
    "fpdf2>=2.8.3",
    "python-dotenv>=1.0.0"
]

for package in REQUIRED_PACKAGES:
    install_if_missing(package.split('>=')[0])

# --- Importações Garantidas ---
from PyPDF2 import PdfReader, PdfException
import docx2txt
from openai import OpenAI
import google.generativeai as genai
from fpdf import FPDF

# --- Configuração Inicial ---
st.set_page_config(
    page_title="Analisador de Propostas IA",
    page_icon="📄",
    layout="wide"
)
load_dotenv()

# --- Constantes ---
MAX_FILE_SIZE_MB = 10
MAX_TOKENS = 8000

# --- Inicialização de Serviços ---
def init_services():
    services = {}
    try:
        if os.getenv("OPENAI_API_KEY") or st.secrets.get("openai", {}).get("api_key"):
            services["openai"] = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or st.secrets["openai"]["api_key"])
    except Exception:
        pass

    try:
        if os.getenv("GEMINI_API_KEY") or st.secrets.get("gemini", {}).get("api_key"):
            genai.configure(api_key=os.getenv("GEMINI_API_KEY") or st.secrets["gemini"]["api_key"])
            services["gemini"] = genai
    except Exception:
        pass

    return services

services = init_services()

# --- Funções Principais (Mantidas como estavam) ---
def read_pdf(file):
    try:
        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Arquivo muito grande (limite: {MAX_FILE_SIZE_MB}MB)")

        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        
        if not text.strip():
            raise ValueError("PDF não contém texto legível")
        
        return text[:MAX_TOKENS]
    except Exception as e:
        raise ValueError(f"Erro no PDF: {str(e)}")

def read_docx(file):
    try:
        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Arquivo muito grande (limite: {MAX_FILE_SIZE_MB}MB)")
        
        text = docx2txt.process(file)
        if not text.strip():
            raise ValueError("DOCX vazio ou sem texto legível")
        
        return text[:MAX_TOKENS]
    except Exception as e:
        raise ValueError(f"Erro no DOCX: {str(e)}")

def read_file(file):
    if not file:
        raise ValueError("Nenhum arquivo fornecido")
    
    try:
        if file.name.endswith(".pdf"):
            return read_pdf(file)
        elif file.name.endswith(".docx"):
            return read_docx(file)
        else:
            raise ValueError("Formato não suportado")
    except Exception as e:
        raise ValueError(f"Erro ao processar {file.name}: {str(e)}")

# --- Análise com IA (Mantida como estava) ---
def analyze_with_openai(prompt, model="gpt-4-turbo-preview"):
    try:
        response = services["openai"].chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt[:MAX_TOKENS]}],
            temperature=0.4
        )
        return response.choices[0].message.content, "openai"
    except Exception as e:
        if model != "gpt-3.5-turbo":
            return analyze_with_openai(prompt, "gpt-3.5-turbo")
        raise

def analyze_with_gemini(prompt):
    try:
        model = services["gemini"].GenerativeModel('gemini-1.5-pro-latest')
        response = model.generate_content(prompt[:MAX_TOKENS])
        return response.text, "gemini"
    except Exception as e:
        raise

def safe_analyze(prompt):
    error_log = []
    providers = [
        ("openai", analyze_with_openai),
        ("gemini", analyze_with_gemini)
    ]
    
    for provider_name, analyzer in providers:
        if provider_name not in services:
            continue
            
        try:
            return analyzer(prompt)
        except Exception as e:
            error_log.append(f"{provider_name}: {str(e)}")
            time.sleep(2)
    
    raise Exception("Todos os provedores falharam")

# --- Interface do Usuário (Mantida como estava) ---
def main():
    st.title("📊 Analisador de Propostas com IA")
    
    available_providers = []
    if "openai" in services:
        available_providers.append("OpenAI")
    if "gemini" in services:
        available_providers.append("Gemini")
    
    if not available_providers:
        st.error("Configure pelo menos uma API (OpenAI ou Gemini)")
        return
    
    selected_provider = st.radio(
        "🔧 Provedor de IA:",
        available_providers
    )

    with st.expander("📤 Upload de Documentos", expanded=True):
        edital_file = st.file_uploader("Edital Base (PDF/DOCX)", type=["pdf", "docx"])
        propostas_files = st.file_uploader("Propostas (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True)

    if st.button("🔍 Analisar Propostas", type="primary") and edital_file and propostas_files:
        try:
            edital_text = read_file(edital_file)
            progress_bar = st.progress(0)
            
            for i, proposta_file in enumerate(propostas_files):
                try:
                    proposta_text = read_file(proposta_file)
                    prompt = f"""
                    [ANÁLISE TÉCNICA] Compare esta proposta com o edital base:

                    EDITAL:
                    {edital_text[:5000]}

                    PROPOSTA ({proposta_file.name}):
                    {proposta_text[:5000]}

                    Forneça:
                    1. Itens atendidos ✔️  
                    2. Itens não atendidos ❌  
                    3. Score (0-100%) 📊  
                    4. Recomendações 💡
                    """
                    
                    with st.spinner(f"Analisando {proposta_file.name}..."):
                        analysis, used_provider = safe_analyze(prompt)
                        
                        with st.container():
                            st.subheader(f"📝 {proposta_file.name}")
                            st.markdown(analysis)
                            
                            pdf = FPDF()
                            pdf.add_page()
                            pdf.set_font("Arial", size=12)
                            pdf.multi_cell(0, 10, analysis)
                            pdf_bytes = pdf.output(dest="S").encode("latin1")
                            
                            st.download_button(
                                label="⬇️ Baixar Relatório",
                                data=pdf_bytes,
                                file_name=f"relatorio_{proposta_file.name[:50]}.pdf",
                                mime="application/pdf"
                            )
                    
                    progress_bar.progress((i + 1) / len(propostas_files))
                
                except Exception as e:
                    st.error(f"Erro em {proposta_file.name}: {str(e)}")
                    continue
            
            st.success("✅ Análise concluída!")
        
        except Exception as e:
            st.error(f"Erro crítico: {str(e)}")

if _name_ == "_main_":
    main()
