import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
from io import StringIO

# Configuração básica
st.set_page_config(
    page_title="Pipeline CAX",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Calculadora Pipeline CAX")
st.write("Versão de Debug - Carregando...")

# Função super simples para carregar dados
@st.cache_data(ttl=600)  # Cache por 10 minutos
def load_data_simple():
    """Carrega dados com fallback imediato"""
    try:
        # Tenta apenas uma URL simples
        url = "https://docs.google.com/spreadsheets/d/1L0nO-rchxshEufLANyH3aEz6hFulvpq1OMPUzTw76LM/export?format=csv&gid=0"
        
        # Timeout muito baixo para não travar
        response = requests.get(url, timeout=3)
        
        if response.status_code == 200 and len(response.text) > 50:
            df = pd.read_csv(StringIO(response.text))
            if not df.empty:
                st.success("✅ Dados carregados do Google Sheets")
                return df
    except:
        pass
    
    # Fallback imediato para dados de teste
    st.warning("⚠️ Usando dados de demonstração")
    return create_test_data()

def create_test_data():
    """Dados de teste simples"""
    data = {
        'dealname': ['Deal A', 'Deal B', 'Deal C', 'Deal D', 'Deal E'],
        'etapa': ['SAL', 'SQL', 'OPP', 'BC', 'ONB_AGEND'],
        'bdr': ['João', 'Maria', 'Pedro', 'Ana', 'Carlos'],
        'data_entrada': pd.date_range('2024-01-01', periods=5, freq='7D'),
        'data_prevista_onboarding': pd.date_range('2024-02-01', periods=5, freq='10D')
    }
    return pd.DataFrame(data)

# Carrega dados de forma simples
try:
    df = load_data_simple()
    st.write("✅ Aplicação carregada com sucesso!")
    
    # Métricas básicas
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Deals", len(df))
    with col2:
        st.metric("Etapas", df['etapa'].nunique())
    with col3:
        st.metric("BDRs", df['bdr'].nunique())
    
    # Tabela simples
    st.subheader("📋 Dados Carregados")
    st.dataframe(df, use_container_width=True)
    
    # Gráfico básico
    if not df.empty:
        fig = px.bar(
            df['etapa'].value_counts().reset_index(),
            x='etapa',
            y='count',
            title="Deals por Etapa"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Configurações mínimas no sidebar
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        if st.button("🔄 Recarregar"):
            st.cache_data.clear()
            st.rerun()
        
        st.divider()
        st.write("🕒 Última atualização:")
        st.write(datetime.now().strftime('%H:%M:%S'))
        
        # Status da conexão
        st.subheader("📡 Status")
        st.write("App: ✅ Funcionando")
        if 'Dados de demonstração' in st.session_state.get('data_source', ''):
            st.write("Dados: ⚠️ Demonstração")
        else:
            st.write("Dados: ✅ Google Sheets")
    
    st.success("🎉 App funcionando perfeitamente!")
    
except Exception as e:
    st.error(f"❌ Erro crítico: {str(e)}")
    st.code(str(e))
    
    # Informações de debug
    st.subheader("🔍 Debug Info")
    st.write(f"Python version: {st.__version__}")
    st.write(f"Time: {datetime.now()}")
    
    # App super básico como último recurso
    st.subheader("📊 App Básico")
    basic_data = pd.DataFrame({
        'Item': ['A', 'B', 'C'],
        'Valor': [10, 20, 30]
    })
    st.dataframe(basic_data)

# Footer sempre visível
st.divider()
st.caption("🚀 App minimalista para debug - Se você vê esta mensagem, o Streamlit está funcionando!")
