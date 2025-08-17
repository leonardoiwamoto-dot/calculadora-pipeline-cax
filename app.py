import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
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
    
    # Calcular dias na etapa (só valores positivos)
    df['dias_na_etapa'] = (datetime.now() - df['data_entrada']).dt.days
    df['dias_na_etapa'] = df['dias_na_etapa'].clip(lower=0)  # Remover valores negativos
    
    # Deals atrasados (mais de 7 dias na etapa)
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
    
    # Garantir que dias_na_etapa seja positivo
    df_clean = df.copy()
    df_clean['dias_na_etapa'] = df_clean['dias_na_etapa'].clip(lower=1)  # Mínimo 1 dia
    
    fig = px.scatter(
        df_clean, 
        x='data_entrada', 
        y='etapa',
        color='bdr',
        size='dias_na_etapa',
        hover_data=['dealname', 'dias_na_etapa'],
        title="📅 Timeline dos Deals por Etapa"
    )
    
    fig.update_layout(height=400)
    return fig

# Funções da Calculadora Pipeline
def get_business_days(start_date, num_days):
    """Retorna data após N dias úteis"""
    current = start_date
    days_added = 0
    
    while days_added < num_days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Segunda a sexta
            days_added += 1
    
    return current

def get_next_business_days(num_days=15):
    """Retorna próximos N dias úteis"""
    business_days = []
    current = datetime.now().date()
    
    while len(business_days) < num_days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            business_days.append(current)
    
    return business_days

def calculate_pipeline_forecast(df, config):
    """Calcula previsão do pipeline para próximos dias"""
    if df.empty:
        return []
    
    business_days = get_next_business_days(15)
    results = []
    
    for target_date in business_days:
        daily_result = {
            'date': pd.Timestamp(target_date),
            'SAL': 0, 'SQL': 0, 'OPP': 0, 'BC': 0, 'ONB': 0
        }
        
        for _, deal in df.iterrows():
            entry_date = deal['data_entrada'].date() if pd.notna(deal['data_entrada']) else datetime.now().date()
            current_stage = deal['etapa']
            
            # Calcular quando cada deal deve converter em cada etapa
            if current_stage == 'SAL':
                sql_date = get_business_days(entry_date, config['SAL']['days'])
                opp_date = get_business_days(sql_date, config['SQL']['days']) 
                bc_date = get_business_days(opp_date, config['OPP']['days'])
                onb_date = get_business_days(bc_date, config['BC']['days'])
                
                if target_date <= sql_date:
                    daily_result['SAL'] += 1
                elif target_date <= opp_date:
                    daily_result['SQL'] += config['SAL']['cvr'] / 100
                elif target_date <= bc_date:
                    daily_result['OPP'] += (config['SAL']['cvr'] / 100) * (config['SQL']['cvr'] / 100)
                elif target_date <= onb_date:
                    daily_result['BC'] += (config['SAL']['cvr'] / 100) * (config['SQL']['cvr'] / 100) * (config['OPP']['cvr'] / 100)
                else:
                    daily_result['ONB'] += (config['SAL']['cvr'] / 100) * (config['SQL']['cvr'] / 100) * (config['OPP']['cvr'] / 100) * (config['BC']['cvr'] / 100)
            
            elif current_stage == 'SQL':
                opp_date = get_business_days(entry_date, config['SQL']['days'])
                bc_date = get_business_days(opp_date, config['OPP']['days'])
                onb_date = get_business_days(bc_date, config['BC']['days'])
                
                if target_date <= opp_date:
                    daily_result['SQL'] += 1
                elif target_date <= bc_date:
                    daily_result['OPP'] += config['SQL']['cvr'] / 100
                elif target_date <= onb_date:
                    daily_result['BC'] += (config['SQL']['cvr'] / 100) * (config['OPP']['cvr'] / 100)
                else:
                    daily_result['ONB'] += (config['SQL']['cvr'] / 100) * (config['OPP']['cvr'] / 100) * (config['BC']['cvr'] / 100)
            
            elif current_stage == 'OPP':
                bc_date = get_business_days(entry_date, config['OPP']['days'])
                onb_date = get_business_days(bc_date, config['BC']['days'])
                
                if target_date <= bc_date:
                    daily_result['OPP'] += 1
                elif target_date <= onb_date:
                    daily_result['BC'] += config['OPP']['cvr'] / 100
                else:
                    daily_result['ONB'] += (config['OPP']['cvr'] / 100) * (config['BC']['cvr'] / 100)
            
            elif current_stage == 'BC':
                onb_date = get_business_days(entry_date, config['BC']['days'])
                
                if target_date <= onb_date:
                    daily_result['BC'] += 1
                else:
                    daily_result['ONB'] += config['BC']['cvr'] / 100
            
            elif current_stage == 'ONB_AGEND':
                # Se tem data prevista, usar ela, senão usar data entrada + lead time
                if pd.notna(deal['data_prevista_onboarding']):
                    onb_date = deal['data_prevista_onboarding'].date()
                else:
                    onb_date = get_business_days(entry_date, 2)  # Default 2 dias
                
                if target_date >= onb_date:
                    daily_result['ONB'] += 1
        
        # Arredondar valores
        for key in ['SAL', 'SQL', 'OPP', 'BC', 'ONB']:
            daily_result[key] = round(daily_result[key], 1)
        
        results.append(daily_result)
    
    return results

