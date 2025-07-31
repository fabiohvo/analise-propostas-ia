"""
ANALISADOR CONTRATUAL VALE - v1.0.0
Código base oficial para análise de propostas vs contratos padrão
Última atualização: dd/mm/aaaa
"""

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

# ================= CONFIGURAÇÃO INICIAL =================
st.set_page_config(
    page_title="Analisador Contratual Vale 1.0.0",
    page_icon="📑",
    layout="wide"
)

# ================= CONSTANTES =================
MAX_FILE_SIZE_MB = 25  # Limite por arquivo
TIMEOUT_API = 300      # 5 minutos para análise
MAX_PAGINAS_PDF = 50   # Limite de páginas para processamento

# ================= SERVIÇOS DE IA =================
@st.cache_resource
def init_services():
    """Inicializa conexões com APIs de IA"""
    services = {}
    load_dotenv()
    
    try:
        # Configura OpenAI
        if os.getenv("OPENAI_API_KEY") or st.secrets.get("openai", {}).get("api_key"):
            services["openai"] = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY") or st.secrets["openai"]["api_key"],
                timeout=TIMEOUT_API
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

# ================= FUNÇÕES PRINCIPAIS =================
def ler_arquivo(file):
    """Processa arquivos PDF/DOCX com tratamento robusto"""
    try:
        # Validação básica
        if not file:
            raise ValueError("Nenhum arquivo enviado")
            
        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Tamanho máximo excedido ({MAX_FILE_SIZE_MB}MB)")
        
        # Processamento por tipo
        if file.name.endswith('.pdf'):
            reader = PdfReader(file)
            return "\n".join([page.extract_text() or "" for page in reader.pages[:MAX_PAGINAS_PDF]])
            
        elif file.name.endswith('.docx'):
            return docx2txt.process(file)[:500000]  # Limite de caracteres
        
        raise ValueError("Formato inválido (use PDF ou DOCX)")
    except Exception as e:
        raise ValueError(f"Erro ao processar {file.name}: {str(e)}")

def gerar_relatorio_pdf(conteudo, nome_arquivo):
    """Gera PDF otimizado para contratos Vale"""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 8, conteudo)
        pdf_bytes = pdf.output(dest='S')
        return pdf_bytes.encode('latin1') if isinstance(pdf_bytes, str) else pdf_bytes
    except Exception as e:
        raise ValueError(f"Falha ao gerar PDF: {str(e)}")

# ================= ANÁLISE CONTRATUAL =================
def analisar_contrato_vale(contrato_base, proposta, nome_proposta):
    """Lógica principal de análise para contratos Vale"""
    services = init_services()
    
    prompt = f"""
    [ANÁLISE CONTRATUAL VALE - DIRETRIZES]
    1. Compare rigorosamente os termos:
       - Contrato Base: {contrato_base[:30000]}
       - Proposta: {proposta[:30000]}
    
    2. Entregue:
       - Conformidade (0-100%)
       - 3 riscos principais
       - Itens críticos ausentes
       - Recomendações específicas
    """
    
    # Tenta OpenAI primeiro
    if "openai" in services:
        try:
            response = services["openai"].chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                timeout=30
            )
            return response.choices[0].message.content
        except:
            pass
    
    # Fallback para Gemini
    if "gemini" in services:
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(prompt, request_options={"timeout": 30})
            return response.text
        except:
            pass
    
    raise Exception("Todos os serviços de IA falharam")

# ================= INTERFACE =================
def main():
    st.title("📑 Analisador Contratual Vale 1.0.0")
    st.caption("Sistema oficial para análise de conformidade de propostas")
    
    with st.form("form_analise"):
        # Upload de documentos
        contrato_base = st.file_uploader("CONTRATO BASE VALE", type=["pdf", "docx"])
        propostas = st.file_uploader("PROPOSTAS COMERCIAIS", type=["pdf", "docx"], accept_multiple_files=True)
        
        if st.form_submit_button("EXECUTAR ANÁLISE", type="primary"):
            if contrato_base and propostas:
                try:
                    with st.spinner("Processando contrato base..."):
                        texto_base = ler_arquivo(contrato_base)
                    
                    resultados = []
                    for proposta in propostas:
                        try:
                            with st.spinner(f"Analisando {proposta.name}..."):
                                texto_proposta = ler_arquivo(proposta)
                                analise = analisar_contrato_vale(texto_base, texto_proposta, proposta.name)
                                
                                with st.expander(f"RESULTADO: {proposta.name}", expanded=False):
                                    st.markdown(analise)
                                    
                                    # Geração de relatório
                                    pdf_bytes = gerar_relatorio_pdf(analise, proposta.name)
                                    st.download_button(
                                        "📥 BAIXAR RELATÓRIO",
                                        data=pdf_bytes,
                                        file_name=f"Vale_Analise_{proposta.name[:45]}.pdf",
                                        mime="application/pdf"
                                    )
                            
                            resultados.append(proposta.name)
                        except Exception as e:
                            st.error(f"Falha na proposta {proposta.name}: {str(e)}")
                            continue
                    
                    if resultados:
                        st.success(f"✅ Análise concluída para {len(resultados)} proposta(s)")
                
                except Exception as e:
                    st.error(f"ERRO SISTÊMICO: {str(e)}")
                    with st.expander("Detalhes técnicos"):
                        st.exception(e)

if __name__ == "__main__":
    main()
