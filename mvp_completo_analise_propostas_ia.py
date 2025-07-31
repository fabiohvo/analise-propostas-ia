"""
ANALISADOR CONTRATUAL VALE - v1.0.2
Correção definitiva do erro 'bytearray' object has no attribute 'encode'
"""

import streamlit as st
from pypdf import PdfReader
import docx2txt
from openai import OpenAI
import google.generativeai as genai
from fpdf import FPDF
from dotenv import load_dotenv
import os
import time

# ================= CONFIGURAÇÃO =================
st.set_page_config(
    page_title="Analisador Contratual Vale 1.0.2",
    page_icon="📑",
    layout="wide"
)

MAX_FILE_SIZE_MB = 25
TIMEOUT_API = 300

@st.cache_resource
def init_services():
    """Inicializa conexões com APIs"""
    services = {}
    load_dotenv()
    
    if os.getenv("OPENAI_API_KEY") or st.secrets.get("openai", {}).get("api_key"):
        services["openai"] = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY") or st.secrets["openai"]["api_key"],
            timeout=TIMEOUT_API
        )
    
    if os.getenv("GEMINI_API_KEY") or st.secrets.get("gemini", {}).get("api_key"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY") or st.secrets["gemini"]["api_key"])
        services["gemini"] = genai
    
    return services

def ler_arquivo(file):
    """Lê PDF/DOCX com tratamento de erros"""
    try:
        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Arquivo muito grande (limite: {MAX_FILE_SIZE_MB}MB)")
        
        if file.name.endswith('.pdf'):
            reader = PdfReader(file)
            return "\n".join([page.extract_text() or "" for page in reader.pages[:50]])
        elif file.name.endswith('.docx'):
            return docx2txt.process(file)[:500000]
        raise ValueError("Formato inválido (use PDF ou DOCX)")
    except Exception as e:
        raise ValueError(f"Erro ao ler {file.name}: {str(e)}")

def gerar_pdf(conteudo):
    """Gera PDF de forma compatível com todas versões do fpdf2"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 8, conteudo)
    
    # Solução universal para bytearray/string
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        return pdf_output.encode('latin1')
    return pdf_output  # Já é bytes

def analisar_contrato(contrato_base, proposta, nome_proposta):
    """Lógica de análise contratual"""
    services = init_services()
    
    prompt = f"""
    [ANÁLISE CONTRATUAL VALE]
    Compare:
    - CONTRATO BASE: {contrato_base[:30000]}
    - PROPOSTA ({nome_proposta}): {proposta[:30000]}
    
    Entregue:
    1. Conformidade (0-100%)
    2. Itens críticos faltantes
    3. Recomendações específicas
    """
    
    if "openai" in services:
        try:
            response = services["openai"].chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            return response.choices[0].message.content
        except Exception as e:
            st.warning(f"OpenAI falhou: {str(e)}")
    
    if "gemini" in services:
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            st.warning(f"Gemini falhou: {str(e)}")
    
    raise Exception("Todos os serviços de IA falharam (verifique créditos)")

def main():
    st.title("📑 Analisador Contratual Vale 1.0.2")
    
    # Upload de documentos
    contrato_base = st.file_uploader("Contrato Base Vale", type=["pdf", "docx"])
    propostas = st.file_uploader("Propostas Comerciais", type=["pdf", "docx"], accept_multiple_files=True)
    
    if st.button("Executar Análise", type="primary") and contrato_base and propostas:
        try:
            with st.spinner("Processando contrato base..."):
                texto_base = ler_arquivo(contrato_base)
            
            resultados = []
            for proposta in propostas:
                try:
                    with st.spinner(f"Analisando {proposta.name}..."):
                        texto_proposta = ler_arquivo(proposta)
                        analise = analisar_contrato(texto_base, texto_proposta, proposta.name)
                        
                        with st.expander(f"Resultado: {proposta.name}", expanded=False):
                            st.markdown(analise)
                            
                            # Geração de PDF corrigida
                            pdf_bytes = gerar_pdf(analise)
                            st.download_button(
                                "📥 Baixar Relatório",
                                data=pdf_bytes,
                                file_name=f"Vale_Analise_{proposta.name[:45]}.pdf",
                                mime="application/pdf"
                            )
                    
                    resultados.append(proposta.name)
                except Exception as e:
                    st.error(f"Falha na proposta {proposta.name}: {str(e)}")
                    continue
            
            st.success(f"✅ Análise concluída para {len(resultados)} proposta(s)")
        
        except Exception as e:
            st.error(f"Erro crítico: {str(e)}")

if __name__ == "__main__":
    main()
