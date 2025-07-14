
# Auto-instalação de pacotes
import subprocess
import sys

def instalar(pacote):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pacote])

for pacote in ["streamlit", "pandas", "openpyxl", "rapidfuzz"]:
    try:
        __import__(pacote)
    except ImportError:
        instalar(pacote)

import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
from openpyxl import Workbook
from io import BytesIO

# Login fixo
USUARIO = "MF_Pricing"
SENHA = "Pricing"

def limpar_texto(texto):
    return ''.join(e for e in str(texto).lower() if e.isalnum() or e.isspace())

def similaridade_combinada(modelo, lista_modelos):
    modelo = limpar_texto(modelo)
    lista_limpa = [limpar_texto(x) for x in lista_modelos]
    scores = [
        0.3 * fuzz.token_sort_ratio(modelo, ref) +
        0.5 * fuzz.ratio(modelo, ref) +
        0.2 * fuzz.partial_ratio(modelo, ref)
        for ref in lista_limpa
    ]
    idx_melhor = scores.index(max(scores))
    return idx_melhor, max(scores)

@st.cache_data
def carregar_base_atg():
    return pd.read_excel("baseatg.xlsx")

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Login")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if usuario == USUARIO and senha == SENHA:
            st.session_state["autenticado"] = True
            st.success("Login bem-sucedido! ✅")
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha inválidos.")
    st.stop()

# --- APP PRINCIPAL ---
st.title("Preenchimento por Similaridade - Fipe, Montadora e Categoria")
tab1, tab2 = st.tabs(["Rotina 1", "Rotina 2 (Base ATG)"])

with tab1:
    st.header("Rotina 1")
    with st.expander("Instruções - Rotina 1", expanded=True):
        st.markdown("""
        **1.** Insira uma base Excel com as colunas:
        - `Veiculo`
        - `Fipe_Ano`
        - `Montadora_Familia`
        - `Categoria`

        **2.** A base deve conter veículos preenchidos (com Fipe_Ano) e veículos a preencher (com Fipe_Ano em branco).

        **3.** Clique em **Processar dados** para preencher.

        **4.** Clique em **Download Resultado** para baixar a base preenchida.
        """)

    arquivo = st.file_uploader("Escolha o arquivo Excel (.xlsx)", type="xlsx")
    if arquivo:
        df = pd.read_excel(arquivo)
        if "Veiculo" not in df.columns:
            st.error("A planilha deve conter a coluna 'Veiculo'.")
        else:
            df["Modelo_Limpo"] = df["Veiculo"].apply(limpar_texto)
            com_fipe = df[df["Fipe_Ano"].notna()].copy()
            sem_fipe = df[df["Fipe_Ano"].isna()].copy()

            if st.button("Processar dados"):
                resultados = []
                total = len(sem_fipe)
                progress_bar = st.progress(0)
                for i, modelo in enumerate(sem_fipe["Modelo_Limpo"]):
                    idx, score = similaridade_combinada(modelo, com_fipe["Modelo_Limpo"])
                    linha = com_fipe.iloc[idx]
                    if "blind" in modelo:
                        montadora = f"{linha['Montadora_Familia']} (blindado)"
                        categoria = f"BLINDADO {linha['Categoria']}"
                    else:
                        montadora = linha["Montadora_Familia"]
                        categoria = linha["Categoria"]
                    resultados.append({
                        "Veiculo": modelo,
                        "Montadora_Familia": montadora,
                        "Modelo_Base": linha["Veiculo"],
                        "Fipe_Ano": linha["Fipe_Ano"],
                        "Categoria": categoria,
                        "Percentual_Associacao": round(score, 2)
                    })
                    progress_bar.progress((i + 1) / total)

                df_result = pd.concat([com_fipe, pd.DataFrame(resultados)], ignore_index=True)
                st.dataframe(df_result)

                buffer = BytesIO()
                df_result.to_excel(buffer, index=False)
                st.download_button(
                    label="Download Resultado",
                    data=buffer.getvalue(),
                    file_name=f"Resultado_Montadora_{pd.Timestamp.today().date()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

with tab2:
    st.header("Rotina 2 - Base ATG")
    with st.expander("Instruções - Rotina 2", expanded=True):
        st.markdown("""
        **1.** Você pode inserir um arquivo Excel com uma coluna chamada `Veiculo`,  
        **ou** colar os nomes dos veículos (um por linha) no campo abaixo.

        **2.** O modelo irá comparar com a base `baseatg.xlsx` incluída no repositório.

        **3.** Clique em **Preencher com Base ATG** e depois em **Download Resultado ATG**.
        """)

    base_atg = carregar_base_atg()
    base_atg["Modelo_Limpo"] = base_atg["Veiculo"].apply(limpar_texto)

    arquivo_atg = st.file_uploader("Escolha o arquivo com as descrições (.xlsx)", type="xlsx", key="atgfile")
    texto_veiculos = st.text_area("Ou cole os veículos (um por linha):")

    if st.button("Preencher com Base ATG"):
        entrada = None
        if arquivo_atg:
            entrada = pd.read_excel(arquivo_atg)
        elif texto_veiculos.strip():
            entrada = pd.DataFrame({"Veiculo": texto_veiculos.strip().split("\n")})

        if entrada is not None and "Veiculo" in entrada.columns:
            entrada["Modelo_Limpo"] = entrada["Veiculo"].apply(limpar_texto)
            resultados = []
            total = len(entrada)
            progress_bar = st.progress(0)
            for i, modelo in enumerate(entrada["Modelo_Limpo"]):
                idx, score = similaridade_combinada(modelo, base_atg["Modelo_Limpo"])
                linha = base_atg.iloc[idx]
                resultados.append({
                    "Veiculo_Imputado": linha["Veiculo"],
                    "Fipe": linha["Fipe"],
                    "Ano": linha["Ano"],
                    "Montadora_Familia": linha["Montadora_Familia"],
                    "Percentual_Associacao": round(score, 2)
                })
                progress_bar.progress((i + 1) / total)

            df_result = entrada.join(pd.DataFrame(resultados))
            st.dataframe(df_result)

            buffer = BytesIO()
            df_result.to_excel(buffer, index=False)
            st.download_button(
                label="Download Resultado ATG",
                data=buffer.getvalue(),
                file_name=f"Resultado_Base_ATG_{pd.Timestamp.today().date()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error("A planilha deve conter a coluna 'Veiculo'.")