def create_pipeline_evolution_chart(df_pipeline):
    """Cria gráfico de evolução do pipeline"""
    fig = go.Figure()
    
    colors = {
        'SAL': '#3b82f6',
        'SQL': '#f59e0b', 
        'OPP': '#ef4444',
        'BC': '#10b981',
        'ONB': '#8b5cf6'
    }
    
    for stage in ['SAL', 'SQL', 'OPP', 'BC', 'ONB']:
        fig.add_trace(go.Scatter(
            x=df_pipeline['date'],
            y=df_pipeline[stage],
            mode='lines+markers',
            name=stage,
            line=dict(color=colors[stage], width=3),
            marker=dict(size=6)
        ))
    
    fig.update_layout(
        title="📈 Evolução do Pipeline - Próximos 15 dias",
        xaxis_title="Data",
        yaxis_title="Número de Deals",
        height=500,
        hovermode='x unified'
    )
    
    return fig

def get_next_wednesday_deals(df_pipeline):
    """Retorna deals para próxima quarta-feira"""
    today = datetime.now().date()
    
    # Encontrar próxima quarta-feira
    days_until_wednesday = (2 - today.weekday()) % 7
    if days_until_wednesday == 0:  # Se hoje é quarta
        days_until_wednesday = 7
    
    next_wednesday = today + timedelta(days=days_until_wednesday)
    
    # Encontrar na tabela
    wednesday_row = df_pipeline[df_pipeline['date'].dt.date == next_wednesday]
    
    if not wednesday_row.empty:
        return wednesday_row.iloc[0]['ONB']
    
    return 0

