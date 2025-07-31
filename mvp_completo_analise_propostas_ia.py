import streamlit as st
import sqlite3
from datetime import datetime
import os
import time
import sys
import subprocess
from typing import Tuple, Optional

# --- CONFIGURAÇÃO DE AMBIENTE À PROVA DE FALHAS ---
def install_package(package_name: str) -> bool:
    """Sistema de instalação robusto com múltiplos fallbacks"""
    try:
        # Tenta instalar normalmente
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120
        )
        return True
    except Exception:
        try:
            # Fallback 1: Tentar com --user
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--user", package_name],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120
            )
            return True
        except Exception:
            try:
                # Fallback 2: Tentar sem verificação
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--no-deps", package_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=120
                )
                return True
            except Exception:
                return False

# Lista de pacotes prioritários
PACKAGES = [
    "pypdf>=3.0.0",  # Principal
    "PyPDF2>=3.0.0",  # Fallback
    "pdfminer.six>=20221105",  # Fallback extremo
    "docx2txt>=0.9",
    "openai>=1.12.0",
    "google-generativeai>=0.3.0",
    "fpdf2>=2.8.3",
    "python-dotenv>=1.0.0"
]

# Instalação com relatório
success_count = 0
for package in PACKAGES:
    if install_package(package):
        success_count += 1
    else:
        st.warning(f"⚠️ Falha ao instalar: {package.split('>=')[0]}")

if success_count < 5:  # Mínimo de pacotes essenciais
    st.error("Falha crítica na instalação de dependências")
    st.stop()

# --- SISTEMA DE IMPORTACOES COM FALLBACK ---
PDF_READER = None
try:
    from pypdf import PdfReader as PDF_READER
    st.info("✅ Usando pypdf (recomendado)")
except ImportError:
    try:
        from PyPDF2 import PdfReader as PDF_READER
        st.info("ℹ️ Usando PyPDF2 (fallback)")
    except ImportError:
        try:
            from pdfminer.high_level import extract_text as PDF_READER
            st.info("ℹ️ Usando pdfminer (fallback avançado)")
        except ImportError:
            st.error("❌ Nenhuma biblioteca PDF disponível!")
            st.stop()

# Outras importações essenciais
try:
    import docx2txt
    from openai import OpenAI
    import google.generativeai as genai
    from fpdf import FPDF
    from dotenv import load_dotenv
except ImportError as e:
    st.error(f"❌ Falha em importações essenciais: {str(e)}")
    st.stop()

# --- CONSTANTES ---
MAX_FILE_SIZE_MB = 25
TIMEOUT_ANALISE = 300

class AnalisadorContratos:
    def _init_(self):
        self.servicos = self._iniciar_servicos()
    
    def _iniciar_servicos(self) -> dict:
        """Inicialização robusta dos serviços de IA"""
        servicos = {}
        load_dotenv()
        
        # Configuração OpenAI
        try:
            if "OPENAI_API_KEY" in os.environ or "openai" in st.secrets:
                servicos["openai"] = OpenAI(
                    api_key=os.getenv("OPENAI_API_KEY") or st.secrets["openai"]["api_key"],
                    timeout=TIMEOUT_ANALISE
                )
        except Exception as e:
            st.warning(f"OpenAI não disponível: {str(e)}")
        
        # Configuração Gemini
        try:
            if "GEMINI_API_KEY" in os.environ or "gemini" in st.secrets:
                genai.configure(
                    api_key=os.getenv("GEMINI_API_KEY") or st.secrets["gemini"]["api_key"]
                )
                servicos["gemini"] = genai
        except Exception as e:
            st.warning(f"Gemini não disponível: {str(e)}")
        
        return servicos

def ler_arquivo(file) -> str:
    """Sistema de leitura de arquivos robusto"""
    try:
        if not file:
            raise ValueError("Nenhum arquivo enviado")
        
        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Arquivo muito grande (limite: {MAX_FILE_SIZE_MB}MB)")
        
        if file.name.endswith('.pdf'):
            if "extract_text" in str(PDF_READER._name_):
                return PDF_READER(file)
            else:
                reader = PDF_READER(file)
                return "\n".join([page.extract_text() or "" for page in reader.pages])
        elif file.name.endswith('.docx'):
            return docx2txt.process(file)
        else:
            raise ValueError("Formato não suportado")
    except Exception as e:
        raise ValueError(f"Erro ao ler arquivo: {str(e)}")

