import streamlit as st
import sqlite3
from datetime import datetime
import os
import time
from pypdf import PdfReader
import docx2txt
from openai import OpenAI
import google.generativeai as genai
from fpdf import FPDF
from dotenv import load_dotenv

# Configurações básicas
st.set_page_config(
    page_title="Analisador Contratual Vale",
    page_icon="📑",
    layout="wide"
)

# Constantes
MAX_FILE_SIZE_MB = 25
TIMEOUT_ANALISE = 300  # 5 minutos

@st.cache_resource
def init_services():
    """Inicializa serviços de IA com timeout"""
    services = {}
    load_dotenv()
    
    try:
        # Configura OpenAI
        if os.getenv("OPENAI_API_KEY") or st.secrets.get("openai", {}).get("api_key"):
            services["openai"] = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY") or st.secrets["openai"]["api_key"],
                timeout=TIMEOUT_ANALISE
            )
    except Exception as e:
        st.warning(f"OpenAI não disponível: {str(e)}")
    
    try:
        # Configura Gemini
        if os.getenv("GEMINI_API_KEY") or st.secrets.get("gemini", {}).get("api_key"):
            genai.configure(
                api_key=os.getenv("GEMINI_API_KEY") or st.secrets["gemini"]["api_key"]
            )
            services["gemini"] = genai
    except Exception as e:
        st.warning(f"Gemini não disponível: {str(e)}")
    
    if not services:
        st.error("Configure pelo menos uma API no menu Settings > Secrets")
        st.stop()
    
    return services

def read_file(file):
    """Leitura otimizada de arquivos"""
    try:
        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Tamanho máximo: {MAX_FILE_SIZE_MB}MB")
            
        if file.name.endswith('.pdf'):
            reader = PdfReader(file)
            return "\n".join([page.extract_text() or "" for page in reader.pages][:50])  # Limita a 50 páginas
            
        elif file.name.endswith('.docx'):
            return docx2txt.process(file)[:500000]  # Limita o tamanho
            
        raise ValueError("Formato inválido (use PDF ou DOCX)")
    except Exception as e:
        raise ValueError(f"Erro ao ler {file.name}: {str(e)}")

def analyze_contract(base_text, proposal_text, proposal_name):
    """Análise com timeout e fallback"""
    services = init_services()
    prompt = f"""
    [ANÁLISE VALE] Compare esta proposta com o contrato padrão:

    CONTRATO BASE:
    {base_text[:30000]}

    PROPOSTA ({proposal_name}):
    {proposal_text[:30000]}

    Entregue:
    1. Conformidade (0-100%)
    2. Itens críticos faltantes
    3. 3 recomendações específicas
    """
    
    # Tenta OpenAI
    if "openai" in services:
        try:
            response = services["openai"].chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                timeout=30  # Timeout reduzido
            )
            return response.choices[0].message.content
        except:
            pass
    
    # Fallback Gemini
    if "gemini" in services:
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(prompt, request_options={"timeout": 30})
            return response.text
        except:
            pass
    
    raise Exception("Todas as APIs falharam")

def main():
    st.title("📑 Análise de Propostas Vale")
    
    # Upload otimizado
    with st.form("upload_form"):
        base_file = st.file_uploader("Contrato Base Vale", type=["pdf", "docx"])
        prop_files = st.file_uploader("Propostas", type=["pdf", "docx"], accept_multiple_files=True)
        
        if st.form_submit_button("Iniciar Análise", type="primary"):
            if base_file and prop_files:
                try:
                    base_text = read_file(base_file)
                    
                    for prop in prop_files:
                        with st.spinner(f"Analisando {prop.name}..."):
                            try:
                                prop_text = read_file(prop)
                                analysis = analyze_contract(base_text, prop_text, prop.name)
                                
                                with st.expander(f"Resultado: {prop.name}"):
                                    st.write(analysis)
                                    
                                    # PDF seguro
                                    pdf = FPDF()
                                    pdf.add_page()
                                    pdf.set_font("Arial", size=10)
                                    pdf.multi_cell(0, 8, analysis)
                                    pdf_bytes = pdf.output(dest='S')
                                    if isinstance(pdf_bytes, str):
                                        pdf_bytes = pdf_bytes.encode('latin1')
                                    
                                    st.download_button(
                                        "Baixar Relatório",
                                        data=pdf_bytes,
                                        file_name=f"Vale_Analise_{prop.name[:50]}.pdf"
                                    )
                            
                            except Exception as e:
                                st.error(f"Falha em {prop.name}: {str(e)}")
                                continue
                    
                    st.success("Concluído!")
                
                except Exception as e:
                    st.error(f"Erro principal: {str(e)}")

if __name_ == "__main_":
    main()
