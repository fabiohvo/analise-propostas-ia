import streamlit as st
import sqlite3
from datetime import datetime
import os
import time
import sys
import subprocess
from typing import Tuple, Optional

# --- CONFIGURAÇÃO DE AMBIENTE ROBUSTA ---
def install_package(package_spec: str) -> bool:
    """Instala pacotes com tratamento avançado de erros"""
    package_name = package_spec.split('>=')[0]
    try:
        # Verifica se já está instalado primeiro
        import importlib
        importlib.import_module(package_name)
        return True
    except ImportError:
        try:
            # Tenta instalar com a especificação completa
            subprocess.run(
                [sys.executable, "-m", "pip", "install", package_spec],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            try:
                # Fallback: instala apenas o nome do pacote
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", package_name],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=60
                )
                return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                st.warning(f"Não foi possível instalar {package_name}")
                return False

# Lista de pacotes essenciais com fallbacks
ESSENTIAL_PACKAGES = [
    "pypdf>=3.0.0",  # Usando pypdf como principal (sucessor do PyPDF2)
    "docx2txt>=0.9",
    "openai>=1.12.0",
    "google-generativeai>=0.3.0",
    "fpdf2>=2.8.3",
    "python-dotenv>=1.0.0"
]

# Instalação controlada
for package in ESSENTIAL_PACKAGES:
    if not install_package(package):
        st.error(f"Falha crítica ao instalar {package}. O app pode não funcionar corretamente.")

# --- IMPORTACOES COM FALLBACKS ---
try:
    from pypdf import PdfReader, PdfException  # Principal
    st.info("Usando pypdf para leitura de PDFs")
except ImportError:
    st.error("Biblioteca pypdf é obrigatória. O app não pode continuar.")
    st.stop()

try:
    import docx2txt
    from openai import OpenAI
    import google.generativeai as genai
    from fpdf import FPDF
    from dotenv import load_dotenv
except ImportError as e:
    st.error(f"FALHA NAS IMPORTAÇÕES ESSENCIAIS: {str(e)}")
    st.stop()

# --- CONSTANTES ---
MAX_FILE_SIZE_MB = 25
MAX_TOKENS = 100000
TIMEOUT_ANALISE = 300  # 5 minutos

# --- CLASSE PRINCIPAL ---
class AnalisadorContratos:
    def _init_(self):
        self.servicos = self._iniciar_servicos()
    
    def _iniciar_servicos(self) -> dict:
        """Inicializa serviços de IA com fallback"""
        servicos = {}
        load_dotenv()
        
        # OpenAI
        try:
            openai_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("openai", {}).get("api_key")
            if openai_key:
                servicos["openai"] = OpenAI(
                    api_key=openai_key,
                    timeout=TIMEOUT_ANALISE
                )
        except Exception as e:
            st.warning(f"OpenAI não disponível: {str(e)}")
        
        # Gemini
        try:
            gemini_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("gemini", {}).get("api_key")
            if gemini_key:
                genai.configure(api_key=gemini_key)
                servicos["gemini"] = genai
        except Exception as e:
            st.warning(f"Gemini não disponível: {str(e)}")
        
        if not servicos:
            st.error("Nenhum serviço de IA disponível. Configure pelo menos uma API.")
        return servicos

# --- FUNÇÕES PRINCIPAIS ---
def ler_arquivo(file) -> str:
    """Lê PDF ou DOCX com tratamento robusto de erros"""
    try:
        if not file:
            raise ValueError("Nenhum arquivo fornecido")
        
        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Arquivo excede o limite de {MAX_FILE_SIZE_MB}MB")
        
        if file.name.endswith('.pdf'):
            reader = PdfReader(file)
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
        elif file.name.endswith('.docx'):
            text = docx2txt.process(file)
        else:
            raise ValueError("Formato de arquivo não suportado")
        
        if not text.strip():
            raise ValueError("Arquivo sem texto legível")
        
        return text[:MAX_TOKENS]  # Limita o tamanho
    
    except PdfException as e:
        raise ValueError(f"Erro na leitura do PDF: {str(e)}")
    except Exception as e:
        raise ValueError(f"Erro ao processar arquivo: {str(e)}")

def analisar_contrato(contrato_base: str, proposta: str, nome_proposta: str) -> Tuple[str, str]:
    """Realiza análise de conformidade contratual"""
    analisador = AnalisadorContratos()
    
    # Pré-processamento
    contrato_base = contrato_base[:50000]  # Limita o tamanho
    proposta = proposta[:50000]
    
    prompt = f"""
    [ANÁLISE CONTRATUAL PROFISSIONAL]
    Compare rigorosamente esta proposta com o contrato base:

    CONTRATO BASE:
    {contrato_base}

    PROPOSTA ({nome_proposta}):
    {proposta}

    Forneça:
    1. Conformidade geral (0-100%)
    2. Itens atendidos/parcialmente/não atendidos
    3. Riscos contratuais
    4. Recomendações específicas
    """
    
    # Tenta OpenAI primeiro
    if "openai" in analisador.servicos:
        try:
            response = analisador.servicos["openai"].chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000
            )
            return response.choices[0].message.content, "GPT-4 Turbo"
        except Exception as e:
            st.warning(f"OpenAI falhou: {str(e)}")
    
    # Fallback para Gemini
    if "gemini" in analisador.servicos:
        try:
            model = genai.GenerativeModel('gemini-1.5-pro-latest')
            response = model.generate_content(prompt)
            return response.text, "Gemini 1.5 Pro"
        except Exception as e:
            st.warning(f"Gemini falhou: {str(e)}")
    
    raise Exception("Todos os serviços de IA falharam")

# --- INTERFACE STREAMLIT ---
def main():
    st.set_page_config(
        page_title="Analisador Contratual",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("🔍 Analisador de Conformidade Contratual")
    st.write("Compare propostas comerciais com contratos base usando IA")
    
    # Upload de arquivos
    with st.expander("📤 Upload de Documentos", expanded=True):
        contrato_base = st.file_uploader("Contrato Base (PDF/DOCX)", type=["pdf", "docx"])
        propostas = st.file_uploader("Propostas (PDF/DOCX)", type=["pdf", "docx"], accept_multiple_files=True)
    
    # Análise
    if st.button("Analisar Propostas", type="primary") and contrato_base and propostas:
        try:
            with st.spinner("Processando contrato base..."):
                texto_base = ler_arquivo(contrato_base)
            
            for proposta in propostas:
                try:
                    with st.spinner(f"Analisando {proposta.name}..."):
                        texto_proposta = ler_arquivo(proposta)
                        analise, modelo = analisar_contrato(texto_base, texto_proposta, proposta.name)
                        
                        with st.container():
                            st.subheader(f"Resultado: {proposta.name}")
                            st.markdown(analise)
                            
                            # Gerar PDF
                            pdf = FPDF()
                            pdf.add_page()
                            pdf.set_font("Arial", size=10)
                            pdf.multi_cell(0, 8, analise)
                            pdf_bytes = pdf.output(dest="S").encode("latin1")
                            
                            st.download_button(
                                "Baixar Relatório",
                                data=pdf_bytes,
                                file_name=f"Analise_{proposta.name}.pdf",
                                mime="application/pdf"
                            )
                
                except Exception as e:
                    st.error(f"Erro na proposta {proposta.name}: {str(e)}")
                    continue
            
            st.success("Análise concluída com sucesso!")
        
        except Exception as e:
            st.error(f"Erro crítico: {str(e)}")

if _name_ == "_main_":
    main()
