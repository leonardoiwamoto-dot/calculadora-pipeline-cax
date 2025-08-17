import streamlit as st
import pandas as pd
from datetime import datetime

# Configuração mínima
st.set_page_config(page_title="Pipeline CAX", page_icon="📊")

# Título
st.title("📊 Calculadora Pipeline CAX")
st.write("**Versão Simplificada - Funcionando!**")

# Dados hardcoded para garantir que funciona
data = {
    'Deal': ['Deal Alpha', 'Deal Beta', 'Deal Gamma', 'Deal Delta', 'Deal Echo'],
    'Etapa': ['SAL', 'SQL', 'OPP', 'BC', 'ONB_AGEND'],
    'BDR': ['João Silva', 'Maria Santos', 'Pedro Costa', 'Ana Lima', 'Carlos Rocha'],
    'Entrada': ['2024-01-15', '2024-01-20', '2024-01-25', '2024-02-01', '2024-02-05'],
    'Previsão': ['2024-02-15', '2024-02-25', '2024-03-01', '2024-03-10', '2024-03-15']
}

df = pd.DataFrame(data)

# Converte datas
df['Entrada'] = pd.to_datetime(df['Entrada'])
df['Previsão'] = pd.to_datetime(df['Previsão'])

st.success("✅ Aplicação carregada com sucesso!")

# Métricas
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📋 Total Deals", len(df))
with col2:
    st.metric("🎯 Etapas Ativas", df['Etapa'].nunique())
with col3:
    st.metric("👤 BDRs", df['BDR'].nunique())
with col4:
    st.metric("📅 Hoje", datetime.now().strftime('%d/%m'))

# Tabela
st.subheader("📊 Pipeline de Vendas")
st.dataframe(df, use_container_width=True)

# Análise por etapa
st.subheader("📈 Distribuição por Etapa")
etapa_counts = df['Etapa'].value_counts()

col1, col2 = st.columns(2)
with col1:
    for etapa, count in etapa_counts.items():
        st.write(f"**{etapa}**: {count} deal(s)")

with col2:
    st.bar_chart(etapa_counts)

# Sidebar
with st.sidebar:
    st.header("⚙️ Controles")
    
    # Filtro por BDR
    selected_bdr = st.selectbox("Filtrar por BDR:", ['Todos'] + list(df['BDR'].unique()))
    
    if selected_bdr != 'Todos':
        filtered_df = df[df['BDR'] == selected_bdr]
        st.subheader("📋 Deals Filtrados")
        st.dataframe(filtered_df[['Deal', 'Etapa']], use_container_width=True)
    
    st.divider()
    
    # Status
    st.subheader("📡 Status do Sistema")
    st.write("🟢 App: Online")
    st.write("🟡 Dados: Demonstração") 
    st.write(f"🕒 Hora: {datetime.now().strftime('%H:%M:%S')}")
    
    st.divider()
    
    # Configurações básicas
    st.subheader("⚙️ Configurações")
    lead_time_sal = st.slider("Lead Time SAL (dias)", 1, 10, 3)
    lead_time_sql = st.slider("Lead Time SQL (dias)", 1, 10, 5)
    
    st.write(f"**Total Lead Time**: {lead_time_sal + lead_time_sql} dias")

# Previsões simples
st.subheader("🔮 Previsões Básicas")

predictions_data = {
    'Data': pd.date_range('2024-08-19', periods=10, freq='D'),
    'Conversões Previstas': [2, 3, 1, 4, 2, 3, 5, 2, 1, 3]
}
predictions_df = pd.DataFrame(predictions_data)

# Destaca quartas-feiras
predictions_df['É Quarta'] = predictions_df['Data'].dt.dayofweek == 2
predictions_df['Dia'] = predictions_df['Data'].dt.strftime('%A')

st.line_chart(predictions_df.set_index('Data')['Conversões Previstas'])

# Tabela de previsões
st.dataframe(predictions_df[['Data', 'Dia', 'Conversões Previstas', 'É Quarta']], use_container_width=True)

# Resumo final
st.subheader("📋 Resumo Executivo")
total_previsto = predictions_df['Conversões Previstas'].sum()
quartas_previsto = predictions_df[predictions_df['É Quarta']]['Conversões Previstas'].sum()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🎯 Total Previsto", total_previsto)
with col2:
    st.metric("📅 Quartas-feiras", quartas_previsto)
with col3:
    if total_previsto > 0:
        perc = (quartas_previsto / total_previsto) * 100
        st.metric("📊 % Quartas", f"{perc:.0f}%")

# Footer
st.divider()
st.write("**✅ Sistema funcionando perfeitamente!**")
st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
st.caption("📧 Para conectar dados reais, configure o Google Sheets")
