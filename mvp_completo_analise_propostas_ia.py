import streamlit as st
import sqlite3
from datetime import datetime
import os
import time
import sys
import subprocess
from typing import Tuple, List, Optional

# --- Configuração de Ambiente ---
try:
    # Verifica e instala dependências faltantes
    def install_package(package_name: str):
        try:
            _import_(package_name)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name.split('>=')[0]])
            _import_(package_name.split('>=')[0])

    # Lista de pacotes necessários
    REQUIRED_PACKAGES = [
        "PyPDF2>=3.0.0",
        "docx2txt>=0.9",
        "openai>=1.12.0",
        "google-generativeai>=0.3.0",
        "fpdf2>=2.8.3",
        "python-dotenv>=1.0.0",
        "tiktoken>=0.5.1"
    ]

    for package in REQUIRED_PACKAGES:
        install_package(package)

    # Importações principais
    from PyPDF2 import PdfReader, PdfException
    import docx2txt
    from openai import OpenAI
    import google.generativeai as genai
    from fpdf import FPDF
    from dotenv import load_dotenv
    import tiktoken

except Exception as e:
    st.error(f"ERRO CRÍTICO NA INICIALIZAÇÃO: {str(e)}")
    st.stop()

# --- Constantes ---
MAX_FILE_SIZE_MB = 25  # 25MB por arquivo
MAX_TOKENS = 120000  # Limite para contexto estendido
MAX_ANALYSIS_TIME = 300  # 5 minutos por análise

# --- Classes de Suporte ---
class ContractAnalyzer:
    """Classe principal para análise contratual"""
    
    def _init_(self):
        self.services = self._initialize_services()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
    def _initialize_services(self) -> dict:
        """Inicializa serviços de IA com tratamento robusto"""
        services = {}
        load_dotenv()
        
        # Configura OpenAI
        try:
            openai_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("openai", {}).get("api_key")
            if openai_key:
                services["openai"] = OpenAI(api_key=openai_key)
        except Exception as e:
            st.warning(f"OpenAI não disponível: {str(e)}")
        
        # Configura Gemini
        try:
            gemini_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("gemini", {}).get("api_key")
            if gemini_key:
                genai.configure(api_key=gemini_key)
                services["gemini"] = genai
        except Exception as e:
            st.warning(f"Gemini não disponível: {str(e)}")
        
        return services
    
    def count_tokens(self, text: str) -> int:
        """Conta tokens para gerenciamento de custos"""
        return len(self.tokenizer.encode(text))

# --- Funções Principais ---
def read_contract_file(file) -> str:
    """
    Lê arquivos de contrato (PDF/DOCX) com tratamento robusto
    Retorna texto limpo e normalizado
    """
    try:
        # Verificação básica
        if not file:
            raise ValueError("Nenhum arquivo fornecido")
        
        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Arquivo excede o tamanho máximo de {MAX_FILE_SIZE_MB}MB")
        
        # Processamento por tipo de arquivo
        if file.name.endswith('.pdf'):
            reader = PdfReader(file)
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
        elif file.name.endswith('.docx'):
            text = docx2txt.process(file)
        else:
            raise ValueError("Formato de arquivo não suportado")
        
        # Limpeza do texto
        text = " ".join(text.split())  # Remove espaços excessivos
        if not text.strip():
            raise ValueError("O arquivo não contém texto legível")
        
        return text[:500000]  # Limite seguro para processamento
    
    except PdfException as e:
        raise ValueError(f"Erro na leitura do PDF: {str(e)}")
    except Exception as e:
        raise ValueError(f"Erro ao processar arquivo: {str(e)}")

