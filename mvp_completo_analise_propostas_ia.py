import streamlit as st
from PyPDF2 import PdfReader
import docx2txt
from openai import OpenAI
from fpdf import FPDF
import sqlite3
from datetime import datetime
import os
from dotenv import load_dotenv

# Configuração inicial
st.set_page_config(page_title="Analisador de Propostas com IA", page_icon="📄")

# Carregar variáveis de ambiente (para desenvolvimento local)
load_dotenv()

# Inicialização da OpenAI com tratamento robusto
try:
    openai_api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("openai", {}).get("api_key", "")
    
    if not openai_api_key:
        st.error("🔒 Chave API da OpenAI não configurada")
        st.info("Por favor, configure a chave API nas Secrets do Streamlit ou no arquivo .env")
        st.stop()
    
    client = OpenAI(api_key=openai_api_key)
    
    # Verificação opcional dos modelos disponíveis
    try:
        available_models = [model.id for model in client.models.list().data]
        st.session_state.available_models = available_models
    except:
        st.session_state.available_models = []
        
except Exception as e:
    st.error(f"Erro na configuração da API OpenAI: {str(e)}")
    st.stop()

# Inicializar banco de dados SQLite
def init_db():
    try:
        conn = sqlite3.connect("historico.db")
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS analises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposta_nome TEXT,
                score TEXT,
                data TEXT,
                parecer TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao inicializar banco de dados: {str(e)}")

init_db()

# Funções auxiliares com tratamento de erros
def read_pdf(file):
    try:
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text
        return text
    except Exception as e:
        st.error(f"Erro ao ler PDF: {str(e)}")
        return ""

def read_docx(file):
    try:
        return docx2txt.process(file)
    except Exception as e:
        st.error(f"Erro ao ler DOCX: {str(e)}")
        return ""

def read_file(file):
    if not file:
        return ""
    
    try:
        if file.name.endswith(".pdf"):
            return read_pdf(file)
        elif file.name.endswith(".docx"):
            return read_docx(file)
        else:
            st.warning(f"Formato de arquivo não suportado: {file.name}")
            return ""
    except Exception as e:
        st.error(f"Erro ao processar arquivo: {str(e)}")
        return ""

def salvar_historico(nome, score, parecer):
    try:
        conn = sqlite3.connect("historico.db")
        c = conn.cursor()
        c.execute("INSERT INTO analises (proposta_nome, score, data, parecer) VALUES (?, ?, ?, ?)",
                (nome, score, datetime.now().strftime("%Y-%m-%d %H:%M"), parecer))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao salvar no histórico: {str(e)}")

class PDFReport(FPDF):
    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "Relatório de Análise de Proposta", 0, 1, "C")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", 0, 0, "C")

    def add_analysis(self, proposta_nome, conteudo):
        self.set_font("Arial", "B", 11)
        self.multi_cell(0, 10, f"📄 Proposta: {proposta_nome}", 0)
        self.set_font("Arial", "", 10)
        self.multi_cell(0, 8, conteudo)
        self.ln(5)

# Interface Streamlit
st.title("📄 Analisador de Propostas com IA")
st.write("Compare múltiplas propostas com um edital base e gere relatórios automáticos.")

# Seção de upload de arquivos
with st.expander("📤 Upload de Arquivos", expanded=True):
    edital_file = st.file_uploader("Edital Base (PDF ou DOCX)", type=["pdf", "docx"], key="edital")
    propostas_files = st.file_uploader("Propostas para Análise", type=["pdf", "docx"], 
                                     accept_multiple_files=True, key="propostas")

# Modelo seleção (se houver modelos disponíveis)
if hasattr(st.session_state, 'available_models') and st.session_state.available_models:
    modelo_selecionado = st.selectbox(
        "Selecione o modelo de IA:",
        options=st.session_state.available_models,
        index=0
    )
else:
    modelo_selecionado = "gpt-4-turbo-preview"  # Fallback

if st.button("🔍 Analisar Propostas", type="primary") and edital_file and propostas_files:
    with st.spinner("Analisando propostas com IA..."):
        edital_text = read_file(edital_file)
        
        if not edital_text:
            st.error("Não foi possível ler o conteúdo do edital")
            st.stop()
        
        for proposta_file in propostas_files:
            try:
                proposta_text = read_file(proposta_file)
                
                if not proposta_text:
                    st.warning(f"Não foi possível ler o conteúdo da proposta: {proposta_file.name}")
                    continue
                
                prompt = f"""
                Você é um avaliador técnico de propostas em licitações. Compare a proposta abaixo com o edital base.
                Encontre itens não atendidos, promessas vagas, omissões e gere um parecer final com score de conformidade.

                EDITAL BASE:
                {edital_text}

                PROPOSTA RECEBIDA ({proposta_file.name}):
                {proposta_text}

                Responda no formato:
                - Itens atendidos
                - Itens não atendidos ou vagos
                - Score geral (0 a 100%)
                - Recomendações
                """

                try:
                    response = client.chat.completions.create(
                        model=modelo_selecionado,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.4,
                    )
                    resultado = response.choices[0].message.content
                    
                    with st.container():
                        st.subheader(f"📋 Resultado: {proposta_file.name}")
                        st.markdown(resultado)
                        
                        # Gerar PDF
                        try:
                            report = PDFReport()
                            report.add_page()
                            report.add_analysis(proposta_file.name, resultado)
                            pdf_file_name = f"relatorio_{proposta_file.name.replace(' ', '_')}.pdf"
                            report.output(pdf_file_name)
                            
                            with open(pdf_file_name, "rb") as f:
                                st.download_button(
                                    label="📥 Baixar Relatório",
                                    data=f,
                                    file_name=pdf_file_name,
                                    mime="application/pdf"
                                )
                        except Exception as e:
                            st.error(f"Erro ao gerar PDF: {str(e)}")
                        
                        # Extrair score e salvar histórico
                        score_linha = next((l for l in resultado.splitlines() if "Score geral" in l), "Score geral: N/A")
                        salvar_historico(proposta_file.name, score_linha, resultado)
                        
                except Exception as e:
                    st.error(f"Erro na API OpenAI ao analisar {proposta_file.name}: {str(e)}")
                    continue
                    
            except Exception as e:
                st.error(f"Erro ao processar {proposta_file.name}: {str(e)}")
                continue

# Seção de histórico
st.sidebar.header("📊 Histórico de Análises")
try:
    conn = sqlite3.connect("historico.db")
    c = conn.cursor()
    c.execute("SELECT proposta_nome, score, data FROM analises ORDER BY data DESC LIMIT 10")
    historico = c.fetchall()
    conn.close()
    
    if historico:
        for nome, score, data in historico:
            st.sidebar.markdown(f"*{nome}*")
            st.sidebar.caption(f"{score} - {data}")
            st.sidebar.divider()
    else:
        st.sidebar.info("Nenhuma análise registrada ainda")
except Exception as e:
    st.sidebar.error(f"Erro ao carregar histórico: {str(e)}")

# Rodapé informativo
st.divider()
st.caption("""
    ℹ️ Aplicativo desenvolvido para análise técnica de propostas. 
    Os resultados são gerados por IA e devem ser validados por especialistas.
""")
