"""Frontend (lente) da Prosa · ponto de entrada do Streamlit.

Esta aplicação NÃO contém o bot: ela só conversa com a API (services/api_client.py). Aqui fica apenas a navegação e
o tema; cada página (pages/) segue o caminho  página → componentes → services/api_client.py → API.

Executar (dentro de frontend/):  streamlit run app.py
"""
import streamlit as st

from components.theme import apply_theme

st.set_page_config(page_title="Duda · Prosa Bot", page_icon="🐾", layout="wide", initial_sidebar_state="expanded")
apply_theme()

navigation = st.navigation([
    st.Page("pages/chat.py", title="Chat com a Duda", icon="💬", default=True),
    st.Page("pages/metricas.py", title="Métricas", icon="📊"),
])
navigation.run()
