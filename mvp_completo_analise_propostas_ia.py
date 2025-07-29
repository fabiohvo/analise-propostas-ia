import streamlit as st
from PyPDF2 import PdfReader, PdfException
import docx2txt
from openai import OpenAI, APIConnectionError, AuthenticationError, RateLimitError
import google.generativeai as genai
from fpdf import FPDF
import sqlite3
from datetime import datetime
import os
import time
from dotenv import load_dotenv

# Configuração inicial
st.set_page_config(
    page_title="Analisador de Propostas IA",
    page_icon="📄",
    layout="wide"
)

# Carrega variáveis de ambiente
load_dotenv()

# --- Constantes ---
MAX_FILE_SIZE_MB = 10  # Tamanho máximo por arquivo
MAX_TOKENS = 8000  # Limite para evitar custos altos

# --- Inicialização Segura de Serviços ---
def init_services():
    """Inicializa serviços de IA com tratamento de erros"""
    services = {}
    errors = []

    # OpenAI
    try:
        openai_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("openai", {}).get("api_key")
        if openai_key:
            services["openai"] = OpenAI(api_key=openai_key)
    except Exception as e:
        errors.append(f"OpenAI: {str(e)}")

    # Google Gemini
    try:
        gemini_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("gemini", {}).get("api_key")
        if gemini_key:
            genai.configure(api_key=gemini_key)
            services["gemini"] = genai
    except Exception as e:
        errors.append(f"Gemini: {str(e)}")

    return services, errors

services, service_errors = init_services()

# --- Funções Robustas para Arquivos ---
def read_pdf(file):
    """Lê PDF com tratamento de erros avançado"""
    try:
        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Arquivo muito grande (limite: {MAX_FILE_SIZE_MB}MB)")

        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            try:
                text += page.extract_text() or ""
            except Exception as e:
                st.warning(f"Erro ao extrair texto de página: {str(e)}")
                continue
        
        if not text.strip():
            raise ValueError("PDF não contém texto legível")
        
        return text[:MAX_TOKENS]  # Limita o tamanho
    
    except PdfException as e:
        raise ValueError(f"Erro no PDF: {str(e)}")
    except Exception as e:
        raise ValueError(f"Erro ao ler arquivo: {str(e)}")

def read_docx(file):
    """Lê DOCX com tratamento de erros"""
    try:
        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Arquivo muito grande (limite: {MAX_FILE_SIZE_MB}MB)")
        
        text = docx2txt.process(file)
        if not text.strip():
            raise ValueError("DOCX vazio ou sem texto legível")
        
        return text[:MAX_TOKENS]
    except Exception as e:
        raise ValueError(f"Erro ao ler DOCX: {str(e)}")

def read_file(file):
    """Seleciona leitor apropriado com validação"""
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

# --- Análise com Fallback Automático ---
def analyze_with_openai(prompt, model="gpt-4-turbo-preview"):
    """Analisa texto com OpenAI e fallback para GPT-3.5"""
    try:
        if "openai" not in services:
            raise APIConnectionError("OpenAI não configurada")
        
        response = services["openai"].chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt[:MAX_TOKENS]}],
            temperature=0.4
        )
        return response.choices[0].message.content, "openai"
    
    except RateLimitError:
        if model != "gpt-3.5-turbo":
            return analyze_with_openai(prompt, "gpt-3.5-turbo")
        raise
    except Exception as e:
        raise Exception(f"OpenAI: {str(e)}")

def analyze_with_gemini(prompt):
    """Analisa texto usando Google Gemini"""
    try:
        if "gemini" not in services:
            raise APIConnectionError("Gemini não configurado")
        
        model = services["gemini"].GenerativeModel('gemini-1.5-pro-latest')
        response = model.generate_content(prompt[:MAX_TOKENS])
        
        if not response.text:
            raise ValueError("Resposta vazia do Gemini")
        
        return response.text, "gemini"
    except Exception as e:
        raise Exception(f"Gemini: {str(e)}")

