import streamlit as st

from indigenas import render_indigenas

st.set_page_config(page_title="População e Crescimento Demográfico", layout="wide")

st.title("População e Crescimento Demográfico")
st.caption("Capitais analisadas: Curitiba, Porto Alegre, Belo Horizonte, Salvador e Florianópolis.")

render_indigenas()