def analyze_contract_compliance(base_contract: str, proposal: str, proposal_name: str) -> Tuple[str, str]:
    """
    Analisa a conformidade entre contrato base e proposta
    Retorna: (análise_formatada, modelo_utilizado)
    """
    analyzer = ContractAnalyzer()
    
    # Pré-processamento
    base_contract = base_contract[:150000]  # Limita o tamanho
    proposal = proposal[:150000]
    
    # Prompt de análise profissional
    prompt = f"""
    [ANÁLISE CONTRATUAL PROFISSIONAL]
    
    CONTEXTO:
    Você é um especialista em análise contratual para grandes empresas como Vale, Petrobras, etc.
    Sua tarefa é comparar rigorosamente uma proposta comercial com um contrato base.

    CONTRATO BASE (resumido):
    {base_contract[:50000]}

    PROPOSTA ANALISADA ({proposal_name}):
    {proposal[:50000]}

    REQUISITOS DA ANÁLISE:
    1. Itens plenamente atendidos (com evidências)
    2. Itens parcialmente atendidos (com especificações)
    3. Itens não atendidos (com gravidade)
    4. Inconsistências conceituais
    5. Riscos contratuais identificados
    6. Pontos de atenção jurídica
    7. Score de conformidade (0-100%)
    8. Recomendações estratégicas

    FORMATAÇÃO:
    Use markdown com destaques e seções claras.
    Inclua exemplos específicos de trechos problemáticos.
    """
    
    # Tenta OpenAI primeiro
    if "openai" in analyzer.services:
        try:
            response = analyzer.services["openai"].chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000
            )
            analysis = response.choices[0].message.content
            return analysis, "GPT-4 Turbo"
        except Exception as e:
            st.warning(f"OpenAI falhou: {str(e)}")
    
    # Fallback para Gemini
    if "gemini" in analyzer.services:
        try:
            model = analyzer.services["gemini"].GenerativeModel('gemini-1.5-pro-latest')
            response = model.generate_content(prompt)
            return response.text, "Gemini 1.5 Pro"
        except Exception as e:
            st.warning(f"Gemini falhou: {str(e)}")
    
    raise Exception("Todos os serviços de IA falharam")

# --- Interface Streamlit ---
def main():
    # Configuração inicial
    st.set_page_config(
        page_title="Analisador Contratual Profissional",
        page_icon="📑",
        layout="wide"
    )
    
    st.title("🔍 Analisador de Conformidade Contratual")
    st.markdown("""
    *Sistema profissional para análise de propostas vs contratos base*  
    Identifica inconsistências, riscos e oportunidades em documentos contratuais
    """)
    
    # Controles principais
    with st.expander("📁 UPLOAD DE DOCUMENTOS", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            base_contract = st.file_uploader(
                "CONTRATO BASE (PDF/DOCX)",
                type=["pdf", "docx"],
                key="contract"
            )
        with col2:
            proposals = st.file_uploader(
                "PROPOSTAS COMERCIAIS (PDF/DOCX)",
                type=["pdf", "docx"],
                accept_multiple_files=True,
                key="proposals"
            )
    
    # Análise
    if st.button("🚀 ANALISAR CONFORMIDADE", type="primary"):
        if not base_contract or not proposals:
            st.warning("Envie ambos: contrato base e propostas")
            return
        
        try:
            # Processa contrato base
            with st.spinner("Processando contrato base..."):
                base_text = read_contract_file(base_contract)
                st.session_state.base_text = base_text
            
            # Processa cada proposta
            for proposal in proposals:
                try:
                    with st.spinner(f"Analisando {proposal.name}..."):
                        # Leitura e análise
                        proposal_text = read_contract_file(proposal)
                        start_time = time.time()
                        
                        analysis, model_used = analyze_contract_compliance(
                            base_text,
                            proposal_text,
                            proposal.name
                        )
                        
                        # Exibe resultados
                        with st.container():
                            st.subheader(f"📋 {proposal.name}")
                            st.caption(f"Modelo usado: {model_used}")
                            
                            # Análise formatada
                            st.markdown("---")
                            st.markdown(analysis)
                            st.markdown("---")
                            
                            # Download
                            pdf = FPDF()
                            pdf.add_page()
                            pdf.set_font("Arial", size=10)
                            pdf.multi_cell(0, 8, analysis)
                            pdf_bytes = pdf.output(dest="S").encode("latin1")
                            
                            st.download_button(
                                label="📥 BAIXAR RELATÓRIO",
                                data=pdf_bytes,
                                file_name=f"ANALISE_{proposal.name.split('.')[0]}.pdf",
                                mime="application/pdf"
                            )
                            
                            # Log de desempenho
                            elapsed = time.time() - start_time
                            st.info(f"Análise concluída em {elapsed:.2f} segundos")
                
                except Exception as e:
                    st.error(f"Falha na análise de {proposal.name}: {str(e)}")
                    continue
            
            st.success("✅ TODAS AS ANÁLISES CONCLUÍDAS!")
        
        except Exception as e:
            st.error(f"ERRO NO PROCESSAMENTO: {str(e)}")
            st.exception(e)

if _name_ == "_main_":
    main()