def calculate_scenario_impact(new_sal, new_sql, new_opp, config):
    """Calcula impacto de um cenário de novos deals"""
    
    # Calcular conversões em cascata
    sal_to_onb = new_sal * (config['SAL']['cvr']/100) * (config['SQL']['cvr']/100) * (config['OPP']['cvr']/100) * (config['BC']['cvr']/100)
    sql_to_onb = new_sql * (config['SQL']['cvr']/100) * (config['OPP']['cvr']/100) * (config['BC']['cvr']/100)
    opp_to_onb = new_opp * (config['OPP']['cvr']/100) * (config['BC']['cvr']/100)
    
    total_onbs = sal_to_onb + sql_to_onb + opp_to_onb
    
    # Calcular quando primeira conversão acontece
    min_days = float('inf')
    if new_sal > 0:
        sal_days = config['SAL']['days'] + config['SQL']['days'] + config['OPP']['days'] + config['BC']['days']
        min_days = min(min_days, sal_days)
    if new_sql > 0:
        sql_days = config['SQL']['days'] + config['OPP']['days'] + config['BC']['days']
        min_days = min(min_days, sql_days)
    if new_opp > 0:
        opp_days = config['OPP']['days'] + config['BC']['days']
        min_days = min(min_days, opp_days)
    
    first_conversion_days = min_days if min_days != float('inf') else 0
    
    # Estimativa de receita (R$ 50.000 por ONB)
    estimated_revenue = total_onbs * 50000
    
    return {
        'additional_onbs': total_onbs,
        'first_conversion_days': first_conversion_days,
        'estimated_revenue': estimated_revenue
    }

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
        st.rerun()
    
    # Layout principal com tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔮 Calculadora Pipeline", "📈 Dashboard", "📋 Lista de Deals", "⚠️ Deals Atrasados", "📊 Análises"])
    
    # TAB 1: CALCULADORA PIPELINE (PRINCIPAL)
    with tab1:
        st.header("🔮 Calculadora Pipeline de Vendas")
        
        # Configurações do funil
        st.subheader("⚙️ Configurações do Funil")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Taxa de Conversão (%)**")
            sal_cvr = st.slider("SAL → SQL", 0, 100, 80, key="sal_cvr")
            sql_cvr = st.slider("SQL → OPP", 0, 100, 90, key="sql_cvr") 
            opp_cvr = st.slider("OPP → BC", 0, 100, 75, key="opp_cvr")
            bc_cvr = st.slider("BC → ONB", 0, 100, 67, key="bc_cvr")
        
        with col2:
            st.write("**Lead Time (dias úteis)**")
            sal_days = st.number_input("SAL Lead Time", 0, 30, 2, key="sal_days")
            sql_days = st.number_input("SQL Lead Time", 0, 30, 0, key="sql_days")
            opp_days = st.number_input("OPP Lead Time", 0, 30, 2, key="opp_days")
            bc_days = st.number_input("BC Lead Time", 0, 30, 5, key="bc_days")
        
        # Calcular pipeline atual
        if not filtered_df.empty:
            pipeline_results = calculate_pipeline_forecast(filtered_df, {
                'SAL': {'cvr': sal_cvr, 'days': sal_days},
                'SQL': {'cvr': sql_cvr, 'days': sql_days}, 
                'OPP': {'cvr': opp_cvr, 'days': opp_days},
                'BC': {'cvr': bc_cvr, 'days': bc_days}
            })
            
            # Tabela de previsão
            st.subheader("📅 Previsão Pipeline - Próximos 15 dias úteis")
            
            if pipeline_results:
                df_pipeline = pd.DataFrame(pipeline_results)
                df_pipeline['Data'] = df_pipeline['date'].dt.strftime('%d/%m')
                df_pipeline['Dia'] = df_pipeline['date'].dt.strftime('%a')
                
                # Destacar quartas-feiras
                def highlight_wednesday(row):
                    if row['date'].weekday() == 2:  # Quarta-feira
                        return ['background-color: #fff3cd'] * len(row)
                    return [''] * len(row)
                
                display_cols = ['Data', 'Dia', 'SAL', 'SQL', 'OPP', 'BC', 'ONB']
                styled_df = df_pipeline[display_cols].style.apply(highlight_wednesday, axis=1)
                
                st.dataframe(styled_df, use_container_width=True, height=400)
                
                # Gráfico de evolução
                fig_evolution = create_pipeline_evolution_chart(df_pipeline)
                st.plotly_chart(fig_evolution, use_container_width=True)
                
                # Métricas de resumo
                col1, col2, col3, col4 = st.columns(4)
                
                total_onb_15_days = df_pipeline['ONB'].sum()
                deals_proxima_quarta = get_next_wednesday_deals(df_pipeline)
                
                with col1:
                    st.metric("🎯 ONBs próximos 15 dias", f"{total_onb_15_days:.1f}")
                with col2:
                    st.metric("📅 ONBs próxima quarta", f"{deals_proxima_quarta:.1f}")
                with col3:
                    pipeline_atual = filtered_df.shape[0]
                    st.metric("📊 Pipeline atual", pipeline_atual)
                with col4:
                    conversion_rate = (total_onb_15_days / pipeline_atual * 100) if pipeline_atual > 0 else 0
                    st.metric("📈 Taxa conversão", f"{conversion_rate:.1f}%")
        
        # Teste de cenários
        st.subheader("🎮 Teste de Cenários")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            scenario_sal = st.number_input("Novos SALs hoje", 0, 100, 5, key="scenario_sal")
        with col2:
            scenario_sql = st.number_input("Novos SQLs hoje", 0, 100, 2, key="scenario_sql") 
        with col3:
            scenario_opp = st.number_input("Novos OPPs hoje", 0, 100, 1, key="scenario_opp")
        
        if st.button("🔮 Calcular Cenário"):
            scenario_results = calculate_scenario_impact(
                scenario_sal, scenario_sql, scenario_opp,
                {
                    'SAL': {'cvr': sal_cvr, 'days': sal_days},
                    'SQL': {'cvr': sql_cvr, 'days': sql_days},
                    'OPP': {'cvr': opp_cvr, 'days': opp_days}, 
                    'BC': {'cvr': bc_cvr, 'days': bc_days}
                }
            )
            
            st.success(f"**Impacto do Cenário:**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("🎯 ONBs adicionais", f"+{scenario_results['additional_onbs']:.1f}")
            with col2:
                st.metric("📅 Primeira conversão em", f"{scenario_results['first_conversion_days']} dias")
            with col3:
                st.metric("💰 Receita estimada", f"R$ {scenario_results['estimated_revenue']:,.0f}")
        
        else:
            st.info("👆 Configure o cenário acima e clique em 'Calcular Cenário'")
    
    with tab2:
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
    
    # TAB 3: Lista de Deals
    with tab3:
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
    
    # TAB 4: Deals Atrasados
    with tab4:
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
    
    # TAB 5: Análises
    with tab5:
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
