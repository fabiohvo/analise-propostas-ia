"""
ANALISADOR CONTRATUAL AVANÇADO - v2.0.0
Comparação detalhada entre contrato base e múltiplas propostas
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
import pandas as pd
from datetime import datetime

# ================= CONFIGURAÇÃO =================
st.set_page_config(
    page_title="Analisador Contratual Avançado 2.0.0",
    page_icon="📊",
    layout="wide"
)

MAX_FILE_SIZE_MB = 25
TIMEOUT_API = 300
MAX_TOKENS = 30000  # Limite para processamento

@st.cache_resource
def init_services():
    """Inicializa conexões com APIs"""
    services = {}
    load_dotenv()
    
    # Conexão OpenAI (ajustada para versão mais recente)
    openai_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
    if openai_key:
        services["openai"] = OpenAI(
            api_key=openai_key,
            timeout=TIMEOUT_API
        )
    
    # Conexão Gemini (mantida igual)
    gemini_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
    if gemini_key:
        genai.configure(api_key=gemini_key)
        services["gemini"] = genai
    
    return services

def ler_arquivo(file):
    """Lê PDF/DOCX com tratamento de erros e extração otimizada"""
    try:
        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Arquivo muito grande (limite: {MAX_FILE_SIZE_MB}MB)")
        
        if file.name.endswith('.pdf'):
            reader = PdfReader(file)
            text = []
            for page in reader.pages[:50]:  # Limita a 50 páginas
                page_text = page.extract_text() or ""
                # Remove headers/footers comuns
                lines = [line for line in page_text.split('\n') 
                        if not line.strip().isdigit()  # Remove números de página
                        and not line.lower().startswith('confidential')]
                text.append('\n'.join(lines))
            return "\n".join(text)[:MAX_TOKENS]
        
        elif file.name.endswith('.docx'):
            text = docx2txt.process(file)
            # Filtra linhas indesejadas
            lines = [line for line in text.split('\n') 
                    if not line.strip().isdigit()
                    and not line.lower().startswith('confidential')]
            return '\n'.join(lines)[:MAX_TOKENS]
        
        raise ValueError("Formato inválido (use PDF ou DOCX)")
    except Exception as e:
        raise ValueError(f"Erro ao ler {file.name}: {str(e)}")

def gerar_pdf(conteudo, nome_arquivo):
    """Gera PDF com formatação melhorada"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    
    # Adiciona cabeçalho
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"Relatório de Análise Contratual", ln=1, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, f"Arquivo: {nome_arquivo}", ln=1)
    pdf.cell(0, 10, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=1)
    pdf.ln(10)
    
    # Conteúdo formatado
    pdf.multi_cell(0, 8, conteudo)
    
    pdf_output = pdf.output(dest='S')
    return pdf_output.encode('latin1') if isinstance(pdf_output, str) else pdf_output

def analisar_contrato(contrato_base, proposta, nome_proposta):
    """Lógica de análise contratual avançada"""
    services = init_services()
    
    prompt = f"""
    [ANÁLISE CONTRATUAL DETALHADA]
    
    ### CONTEXTO:
    Você é um especialista em análise contratual com 20 anos de experiência. Compare o contrato base com a proposta comercial, identificando:
    
    ### DADOS DE ENTRADA:
    - CONTRATO BASE (VALE): {contrato_base[:MAX_TOKENS]}
    - PROPOSTA ({nome_proposta}): {proposta[:MAX_TOKENS]}
    
    ### FORMATO DE SAÍDA:
    
    1. RESUMO EXECUTIVO
    - Conformidade geral (0-100%)
    - Principais pontos de atenção
    - Recomendação (Aprovar/Reprovar/Revisar)
    
    2. ANÁLISE POR CLÁUSULA
    - Tabela comparativa com:
      * Cláusula
      * Status (Conforme/Divergente/Não mencionado)
      * Impacto (Alto/Médio/Baixo)
      * Comentários
    
    3. ITENS CRÍTICOS
    - Lista dos 5 itens mais críticos com explicação
    
    4. RECOMENDAÇÕES
    - Ações específicas para alinhamento
    
    ### REGRAS:
    - Seja objetivo e técnico
    - Priorize cláusulas financeiras e de responsabilidade
    - Destaque prazos e penalidades divergentes
    """
    
    if "openai" in services:
        try:
            response = services["openai"].chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1  # Menor temperatura para mais objetividade
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

