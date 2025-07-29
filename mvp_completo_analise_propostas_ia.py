
import streamlit as st
from PyPDF2 import PdfReader
import docx2txt
import openai
from fpdf import FPDF
import sqlite3
from datetime import datetime

# Configuração da OpenAI
openai.api_key = "SUA_API_AQUI"

# Inicializar banco de dados SQLite
def init_db():
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

init_db()

# Funções auxiliares
def read_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def read_docx(file):
    return docx2txt.process(file)

def read_file(file):
    if file.name.endswith(".pdf"):
        return read_pdf(file)
    elif file.name.endswith(".docx"):
        return read_docx(file)
    else:
        return ""

def salvar_historico(nome, score, parecer):
    conn = sqlite3.connect("historico.db")
    c = conn.cursor()
    c.execute("INSERT INTO analises (proposta_nome, score, data, parecer) VALUES (?, ?, ?, ?)",
              (nome, score, datetime.now().strftime("%Y-%m-%d %H:%M"), parecer))
    conn.commit()
    conn.close()

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
st.title("Analisador de Propostas com IA")
st.write("Compare múltiplas propostas com um edital base e gere relatórios automáticos.")

edital_file = st.file_uploader("📄 Upload do Edital (PDF ou DOCX)", type=["pdf", "docx"])
propostas_files = st.file_uploader("📄 Upload das Propostas", type=["pdf", "docx"], accept_multiple_files=True)

if st.button("🔍 Analisar Propostas") and edital_file and propostas_files:
    with st.spinner("Analisando propostas com IA..."):
        edital_text = read_file(edital_file)

        for proposta_file in propostas_files:
            proposta_text = read_file(proposta_file)

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

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
            )

            resultado = response['choices'][0]['message']['content']
            st.subheader(f"📋 Resultado da Análise: {proposta_file.name}")
            st.write(resultado)

            # Gerar e oferecer download do PDF
            report = PDFReport()
            report.add_page()
            report.add_analysis(proposta_file.name, resultado)
            pdf_file_name = f"relatorio_{proposta_file.name.replace(' ', '_')}.pdf"
            report.output(pdf_file_name)
            with open(pdf_file_name, "rb") as f:
                st.download_button("📥 Baixar Relatório em PDF", f, file_name=pdf_file_name)

            # Extrair score da resposta (tentando localizar na string)
            score_linha = next((l for l in resultado.splitlines() if "Score geral" in l), "Score geral: N/A")
            salvar_historico(proposta_file.name, score_linha, resultado)

# Exibir histórico salvo
st.sidebar.header("📊 Histórico de Análises")
conn = sqlite3.connect("historico.db")
c = conn.cursor()
c.execute("SELECT proposta_nome, score, data FROM analises ORDER BY data DESC")
historico = c.fetchall()
conn.close()

for nome, score, data in historico:
    st.sidebar.write(f"**{nome}**
- {score}
- {data}")