def main():
    st.set_page_config(
        page_title="Analisador Contratual Profissional",
        page_icon="📑",
        layout="wide"
    )
    
    st.title("🔍 Sistema de Análise Contratual IA")
    st.markdown("""
    *Análise profissional de conformidade entre contratos base e propostas*  
    Identifica riscos, inconsistências e oportunidades em documentos legais
    """)
    
    with st.expander("📤 UPLOAD DE DOCUMENTOS", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            contrato_base = st.file_uploader(
                "CONTRATO BASE (PDF/DOCX)",
                type=["pdf", "docx"],
                key="contrato"
            )
        with col2:
            propostas = st.file_uploader(
                "PROPOSTAS (PDF/DOCX)",
                type=["pdf", "docx"],
                accept_multiple_files=True,
                key="propostas"
            )
    
    if st.button("🚀 EXECUTAR ANÁLISE", type="primary") and contrato_base and propostas:
        try:
            with st.spinner("🔍 Processando contrato base..."):
                texto_base = ler_arquivo(contrato_base)
                if not texto_base:
                    raise ValueError("Contrato base vazio ou inválido")
            
            resultados = []
            for proposta in propostas:
                try:
                    with st.spinner(f"📊 Analisando {proposta.name}..."):
                        texto_proposta = ler_arquivo(proposta)
                        analisador = AnalisadorContratos()
                        
                        if not analisador.servicos:
                            raise ValueError("Nenhum serviço de IA disponível")
                        
                        prompt = f"""
                        [ANÁLISE CONTRATUAL PROFISSIONAL]
                        CONTEXTO: Você é um especialista em contratos de mineração/energia.
                        
                        CONTRATO BASE:
                        {texto_base[:30000]}
                        
                        PROPOSTA:
                        {texto_proposta[:30000]}
                        
                        SAÍDA ESPERADA:
                        1. Conformidade geral (0-100%)
                        2. Itens críticos atendidos/não atendidos
                        3. Riscos jurídicos identificados
                        4. Recomendações específicas
                        """
                        
                        # Tenta OpenAI primeiro
                        if "openai" in analisador.servicos:
                            try:
                                response = analisador.servicos["openai"].chat.completions.create(
                                    model="gpt-4-turbo-preview",
                                    messages=[{"role": "user", "content": prompt}],
                                    temperature=0.2,
                                    max_tokens=3000
                                )
                                analise = response.choices[0].message.content
                                resultados.append((proposta.name, analise, "GPT-4 Turbo"))
                                continue
                            except Exception as e:
                                st.warning(f"OpenAI falhou: {str(e)}")
                        
                        # Fallback para Gemini
                        if "gemini" in analisador.servicos:
                            try:
                                model = genai.GenerativeModel('gemini-1.5-pro-latest')
                                response = model.generate_content(prompt)
                                analise = response.text
                                resultados.append((proposta.name, analise, "Gemini 1.5 Pro"))
                                continue
                            except Exception as e:
                                st.warning(f"Gemini falhou: {str(e)}")
                        
                        raise ValueError("Todos os serviços de IA falharam")
                
                except Exception as e:
                    st.error(f"❌ Falha na análise de {proposta.name}: {str(e)}")
                    resultados.append((proposta.name, f"Erro: {str(e)}", "Falha"))
            
            # Exibe resultados
            st.success("✅ ANÁLISE CONCLUÍDA!")
            for nome, analise, modelo in resultados:
                with st.expander(f"📝 {nome} ({modelo})", expanded=False):
                    st.markdown(analise)
                    
                    # Geração de PDF
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", size=10)
                    pdf.multi_cell(0, 8, analise)
                    pdf_bytes = pdf.output(dest="S").encode("latin1")
                    
                    st.download_button(
                        "⬇️ BAIXAR RELATÓRIO",
                        data=pdf_bytes,
                        file_name=f"ANALISE_{nome[:50]}.pdf",
                        mime="application/pdf"
                    )
        
        except Exception as e:
            st.error(f"❌ ERRO CRÍTICO: {str(e)}")
            with st.expander("Detalhes técnicos"):
                st.exception(e)

if _name_ == "_main_":
    main()