def extrair_metricas(analise):
    """Extrai métricas do relatório para dashboard"""
    try:
        metricas = {
            "Conformidade": 0,
            "Pontos Criticos": 0,
            "Recomendacao": "Indefinido"
        }
        
        # Extrai conformidade (ex: "Conformidade geral: 85%")
        if "Conformidade geral:" in analise:
            start = analise.find("Conformidade geral:") + len("Conformidade geral:")
            end = analise.find("%", start)
            if end != -1:
                metricas["Conformidade"] = int(analise[start:end].strip())
        
        # Conta itens críticos
        metricas["Pontos Criticos"] = analise.count("🔴")  # Usando emoji como marcador
        
        # Extrai recomendação
        for termo in ["Aprovar", "Reprovar", "Revisar"]:
            if termo in analise:
                metricas["Recomendacao"] = termo
                break
                
        return metricas
    except:
        return None

def main():
    st.title("📊 Analisador Contratual Avançado 2.0.0")
    st.markdown("Compare um contrato base com múltiplas propostas comerciais")
    
    # Upload de documentos
    col1, col2 = st.columns(2)
    with col1:
        contrato_base = st.file_uploader("Contrato Base", type=["pdf", "docx"], key="base")
    with col2:
        propostas = st.file_uploader("Propostas Comerciais", type=["pdf", "docx"], 
                                   accept_multiple_files=True, key="propostas")
    
    if st.button("Executar Análise Comparativa", type="primary") and contrato_base and propostas:
        try:
            with st.spinner("Processando contrato base..."):
                texto_base = ler_arquivo(contrato_base)
            
            # Área para resultados
            resultados = []
            metricas_gerais = []
            
            tab_view, tab_dash = st.tabs(["Relatórios", "Dashboard Comparativo"])
            
            for proposta in propostas:
                try:
                    with st.spinner(f"Analisando {proposta.name}..."):
                        texto_proposta = ler_arquivo(proposta)
                        analise = analisar_contrato(texto_base, texto_proposta, proposta.name)
                        metricas = extrair_metricas(analise)
                        
                        with tab_view:
                            with st.expander(f"📌 {proposta.name}", expanded=False):
                                st.markdown(analise)
                                
                                # Geração de PDF
                                pdf_bytes = gerar_pdf(analise, proposta.name)
                                st.download_button(
                                    "📥 Baixar Relatório Completo",
                                    data=pdf_bytes,
                                    file_name=f"Analise_{proposta.name[:40]}.pdf",
                                    mime="application/pdf",
                                    key=f"pdf_{proposta.name}"
                                )
                        
                        if metricas:
                            metricas["Proposta"] = proposta.name
                            metricas_gerais.append(metricas)
                            
                        resultados.append(proposta.name)
                except Exception as e:
                    st.error(f"Falha na proposta {proposta.name}: {str(e)}")
                    continue
            
            # Dashboard comparativo
            with tab_dash:
                if metricas_gerais:
                    df = pd.DataFrame(metricas_gerais)
                    df.set_index("Proposta", inplace=True)
                    
                    st.subheader("Visão Comparativa das Propostas")
                    
                    # Gráficos
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Melhor Conformidade", f"{df['Conformidade'].max()}%")
                    with col2:
                        st.metric("Mais Itens Críticos", df['Pontos Criticos'].max())
                    with col3:
                        st.metric("Propostas para Revisar", (df['Recomendacao'] == 'Revisar').sum())
                    
                    # Tabela detalhada
                    st.dataframe(df.style
                                .background_gradient(subset=['Conformidade'], cmap='RdYlGn'))
                    
                    # Gráfico de barras
                    st.bar_chart(df['Conformidade'])
            
            st.success(f"✅ Análise concluída para {len(resultados)} proposta(s)")
        
        except Exception as e:
            st.error(f"Erro crítico: {str(e)}")

if __name__ == "__main__":
    main()
