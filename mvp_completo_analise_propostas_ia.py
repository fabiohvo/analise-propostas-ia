import streamlit as st
import sqlite3
from datetime import datetime
import os
import time
import sys
import subprocess
from typing import Tuple, Optional

# --- CONFIGURAÇÃO DE AMBIENTE ROBUSTA ---
def install_package(package_spec: str):
    """Instala pacotes com tratamento avançado de erros"""
    package_name = package_spec.split('>=')[0]
    try:
        # Tenta importar primeiro para verificar se já está instalado
        import importlib
        importlib.import_module(package_name)
    except ImportError:
        try:
            # Instalação silenciosa
            subprocess.run(
                [sys.executable, "-m", "pip", "install", package_spec],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            st.warning(f"Falha ao instalar {package_spec}. Tentando versão mínima...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", package_name],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            except subprocess.CalledProcessError:
                st.error(f"Não foi possível instalar {package_name}")
                return False
    return True

# Lista de pacotes com fallbacks
PACKAGES = [
    "PyPDF2>=3.0.0,<4.0.0",  # Restringindo versão para evitar incompatibilidades
    "docx2txt>=0.9",
    "openai>=1.12.0",
    "google-generativeai>=0.3.0",
    "fpdf2>=2.8.3",
    "python-dotenv>=1.0.0",
    "tiktoken>=0.5.1;python_version<'3.11'",  # Instala apenas para Python <3.11
    "pypdf>=3.0.0"  # Fallback para PyPDF2
]

# Instalação controlada
for package in PACKAGES:
    success = install_package(package)
    if not success and "PyPDF2" in package:
        st.warning("Usando pypdf como fallback para PyPDF2")

# --- IMPORTACOES COM FALLBACKS ---
try:
    # Tenta primeiro com PyPDF2
    from PyPDF2 import PdfReader
    try:
        from PyPDF2 import PdfException
    except ImportError:
        class PdfException(Exception): pass  # Fallback para PdfException
except ImportError:
    try:
        # Fallback para pypdf
        from pypdf import PdfReader, PdfException
        st.info("Usando pypdf em vez de PyPDF2")
    except ImportError as e:
        st.error("Nenhuma biblioteca PDF disponível!")
        st.stop()

try:
    import docx2txt
    from openai import OpenAI
    import google.generativeai as genai
    from fpdf import FPDF
    from dotenv import load_dotenv
    
    # Tenta importar tiktoken apenas se Python < 3.11
    if sys.version_info < (3, 11):
        try:
            import tiktoken
        except ImportError:
            st.warning("tiktoken não disponível - usando contagem simples de tokens")
            tiktoken = None
    else:
        tiktoken = None
        st.info("Python 3.11+ detectado - tiktoken não é necessário")
except ImportError as e:
    st.error(f"FALHA NAS IMPORTAÇÕES: {str(e)}")
    st.stop()

# --- CONSTANTES ---
MAX_FILE_SIZE_MB = 25
MAX_TOKENS = 100000
TIMEOUT_ANALISE = 300  # 5 minutos

# --- CLASSE PRINCIPAL ---
class AnalisadorContratos:
    def _init_(self):
        self.servicos = self._iniciar_servicos()
        self._setup_tokenizer()
    
    def _iniciar_servicos(self):
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
            raise Exception("Nenhum serviço de IA disponível")
        return servicos
    
    def _setup_tokenizer(self):
        """Configura tokenizador com fallback"""
        self.tokenizer = None
        if tiktoken:
            try:
                self.tokenizer = tiktoken.get_encoding("cl100k_base")
            except:
                pass
    
    def contar_tokens(self, texto: str) -> int:
        """Conta tokens com fallback para len() se tiktoken falhar"""
        if self.tokenizer:
            return len(self.tokenizer.encode(texto))
        return len(texto.split())  # Fallback aproximado

# ... [Restante do código permanece idêntico ao anterior] ...

if _name_ == "_main_":
    try:
        main()
    except Exception as e:
        st.error("ERRO INESPERADO NO SISTEMA")
        with st.expander("Detalhes técnicos (para suporte)"):
            st.exception(e)
        st.info("Por favor, tente novamente ou contate o administrador")
