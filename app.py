import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Configuração da página
st.set_page_config(
    page_title="Calculadora Pipeline CAX",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }
    
    .stage-sal { border-left-color: #3b82f6; }
    .stage-sql { border-left-color: #f59e0b; }
    .stage-opp { border-left-color: #ef4444; }
    .stage-bc { border-left-color: #10b981; }
    .stage-onb { border-left-color: #8b5cf6; }
</style>
""", unsafe_allow_html=True)

# Função para conectar com Google Sheets
@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_data():
    """Carrega dados do Google Sheets"""
    try:
        # Configuração da conexão
        SPREADSHEET_ID = "1L0nO-rchxshEufLANyH3aEz6hFulvpq1OMPUzTw76LM"
        SHEET_NAME = "Pipeline"
        
        # Criar URL para CSV do Google Sheets
        csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
        
        # Carregar dados
        df = pd.read_csv(csv_url)
        
        # Limpar e processar dados
        df = df.dropna(subset=['id'])  # Remove linhas vazias
        df['data_entrada'] = pd.to_datetime(df['data_entrada'], errors='coerce')
        df['data_prevista_onboarding'] = pd.to_datetime(df['data_prevista_onboarding'], errors='coerce')
        
        return df
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        return pd.DataFrame()

# Função para calcular métricas do pipeline
def calculate_metrics(df):
    """Calcula métricas do pipeline"""
    if df.empty:
        return {}
    
    today = datetime.now().date()
    
    # Contagem por etapa
    stage_counts = df['etapa'].value_counts().to_dict()
    
    # Deals para hoje
    deals_hoje = 0
    if 'data_prevista_onboarding' in df.columns:
        deals_hoje = len(df[df['data_prevista_onboarding'].dt.date == today])
    
    # Deals atrasados (mais de 7 dias na etapa)
    df['dias_na_etapa'] = (datetime.now() - df['data_entrada']).dt.days
    deals_atrasados = len(df[df['dias_na_etapa'] > 7])
    
    return {
        'total_deals': len(df),
        'stage_counts': stage_counts,
        'deals_hoje': deals_hoje,
        'deals_atrasados': deals_atrasados,
        'dias_na_etapa': df['dias_na_etapa']
    }

# Função para criar gráfico do funil
def create_funnel_chart(stage_counts):
    """Cria gráfico de funil das etapas"""
    stages = ['SAL', 'SQL', 'OPP', 'BC', 'ONB_AGEND']
    colors = ['#3b82f6', '#f59e0b', '#ef4444', '#10b981', '#8b5cf6']
    
    values = [stage_counts.get(stage, 0) for stage in stages]
    
    fig = go.Figure(go.Funnel(
        y=stages,
        x=values,
        textinfo="value+percent initial",
        marker={
            'color': colors,
            'line': {'width': 2, 'color': 'white'}
        }
    ))
    
    fig.update_layout(
        title="🎯 Funil de Vendas por Etapa",
        height=400,
        showlegend=False
    )
    
    return fig

# Função para criar gráfico de timeline
def create_timeline_chart(df):
    """Cria gráfico de timeline dos deals"""
    if df.empty:
        return None
    
    fig = px.scatter(
        df, 
        x='data_entrada', 
        y='etapa',
        color='bdr',
        size='dias_na_etapa',
        hover_data=['dealname', 'dias_na_etapa'],
        title="📅 Timeline dos Deals por Etapa"
    )
    
    fig.update_layout(height=400)
    return fig

# INTERFACE PRINCIPAL
def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📊 Calculadora Pipeline CAX</h1>
        <p>Dashboard em tempo real conectado com Google Sheets</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Carregar dados
    with st.spinner("🔄 Carregando dados da planilha..."):
        df = load_data()
    
    if df.empty:
        st.error("❌ Não foi possível carregar os dados. Verifique a planilha.")
        st.info("💡 Certifique-se que a planilha está com permissão 'Qualquer pessoa com o link pode visualizar'")
        return
    
    # Sidebar - Filtros
    st.sidebar.header("🎯 Filtros")
    
    # Filtro por BDR
    bdrs = ['Todos'] + sorted(df['bdr'].dropna().unique().tolist())
    selected_bdr = st.sidebar.selectbox("👤 Selecionar BDR", bdrs)
    
    # Filtro por etapa
    etapas = ['Todas'] + sorted(df['etapa'].dropna().unique().tolist())
    selected_etapa = st.sidebar.selectbox("🎯 Selecionar Etapa", etapas)
    
    # Aplicar filtros
    filtered_df = df.copy()
    if selected_bdr != 'Todos':
        filtered_df = filtered_df[filtered_df['bdr'] == selected_bdr]
    if selected_etapa != 'Todas':
        filtered_df = filtered_df[filtered_df['etapa'] == selected_etapa]
    
    # Calcular métricas
    metrics = calculate_metrics(filtered_df)
    
    # Informações no sidebar
    st.sidebar.markdown("---")
    st.sidebar.metric("📊 Total de Deals", metrics.get('total_deals', 0))
    st.sidebar.metric("📅 Para Hoje", metrics.get('deals_hoje', 0))
    st.sidebar.metric("⚠️ Atrasados", metrics.get('deals_atrasados', 0))
    
    # Botão de atualizar
    if st.sidebar.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.experimental_rerun()
    
    # Layout principal com tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Dashboard", "📋 Lista de Deals", "⚠️ Deals Atrasados", "📊 Análises"])
    
    # TAB 1: Dashboard Principal
    with tab1:
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        stage_counts = metrics.get('stage_counts', {})
        
        with col1:
            st.metric("🔵 SAL", stage_counts.get('SAL', 0))
        with col2:
            st.metric("🟡 OPP", stage_counts.get('OPP', 0))
        with col3:
            st.metric("🟢 BC", stage_counts.get('BC', 0))
        with col4:
            st.metric("🟣 ONB_AGEND", stage_counts.get('ONB_AGEND', 0))
        
        # Gráficos
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de funil
            funnel_fig = create_funnel_chart(stage_counts)
            st.plotly_chart(funnel_fig, use_container_width=True)
        
        with col2:
            # Gráfico de distribuição por BDR
            if not filtered_df.empty:
                bdr_counts = filtered_df['bdr'].value_counts()
                fig = px.pie(
                    values=bdr_counts.values, 
                    names=bdr_counts.index,
                    title="👥 Distribuição por BDR"
                )
                st.plotly_chart(fig, use_container_width=True)
    
    # TAB 2: Lista de Deals
    with tab2:
        st.subheader("📋 Lista Completa de Deals")
        
        if not filtered_df.empty:
            # Adicionar coluna de dias na etapa
            display_df = filtered_df.copy()
            display_df['dias_na_etapa'] = (datetime.now() - display_df['data_entrada']).dt.days
            
            # Selecionar colunas para exibir
            columns_to_show = ['id', 'dealname', 'etapa', 'data_entrada', 'bdr', 'dias_na_etapa']
            display_df = display_df[columns_to_show]
            
            # Ordenar por data de entrada (mais recente primeiro)
            display_df = display_df.sort_values('data_entrada', ascending=False)
            
            # Exibir tabela
            st.dataframe(
                display_df,
                use_container_width=True,
                height=600
            )
            
            # Download
            csv = display_df.to_csv(index=False)
            st.download_button(
                "📥 Download CSV",
                csv,
                "pipeline_deals.csv",
                "text/csv"
            )
        else:
            st.info("Nenhum deal encontrado com os filtros selecionados.")
    
    # TAB 3: Deals Atrasados
    with tab3:
        st.subheader("⚠️ Deals Atrasados (7+ dias na etapa)")
        
        if not filtered_df.empty:
            # Filtrar deals atrasados
            dias_na_etapa = (datetime.now() - filtered_df['data_entrada']).dt.days
            atrasados_df = filtered_df[dias_na_etapa > 7].copy()
            atrasados_df['dias_na_etapa'] = dias_na_etapa[dias_na_etapa > 7]
            
            if not atrasados_df.empty:
                # Ordenar por dias na etapa (mais atrasado primeiro)
                atrasados_df = atrasados_df.sort_values('dias_na_etapa', ascending=False)
                
                # Adicionar cor baseada na urgência
                def get_urgency_color(dias):
                    if dias > 14:
                        return "🔴"
                    elif dias > 10:
                        return "🟡"
                    else:
                        return "🟠"
                
                atrasados_df['urgencia'] = atrasados_df['dias_na_etapa'].apply(get_urgency_color)
                
                # Selecionar colunas
                columns_to_show = ['urgencia', 'dealname', 'etapa', 'data_entrada', 'bdr', 'dias_na_etapa']
                display_df = atrasados_df[columns_to_show]
                
                st.dataframe(display_df, use_container_width=True, height=400)
                
                # Métricas de urgência
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("🔴 Críticos (14+ dias)", len(atrasados_df[atrasados_df['dias_na_etapa'] > 14]))
                with col2:
                    st.metric("🟡 Atenção (10-14 dias)", len(atrasados_df[(atrasados_df['dias_na_etapa'] > 10) & (atrasados_df['dias_na_etapa'] <= 14)]))
                with col3:
                    st.metric("🟠 Moderado (7-10 dias)", len(atrasados_df[(atrasados_df['dias_na_etapa'] > 7) & (atrasados_df['dias_na_etapa'] <= 10)]))
            else:
                st.success("🎉 Nenhum deal atrasado! Excelente trabalho!")
        else:
            st.info("Nenhum dado disponível.")
    
    # TAB 4: Análises
    with tab4:
        st.subheader("📊 Análises Avançadas")
        
        if not filtered_df.empty:
            # Timeline dos deals
            timeline_fig = create_timeline_chart(filtered_df)
            if timeline_fig:
                st.plotly_chart(timeline_fig, use_container_width=True)
            
            # Estatísticas por etapa
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📈 Tempo Médio por Etapa")
                tempo_por_etapa = filtered_df.groupby('etapa')['dias_na_etapa'].agg(['mean', 'median', 'std']).round(1)
                st.dataframe(tempo_por_etapa)
            
            with col2:
                st.subheader("👥 Performance por BDR")
                perf_bdr = filtered_df.groupby('bdr').agg({
                    'id': 'count',
                    'dias_na_etapa': 'mean'
                }).round(1)
                perf_bdr.columns = ['Total Deals', 'Tempo Médio']
                st.dataframe(perf_bdr)
        else:
            st.info("Selecione filtros para ver as análises.")
    
    # Footer
    st.markdown("---")
    st.markdown(f"🔄 **Última atualização:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    st.markdown("📊 **Dados em tempo real** conectados com Google Sheets")

if __name__ == "__main__":
    main()
