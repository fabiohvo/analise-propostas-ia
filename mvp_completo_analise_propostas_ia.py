import streamlit as st
import sqlite3
from datetime import datetime
import os
import time
import sys
import subprocess

# --- VERIFICAÇÃO DE DEPENDÊNCIAS CORRIGIDA ---
def install_package(package_name: str):
    """Instala pacotes faltantes de forma robusta"""
    try:
        # Usando importlib como alternativa mais segura
        import importlib
        importlib.import_module(package_name.split('>=')[0])
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package_name.split('>=')[0]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

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

# Instala dependências faltantes
for package in REQUIRED_PACKAGES:
    try:
        install_package(package)
    except Exception as e:
        st.warning(f"Erro ao instalar {package}: {str(e)}")

# --- IMPORTACOES PÓS-INSTALAÇÃO ---
try:
    from PyPDF2 import PdfReader, PdfException
    import docx2txt
    from openai import OpenAI
    import google.generativeai as genai
    from fpdf import FPDF
    from dotenv import load_dotenv
    import tiktoken
except Exception as e:
    st.error(f"FALHA CRÍTICA NAS IMPORTAÇÕES: {str(e)}")
    st.stop()

# --- CONSTANTES ---
MAX_FILE_SIZE_MB = 25
MAX_CONTEXT_TOKENS = 120000
TIMEOUT_ANALISE = 300  # 5 minutos

class AnalisadorContratos:
    """Classe principal para análise de contratos complexos"""
    
    def _init_(self):
        self._inicializar_servicos()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
    def _inicializar_servicos(self):
        """Configura os serviços de IA com fallback"""
        self.servicos = {}
        load_dotenv()
        
        # OpenAI
        try:
            openai_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("openai", {}).get("api_key")
            if openai_key:
                self.servicos["openai"] = OpenAI(api_key=openai_key, timeout=TIMEOUT_ANALISE)
        except Exception as e:
            st.warning(f"OpenAI não disponível: {str(e)}")
        
        # Gemini
        try:
            gemini_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("gemini", {}).get("api_key")
            if gemini_key:
                genai.configure(api_key=gemini_key)
                self.servicos["gemini"] = genai
        except Exception as e:
            st.warning(f"Gemini não disponível: {str(e)}")
        
        if not self.servicos:
            raise Exception("Nenhum serviço de IA disponível")

# ... (o restante do código permanece EXATAMENTE como no exemplo anterior) ...

if _name_ == "_main_":
    try:
        main()
    except Exception as e:
        st.error(f"ERRO INESPERADO: {str(e)}")
        with st.expander("Detalhes técnicos (para administradores)"):
            st.exception(e)