def safe_analyze(prompt):
    """Orquestrador de análise com fallback automático"""
    error_log = []
    
    # Ordem de tentativas
    providers = [
        ("openai", analyze_with_openai),
        ("gemini", analyze_with_gemini)
    ]
    
    for provider_name, analyzer in providers:
        if provider_name not in services:
            continue
            
        try:
            result, used_provider = analyzer(prompt)
            return result, used_provider
        except Exception as e:
            error_log.append(f"{provider_name.upper()}: {str(e)}")
            time.sleep(2)  # Espera para evitar rate limit
    
    raise Exception(f"Todos os provedores falharam:\n" + "\n".join(error_log))

# --- Interface ---
def main():
    st.title("📊 Analisador de Propostas com IA")
    
    # Avisos de serviço
    if service_errors:
        st.warning("⚠️ Problemas nos serviços:")
        for error in service_errors:
            st.error(error)
    
    # Seletor de provedor
    available_providers = []
    if "openai" in services:
        available_providers.append(("OpenAI GPT-4", "openai"))
    if "gemini" in services:
        available_providers.append(("Google Gemini", "gemini"))
    
    if not available_providers:
        st.error("Nenhum serviço de IA disponível. Configure pelo menos uma API.")
        return
    
    selected_provider = st.radio(
        "🔧 Selecione o provedor de IA:",
        options=[p[0] for p in available_providers],
        index=0
    )
    provider_key = [p[1] for p in available_providers if p[0] == selected_provider][0]

    # Upload de arquivos
    with st.expander("📤 Upload de Documentos", expanded=True):
        edital_file = st.file_uploader(
            "Edital Base (PDF/DOCX)",
            type=["pdf", "docx"],
            key="edital_uploader"
        )
        propostas_files = st.file_uploader(
            "Propostas (PDF/DOCX)",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="propostas_uploader"
        )

    # Processamento
    if st.button("🔍 Analisar Propostas", type="primary") and edital_file and propostas_files:
        try:
            # Leitura segura dos arquivos
            try:
                edital_text = read_file(edital_file)
                st.session_state.edital_text = edital_text
            except Exception as e:
                st.error(f"Erro no edital: {str(e)}")
                return
            
            progress_bar = st.progress(0)
            results = []
            
            for i, proposta_file in enumerate(propostas_files):
                try:
                    # Leitura da proposta
                    try:
                        proposta_text = read_file(proposta_file)
                    except Exception as e:
                        st.warning(f"Pulando {proposta_file.name}: {str(e)}")
                        continue
                    
                    # Construção do prompt
                    prompt = f"""
                    [ANÁLISE TÉCNICA] Compare esta proposta com o edital base:

                    EDITAL:
                    {edital_text[:5000]}... [continua]

                    PROPOSTA ({proposta_file.name}):
                    {proposta_text[:5000]}... [continua]

                    Forneça:
                    1. Itens atendidos ✔️  
                    2. Itens não atendidos ❌  
                    3. Score (0-100%) 📊  
                    4. Recomendações 💡
                    """
                    
                    # Análise
                    with st.spinner(f"Analisando {proposta_file.name}..."):
                        try:
                            analysis, used_provider = safe_analyze(prompt)
                            
                            with st.container():
                                st.subheader(f"📝 {proposta_file.name} (via {used_provider.upper()})")
                                st.markdown(analysis)
                                
                                # Geração de PDF
                                try:
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
                                except Exception as e:
                                    st.error(f"Erro ao gerar PDF: {str(e)}")
                            
                            results.append((proposta_file.name, analysis))
                            
                        except Exception as e:
                            st.error(f"Falha na análise: {str(e)}")
                            continue
                    
                    progress_bar.progress((i + 1) / len(propostas_files))
                
                except Exception as e:
                    st.error(f"Erro inesperado: {str(e)}")
                    continue
            
            # Resultados finais
            if results:
                st.success("✅ Análise concluída!")
                st.session_state.results = results
            else:
                st.warning("Nenhuma proposta foi analisada com sucesso")
        
        except Exception as e:
            st.error(f"Erro crítico: {str(e)}")

if _name_ == "_main_":
    main()
