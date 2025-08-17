import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from io import StringIO
import requests
import time

# Configuração da página
st.set_page_config(
    page_title="Calculadora Pipeline CAX",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado para melhor aparência
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        margin-bottom: 2rem;
    }
    .metric-container {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .stAlert > div {
        padding-top: 0.5rem;
        padding-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Configurações globais
GOOGLE_SHEETS_ID = "1L0nO-rchxshEufLANyH3aEz6hFulvpq1OMPUzTw76LM"
ETAPAS_FUNIL = ['SAL', 'SQL', 'OPP', 'BC', 'ONB_AGEND', 'ONB']

# Cache com TTL de 5 minutos
@st.cache_data(ttl=300)
def load_data():
    """Carrega dados do Google Sheets com fallback robusto"""
    
    urls_to_try = [
        f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}/export?format=csv&gid=0",
        f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}/export?format=csv",
        f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}/gviz/tq?tqx=out:csv&gid=0",
        f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}/gviz/tq?tqx=out:csv"
    ]
    
    for i, url in enumerate(urls_to_try):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            if len(response.text) < 20:
                continue
            
            df = pd.read_csv(StringIO(response.text))
            
            if df.empty or len(df.columns) < 2:
                continue
            
            # Limpeza e formatação dos dados
            df.columns = df.columns.str.strip()
            
            # Converte datas
            date_columns = ['data_entrada', 'data_prevista_onboarding']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            # Remove linhas vazias
            if 'dealname' in df.columns:
                df = df.dropna(subset=['dealname'])
                df = df[df['dealname'].str.strip() != '']
            
            # Limpa dados de BDR
            if 'bdr' in df.columns:
                df['bdr'] = df['bdr'].fillna('N/A').astype(str).str.strip()
            
            # Valida etapas
            if 'etapa' in df.columns:
                df['etapa'] = df['etapa'].str.strip()
                df = df[df['etapa'].isin(ETAPAS_FUNIL)]
            
            st.success(f"✅ Dados carregados: {len(df)} registros do Google Sheets")
            return df
            
        except Exception as e:
            if i == len(urls_to_try) - 1:
                st.warning("⚠️ Erro ao carregar Google Sheets. Usando dados de exemplo.")
                return create_sample_data()
            continue
    
    return create_sample_data()

def create_sample_data():
    """Cria dados de exemplo realistas para demonstração"""
    np.random.seed(42)  # Para dados consistentes
    
    deals_data = []
    bdrs = ['João Silva', 'Maria Santos', 'Pedro Costa', 'Ana Lima', 'Carlos Rocha']
    
    for i in range(25):
        etapa = np.random.choice(ETAPAS_FUNIL[:-1], p=[0.3, 0.25, 0.2, 0.15, 0.1])
        bdr = np.random.choice(bdrs)
        
        # Datas mais realistas
        days_ago = np.random.randint(1, 60)
        data_entrada = datetime.now() - timedelta(days=days_ago)
        
        # Data prevista baseada na etapa
        etapa_lead_times = {'SAL': 14, 'SQL': 21, 'OPP': 30, 'BC': 45, 'ONB_AGEND': 7}
        lead_time = etapa_lead_times.get(etapa, 21)
        data_prevista = data_entrada + timedelta(days=lead_time + np.random.randint(-7, 14))
        
        deals_data.append({
            'id': f"DEAL-{i+1:03d}",
            'dealname': f"Empresa {['Alpha', 'Beta', 'Gamma', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel'][i % 8]} {i+1}",
            'etapa': etapa,
            'data_entrada': data_entrada,
            'data_prevista_onboarding': data_prevista,
            'bdr': bdr
        })
    
    # Adiciona alguns deals ONB (fechados)
    for i in range(5):
        deals_data.append({
            'id': f"DEAL-ONB-{i+1:03d}",
            'dealname': f"Deal Fechado {i+1}",
            'etapa': 'ONB',
            'data_entrada': datetime.now() - timedelta(days=np.random.randint(30, 90)),
            'data_prevista_onboarding': datetime.now() - timedelta(days=np.random.randint(1, 15)),
            'bdr': np.random.choice(bdrs)
        })
    
    return pd.DataFrame(deals_data)

def is_business_day(date):
    """Verifica se é dia útil (Segunda a Sexta)"""
    return date.weekday() < 5

def add_business_days(start_date, business_days):
    """Adiciona dias úteis a uma data"""
    current_date = start_date
    days_added = 0
    
    while days_added < business_days:
        current_date += timedelta(days=1)
        if is_business_day(current_date):
            days_added += 1
    
    return current_date

def get_next_business_days(num_days=15):
    """Retorna próximos dias úteis"""
    business_days = []
    current_date = datetime.now().date()
    
    while len(business_days) < num_days:
        current_date += timedelta(days=1)
        if is_business_day(current_date):
            business_days.append(current_date)
    
    return business_days

def calculate_conversion_prediction(df, config, test_scenarios=None):
    """Calcula previsão detalhada de conversões"""
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # Configurações
    lead_times = config.get('lead_times', {
        'SAL': 2, 'SQL': 3, 'OPP': 5, 'BC': 7, 'ONB_AGEND': 2, 'ONB': 0
    })
    conversion_rates = config.get('conversion_rates', {
        'SAL': 0.6, 'SQL': 0.7, 'OPP': 0.8, 'BC': 0.9, 'ONB_AGEND': 0.95, 'ONB': 1.0
    })
    
    next_days = get_next_business_days(15)
    results = []
    detailed_results = []
    
    # Processa deals existentes
    for _, deal in df.iterrows():
        if deal['etapa'] not in ETAPAS_FUNIL or deal['etapa'] == 'ONB':
            continue
        
        base_date = datetime.now().date()
        if pd.notna(deal.get('data_entrada')):
            base_date = max(base_date, deal['data_entrada'].date())
        
        current_stage_idx = ETAPAS_FUNIL.index(deal['etapa'])
        probability = 1.0
        
        # Calcula probabilidade cumulativa
        for stage_idx in range(current_stage_idx, len(ETAPAS_FUNIL)-1):
            stage = ETAPAS_FUNIL[stage_idx]
            probability *= conversion_rates.get(stage, 0.5)
        
        # Calcula lead time total
        total_lead_time = sum([lead_times.get(ETAPAS_FUNIL[i], 2) for i in range(current_stage_idx, len(ETAPAS_FUNIL)-1)])
        conversion_date = add_business_days(base_date, total_lead_time)
        
        if conversion_date in next_days:
            results.append({
                'data': conversion_date,
                'conversoes_previstas': probability,
                'total_deals': 1,
                'tipo': 'Existente'
            })
            
            detailed_results.append({
                'data': conversion_date,
                'deal': deal['dealname'],
                'etapa_atual': deal['etapa'],
                'probabilidade': probability,
                'bdr': deal.get('bdr', 'N/A'),
                'lead_time': total_lead_time,
                'tipo': 'Existente'
            })
    
    # Processa cenários de teste
    if test_scenarios:
        for scenario in test_scenarios:
            stage = scenario.get('etapa', 'SAL')
            quantity = scenario.get('quantidade', 1)
            target_date = scenario.get('data_entrada', datetime.now().date())
            scenario_name = scenario.get('nome', 'Teste')
            
            if stage not in ETAPAS_FUNIL or stage == 'ONB':
                continue
            
            current_stage_idx = ETAPAS_FUNIL.index(stage)
            probability = 1.0
            
            # Calcula probabilidade para cenário
            for stage_idx in range(current_stage_idx, len(ETAPAS_FUNIL)-1):
                current_stage = ETAPAS_FUNIL[stage_idx]
                probability *= conversion_rates.get(current_stage, 0.5)
            
            # Lead time para cenário
            total_lead_time = sum([lead_times.get(ETAPAS_FUNIL[i], 2) for i in range(current_stage_idx, len(ETAPAS_FUNIL)-1)])
            conversion_date = add_business_days(target_date, total_lead_time)
            
            if conversion_date in next_days:
                total_scenario_conversions = quantity * probability
                
                results.append({
                    'data': conversion_date,
                    'conversoes_previstas': total_scenario_conversions,
                    'total_deals': quantity,
                    'tipo': 'Cenário'
                })
                
                for i in range(quantity):
                    detailed_results.append({
                        'data': conversion_date,
                        'deal': f"{scenario_name} #{i+1}",
                        'etapa_atual': stage,
                        'probabilidade': probability,
                        'bdr': scenario.get('bdr', 'Cenário'),
                        'lead_time': total_lead_time,
                        'tipo': 'Cenário'
                    })
    
    if not results:
        return pd.DataFrame(), pd.DataFrame()
    
    # Cria DataFrame resumo
    results_df = pd.DataFrame(results)
    summary = results_df.groupby('data').agg({
        'conversoes_previstas': 'sum',
        'total_deals': 'sum'
    }).round(2)
    
    summary.columns = ['Conversões Previstas', 'Total Deals']
    summary['Data'] = summary.index
    summary['Dia Semana'] = summary['Data'].apply(lambda x: x.strftime('%A'))
    summary['É Quarta'] = summary['Data'].apply(lambda x: x.weekday() == 2)
    summary = summary[['Data', 'Dia Semana', 'É Quarta', 'Conversões Previstas', 'Total Deals']].reset_index(drop=True)
    
    # DataFrame detalhado
    detailed_df = pd.DataFrame(detailed_results)
    
    return summary, detailed_df

def safe_display_dataframe(df, title="", height=400):
    """Exibe DataFrame com formatação segura"""
    if title:
        st.subheader(title)
    
    if df.empty:
        st.info("📭 Nenhum dado disponível")
        return
    
    try:
        if 'É Quarta' in df.columns:
            display_df = df.copy()
            # Adiciona emoji para quartas-feiras
            mask = display_df['É Quarta'] == True
            display_df.loc[mask, 'Dia Semana'] = '🎯 ' + display_df.loc[mask, 'Dia Semana']
            display_df = display_df.drop('É Quarta', axis=1)
            st.dataframe(display_df, use_container_width=True, height=height)
        else:
            st.dataframe(df, use_container_width=True, height=height)
            
    except Exception as e:
        st.warning(f"Problema na formatação: {str(e)[:50]}...")
        st.dataframe(df, use_container_width=True, height=height)

def create_conversion_chart(df):
    """Cria gráfico avançado de conversões"""
    if df.empty:
        return None
    
    fig = go.Figure()
    
    # Dias normais
    normal_days = df[df['É Quarta'] == False]
    if not normal_days.empty:
        fig.add_trace(go.Bar(
            x=normal_days['Data'],
            y=normal_days['Conversões Previstas'],
            name='Dias Úteis',
            marker_color='#1f77b4',
            hovertemplate='<b>%{x}</b><br>' +
                         'Conversões: %{y:.1f}<br>' +
                         'Deals: %{customdata}<br>' +
                         '<extra></extra>',
            customdata=normal_days['Total Deals']
        ))
    
    # Quartas-feiras destacadas
    wednesdays = df[df['É Quarta'] == True]
    if not wednesdays.empty:
        fig.add_trace(go.Bar(
            x=wednesdays['Data'],
            y=wednesdays['Conversões Previstas'],
            name='🎯 Quartas-feiras (ONB)',
            marker_color='#ff7f0e',
            hovertemplate='<b>%{x} (Quarta-feira)</b><br>' +
                         'Conversões: %{y:.1f}<br>' +
                         'Deals: %{customdata}<br>' +
                         '<extra></extra>',
            customdata=wednesdays['Total Deals']
        ))
    
    # Layout melhorado
    fig.update_layout(
        title={
            'text': '📈 Previsão de Conversões - Próximos 15 Dias Úteis',
            'x': 0.5,
            'xanchor': 'center'
        },
        xaxis_title='Data',
        yaxis_title='Conversões Previstas',
        hovermode='x unified',
        showlegend=True,
        height=500,
        template='plotly_white'
    )
    
    return fig

def create_funnel_chart(df):
    """Cria gráfico de funil de vendas"""
    if df.empty or 'etapa' not in df.columns:
        return None
    
    # Conta deals por etapa
    funnel_data = df['etapa'].value_counts()
    
    # Ordena pelas etapas do funil
    ordered_stages = [stage for stage in ETAPAS_FUNIL if stage in funnel_data.index]
    funnel_counts = [funnel_data[stage] for stage in ordered_stages]
    
    fig = go.Figure()
    
    fig.add_trace(go.Funnel(
        y=ordered_stages,
        x=funnel_counts,
        textinfo="value+percent initial",
        marker=dict(
            color=["#ff9999", "#66b3ff", "#99ff99", "#ffcc99", "#ff99cc", "#c2c2f0"][:len(ordered_stages)]
        )
    ))
    
    fig.update_layout(
        title={
            'text': '🎯 Funil de Vendas - Distribuição por Etapa',
            'x': 0.5,
            'xanchor': 'center'
        },
        height=400
    )
    
    return fig

def get_deals_late(df):
    """Identifica e classifica deals atrasados"""
    if df.empty or 'data_prevista_onboarding' not in df.columns:
        return pd.DataFrame()
    
    today = datetime.now().date()
    
    # Filtra deals atrasados
    late_deals = df[
        (pd.notna(df['data_prevista_onboarding'])) &
        (df['data_prevista_onboarding'].dt.date < today) &
        (df['etapa'] != 'ONB')
    ].copy()
    
    if late_deals.empty:
        return pd.DataFrame()
    
    # Calcula dias de atraso
    late_deals['dias_atraso'] = (today - late_deals['data_prevista_onboarding'].dt.date).dt.days
    
    # Classifica por urgência
    def classify_urgency(days):
        if days >= 14:
            return '🔴 Crítico (14+ dias)'
        elif days >= 7:
            return '🟠 Alto (7-13 dias)'
        elif days >= 3:
            return '🟡 Médio (3-6 dias)'
        else:
            return '🟢 Baixo (1-2 dias)'
    
    late_deals['urgencia'] = late_deals['dias_atraso'].apply(classify_urgency)
    
    # Prepara resultado
    result = late_deals[[
        'dealname', 'etapa', 'bdr', 'data_prevista_onboarding', 
        'dias_atraso', 'urgencia'
    ]].sort_values(['dias_atraso', 'dealname'], ascending=[False, True])
    
    result.columns = ['Deal', 'Etapa', 'BDR', 'Data Prevista', 'Dias Atraso', 'Urgência']
    
    return result

def create_bdr_performance_chart(df):
    """Cria gráfico de performance por BDR"""
    if df.empty or 'bdr' not in df.columns:
        return None
    
    # Performance por BDR
    bdr_stats = df.groupby('bdr').agg({
        'etapa': 'count',
        'dealname': lambda x: (df[df['bdr'] == x.iloc[0]]['etapa'] == 'ONB').sum() if not x.empty else 0
    }).round(2)
    
    bdr_stats.columns = ['Total Deals', 'Onboarding']
    bdr_stats['Taxa Conversão (%)'] = (bdr_stats['Onboarding'] / bdr_stats['Total Deals'] * 100).round(1)
    
    fig = go.Figure()
    
    # Adiciona barras para total de deals
    fig.add_trace(go.Bar(
        name='Total Deals',
        x=bdr_stats.index,
        y=bdr_stats['Total Deals'],
        marker_color='#1f77b4',
        yaxis='y'
    ))
    
    # Adiciona linha para taxa de conversão
    fig.add_trace(go.Scatter(
        name='Taxa Conversão (%)',
        x=bdr_stats.index,
        y=bdr_stats['Taxa Conversão (%)'],
        mode='lines+markers',
        marker_color='#ff7f0e',
        yaxis='y2'
    ))
    
    fig.update_layout(
        title='👤 Performance por BDR',
        xaxis_title='BDR',
        yaxis=dict(title='Número de Deals', side='left'),
        yaxis2=dict(title='Taxa de Conversão (%)', side='right', overlaying='y'),
        height=400,
        template='plotly_white'
    )
    
    return fig

def main():
    # Header principal
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.title("📊 Calculadora Pipeline CAX")
    st.markdown("*Dashboard completo de previsões e análise de pipeline de vendas*")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Sidebar - Configurações
    with st.sidebar:
        st.header("⚙️ Configurações do Pipeline")
        
        # Controles de atualização
        st.subheader("🔄 Atualização de Dados")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Recarregar", help="Atualiza dados do Google Sheets"):
                st.cache_data.clear()
                st.rerun()
        
        with col2:
            auto_refresh = st.checkbox("Auto-refresh 5min", value=False, help="CUIDADO: Pode causar loops")
        
        st.divider()
        
        # Configurações de conversão
        st.subheader("📈 Taxas de Conversão")
        st.caption("Probabilidade de avançar para próxima etapa")
        
        conversion_rates = {}
        default_rates = {'SAL': 0.6, 'SQL': 0.7, 'OPP': 0.8, 'BC': 0.9, 'ONB_AGEND': 0.95}
        
        for etapa in ETAPAS_FUNIL[:-1]:
            conversion_rates[etapa] = st.slider(
                f"{etapa} → Próxima", 0.0, 1.0, 
                value=default_rates.get(etapa, 0.5),
                step=0.05,
                help=f"Taxa de conversão da etapa {etapa}",
                key=f"conv_{etapa}"
            )
        
        st.divider()
        
        # Lead times
        st.subheader("⏱️ Lead Times (dias úteis)")
        st.caption("Tempo médio em cada etapa")
        
        lead_times = {}
        default_lead_times = {'SAL': 2, 'SQL': 3, 'OPP': 5, 'BC': 7, 'ONB_AGEND': 2}
        
        for etapa in ETAPAS_FUNIL[:-1]:
            lead_times[etapa] = st.number_input(
                f"{etapa}", min_value=0, max_value=30,
                value=default_lead_times.get(etapa, 2),
                help=f"Dias úteis na etapa {etapa}",
                key=f"lead_{etapa}"
            )
        
        # Resumo das configurações
        total_lead_time = sum(lead_times.values())
        avg_conversion = np.mean(list(conversion_rates.values()))
        
        st.divider()
        st.subheader("📊 Resumo Config")
        st.metric("Lead Time Total", f"{total_lead_time} dias")
        st.metric("Taxa Média", f"{avg_conversion:.1%}")
    
    # Carrega dados
    df = load_data()
    
    if df.empty:
        st.error("❌ Erro crítico ao carregar dados")
        st.stop()
    
    # Auto-refresh (cuidadoso)
    if auto_refresh:
        time.sleep(300)  # 5 minutos
        st.rerun()
    
    # Métricas principais
    st.subheader("📋 Métricas Principais")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total_deals = len(df[df['etapa'] != 'ONB'])
        st.metric("📋 Deals Ativos", total_deals)
    
    with col2:
        deals_onb = len(df[df['etapa'] == 'ONB'])
        st.metric("✅ Onboarding", deals_onb)
    
    with col3:
        deals_bc = len(df[df['etapa'] == 'BC'])
        st.metric("🔥 Business Case", deals_bc)
    
    with col4:
        if total_deals > 0:
            conversion_rate = (deals_onb / (total_deals + deals_onb)) * 100
            st.metric("📊 Taxa Geral", f"{conversion_rate:.1f}%")
        else:
            st.metric("📊 Taxa Geral", "0%")
    
    with col5:
        bdrs_count = df['bdr'].nunique() if 'bdr' in df.columns else 0
        st.metric("👤 BDRs Ativos", bdrs_count)
    
    # Abas principais
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Previsões", "🧪 Cenários", "📋 Deals", "📊 Análises", "🚨 Atrasados"
    ])
    
    with tab1:
        st.header("📅 Previsão de Conversões")
        st.caption("Baseada em probabilidades e lead times configurados")
        
        # Filtros para previsões
        col1, col2, col3 = st.columns(3)
        
        with col1:
            bdrs = ['Todos'] + list(df['bdr'].dropna().unique()) if 'bdr' in df.columns else ['Todos']
            selected_bdr = st.selectbox("👤 Filtrar por BDR", bdrs)
        
        with col2:
            etapas = ['Todas'] + ETAPAS_FUNIL
            selected_etapa = st.selectbox("🎯 Filtrar por Etapa", etapas)
        
        with col3:
            show_details = st.checkbox("📋 Mostrar detalhes", value=False)
        
        # Aplica filtros
        filtered_df = df.copy()
        if selected_bdr != 'Todos' and 'bdr' in df.columns:
            filtered_df = filtered_df[filtered_df['bdr'] == selected_bdr]
        if selected_etapa != 'Todas':
            filtered_df = filtered_df[filtered_df['etapa'] == selected_etapa]
        
        # Configuração do algoritmo
        config = {
            'conversion_rates': conversion_rates,
            'lead_times': lead_times
        }
        
        # Calcula previsões
        prediction_df, detailed_df = calculate_conversion_prediction(filtered_df, config)
        
        if not prediction_df.empty:
            # Gráfico principal
            chart = create_conversion_chart(prediction_df)
            if chart:
                st.plotly_chart(chart, use_container_width=True)
            
            # Tabela de previsões
            safe_display_dataframe(prediction_df, "📊 Resumo de Previsões por Dia")
            
            # Detalhes se solicitado
            if show_details and not detailed_df.empty:
                st.subheader("🔍 Detalhes por Deal")
                detailed_display = detailed_df[['data', 'deal', 'etapa_atual', 'probabilidade', 'bdr', 'lead_time']].copy()
                detailed_display.columns = ['Data', 'Deal', 'Etapa', 'Probabilidade', 'BDR', 'Lead Time']
                st.dataframe(detailed_display, use_container_width=True)
            
            # Métricas de resumo
            st.subheader("📊 Resumo Executivo")
            
            total_conversoes = prediction_df['Conversões Previstas'].sum()
            quartas_conversoes = prediction_df[prediction_df['É Quarta'] == True]['Conversões Previstas'].sum()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("🎯 Total Previsto", f"{total_conversoes:.1f}")
            
            with col2:
                st.metric("📅 Em Quartas", f"{quartas_conversoes:.1f}")
            
            with col3:
                if total_conversoes > 0:
                    perc_quartas = (quartas_conversoes / total_conversoes) * 100
                    st.metric("📊 % Quartas", f"{perc_quartas:.1f}%")
                else:
                    st.metric("📊 % Quartas", "0%")
            
            with col4:
                next_wednesday = next((d for d in prediction_df[prediction_df['É Quarta'] == True]['Data']), None)
                if next_wednesday:
                    days_to_wednesday = (next_wednesday - datetime.now().date()).days
                    st.metric("📅 Próxima Quarta", f"{days_to_wednesday} dias")
                else:
                    st.metric("📅 Próxima Quarta", "N/A")
        else:
            st.info("📭 Nenhuma conversão prevista nos próximos 15 dias úteis com os filtros atuais")
    
    with tab2:
        st.header("🧪 Simulador de Cenários")
        st.caption("Teste o impacto de novos deals no pipeline")
        
        # Formulário de cenários
        with st.form("scenario_form", clear_on_submit=False):
            st.subheader("Configurar Cenário")
            
            col1, col2 = st.columns(2)
            
            with col1:
                scenario_name = st.text_input("📝 Nome do Cenário", "Novo Cenário", 
                                            help="Nome para identificar este cenário")
                scenario_stage = st.selectbox("🎯 Etapa Inicial", ETAPAS_FUNIL[:-1], 
                                            help="Em qual etapa os deals começam")
                scenario_quantity = st.number_input("📊 Quantidade de Deals", 
                                                  min_value=1, max_value=100, value=5,
                                                  help="Quantos deals simular")
            
            with col2:
                scenario_bdr = st.text_input("👤 BDR Responsável", "Cenário", 
                                           help="BDR que trabalhará estes deals")
                scenario_date = st.date_input("📅 Data de Entrada", datetime.now().date(),
                                            help="Quando os deals entram no pipeline")
                
                submit_scenario = st.form_submit_button("🚀 Simular Cenário", 
                                                       help="Executar simulação")
        
        if submit_scenario:
            # Configura cenário
            test_scenarios = [{
                'nome': scenario_name,
                'etapa': scenario_stage,
                'quantidade': scenario_quantity,
                'bdr': scenario_bdr,
                'data_entrada': scenario_date
            }]
            
            # Executa simulação
            scenario_prediction, scenario_detailed = calculate_conversion_prediction(
                df, config, test_scenarios
            )
            
            if not scenario_prediction.empty:
                st.success(f"✅ Cenário '{scenario_name}' simulado com sucesso!")
                
                # Gráfico do cenário
                chart = create_conversion_chart(scenario_prediction)
                if chart:
                    st.plotly_chart(chart, use_container_width=True)
                
                # Tabela do cenário
                safe_display_dataframe(scenario_prediction, f"📊 Resultado: {scenario_name}")
                
                # Impacto do cenário
                col1, col2, col3 = st.columns(3)
                
                total_scenario = scenario_prediction['Conversões Previstas'].sum()
                scenario_wednesdays = scenario_prediction[scenario_prediction['É Quarta'] == True]['Conversões Previstas'].sum()
                
                with col1:
                    st.metric("🎯 Conversões Previstas", f"{total_scenario:.1f}")
                
                with col2:
                    st.metric("📅 Em Quartas-feiras", f"{scenario_wednesdays:.1f}")
                
                with col3:
                    if total_scenario > 0:
                        impact_percentage = (scenario_wednesdays / total_scenario) * 100
                        st.metric("📊 Impacto Quartas", f"{impact_percentage:.1f}%")
                
                # Comparação com pipeline atual
                current_prediction, _ = calculate_conversion_prediction(df, config)
                if not current_prediction.empty:
                    current_total = current_prediction['Conversões Previstas'].sum()
                    increase = ((total_scenario / current_total) * 100) if current_total > 0 else 0
                    
                    st.info(f"📈 Este cenário representa um aumento de {increase:.1f}% nas conversões previstas")
            else:
                st.warning("⚠️ O cenário configurado não gera previsões no período analisado (15 dias úteis)")
    
    with tab3:
        st.header("📋 Gestão de Deals")
        
        # Filtros para deals
        col1, col2, col3 = st.columns(3)
        
        with col1:
            bdrs_filter = ['Todos'] + list(df['bdr'].dropna().unique()) if 'bdr' in df.columns else ['Todos']
            bdr_filter = st.selectbox("👤 BDR", bdrs_filter, key="deals_bdr")
        
        with col2:
            etapas_filter = ['Todas'] + ETAPAS_FUNIL
            etapa_filter = st.selectbox("🎯 Etapa", etapas_filter, key="deals_etapa")
        
        with col3:
            show_dates = st.checkbox("📅 Mostrar datas", value=True)
        
        # Aplica filtros
        deals_df = df.copy()
        if bdr_filter != 'Todos' and 'bdr' in df.columns:
            deals_df = deals_df[deals_df['bdr'] == bdr_filter]
        if etapa_filter != 'Todas':
            deals_df = deals_df[deals_df['etapa'] == etapa_filter]
        
        if not deals_df.empty:
            # Prepara colunas para exibição
            display_cols = ['dealname', 'etapa', 'bdr']
            
            if show_dates and 'data_entrada' in deals_df.columns:
                display_cols.append('data_entrada')
            if show_dates and 'data_prevista_onboarding' in deals_df.columns:
                display_cols.append('data_prevista_onboarding')
            
            # Filtra colunas existentes
            available_cols = [col for col in display_cols if col in deals_df.columns]
            deals_display = deals_df[available_cols].copy()
            
            # Renomeia colunas
            column_rename = {
                'dealname': 'Deal',
                'etapa': 'Etapa',
                'bdr': 'BDR',
                'data_entrada': 'Data Entrada',
                'data_prevista_onboarding': 'Data Prev. ONB'
            }
            deals_display = deals_display.rename(columns=column_rename)
            
            # Ordena por etapa e nome
            if 'Etapa' in deals_display.columns:
                etapa_order = {etapa: i for i, etapa in enumerate(ETAPAS_FUNIL)}
                deals_display['_sort_order'] = deals_display['Etapa'].map(etapa_order)
                deals_display = deals_display.sort_values(['_sort_order', 'Deal'])
                deals_display = deals_display.drop('_sort_order', axis=1)
            
            safe_display_dataframe(deals_display, f"📊 {len(deals_display)} deals encontrados")
            
            # Estatísticas dos deals
            if len(deals_display) > 0:
                st.subheader("📈 Estatísticas dos Deals Filtrados")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if 'Etapa' in deals_display.columns:
                        most_common_stage = deals_display['Etapa'].mode().iloc[0] if not deals_display.empty else 'N/A'
                        st.metric("📊 Etapa Mais Comum", most_common_stage)
                
                with col2:
                    if 'BDR' in deals_display.columns:
                        most_active_bdr = deals_display['BDR'].mode().iloc[0] if not deals_display.empty else 'N/A'
                        st.metric("👤 BDR Mais Ativo", most_active_bdr)
                
                with col3:
                    if 'Data Entrada' in deals_display.columns:
                        try:
                            avg_age = (datetime.now() - pd.to_datetime(deals_display['Data Entrada']).mean()).days
                            st.metric("⏱️ Idade Média", f"{avg_age} dias")
                        except:
                            st.metric("⏱️ Idade Média", "N/A")
        else:
            st.info("📭 Nenhum deal encontrado com os filtros aplicados")
    
    with tab4:
        st.header("📊 Análises Avançadas")
        
        if not df.empty:
            # Funil de vendas
            col1, col2 = st.columns(2)
            
            with col1:
                funnel_chart = create_funnel_chart(df)
                if funnel_chart:
                    st.plotly_chart(funnel_chart, use_container_width=True)
            
            with col2:
                # Distribuição por etapa (pizza)
                etapa_counts = df['etapa'].value_counts()
                fig_pie = px.pie(
                    values=etapa_counts.values,
                    names=etapa_counts.index,
                    title="📊 Distribuição Atual por Etapa",
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            # Performance por BDR
            if 'bdr' in df.columns:
                bdr_chart = create_bdr_performance_chart(df)
                if bdr_chart:
                    st.plotly_chart(bdr_chart, use_container_width=True)
            
            # Análise temporal
            if 'data_entrada' in df.columns:
                st.subheader("📈 Análise Temporal")
                
                df_with_dates = df.dropna(subset=['data_entrada'])
                if not df_with_dates.empty:
                    # Entrada de deals por mês
                    df_with_dates['mes_entrada'] = df_with_dates['data_entrada'].dt.to_period('M')
                    monthly_deals = df_with_dates.groupby('mes_entrada').size()
                    
                    if len(monthly_deals) > 1:
                        fig_timeline = px.line(
                            x=monthly_deals.index.astype(str),
                            y=monthly_deals.values,
                            title="📅 Entrada de Deals por Mês",
                            labels={'x': 'Mês', 'y': 'Número de Deals'},
                            markers=True
                        )
                        fig_timeline.update_layout(height=400)
                        st.plotly_chart(fig_timeline, use_container_width=True)
                    else:
                        st.info("📊 Dados insuficientes para análise temporal (necessário pelo menos 2 meses)")
            
            # Tabela de resumo por BDR
            if 'bdr' in df.columns:
                st.subheader("👤 Performance Detalhada por BDR")
                
                bdr_summary = df.groupby('bdr').agg({
                    'etapa': ['count', lambda x: (x == 'ONB').sum()],
                    'dealname': 'count'
                }).round(2)
                
                bdr_summary.columns = ['Total Deals', 'Onboarding', 'Count']
                bdr_summary = bdr_summary.drop('Count', axis=1)
                bdr_summary['Taxa Sucesso (%)'] = (bdr_summary['Onboarding'] / bdr_summary['Total Deals'] * 100).round(1)
                bdr_summary['Deals Ativos'] = bdr_summary['Total Deals'] - bdr_summary['Onboarding']
                
                # Reordena colunas
                bdr_summary = bdr_summary[['Total Deals', 'Deals Ativos', 'Onboarding', 'Taxa Sucesso (%)']]
                
                st.dataframe(bdr_summary, use_container_width=True)
        else:
            st.info("📭 Dados insuficientes para análises avançadas")
    
    with tab5:
        st.header("🚨 Deals Atrasados")
        st.caption("Deals que passaram da data prevista de onboarding")
        
        late_deals = get_deals_late(df)
        
        if not late_deals.empty:
            # Métricas de atraso
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_late = len(late_deals)
                st.metric("🚨 Total Atrasados", total_late)
            
            with col2:
                critical_late = len(late_deals[late_deals['Urgência'].str.contains('Crítico')])
                st.metric("🔴 Críticos", critical_late)
            
            with col3:
                avg_delay = late_deals['Dias Atraso'].mean()
                st.metric("⏱️ Atraso Médio", f"{avg_delay:.1f} dias")
            
            with col4:
                max_delay = late_deals['Dias Atraso'].max()
                st.metric("📈 Maior Atraso", f"{max_delay} dias")
            
            # Filtro por urgência
            urgency_filter = st.selectbox(
                "🔍 Filtrar por Urgência:",
                ['Todos'] + list(late_deals['Urgência'].unique())
            )
            
            filtered_late = late_deals.copy()
            if urgency_filter != 'Todos':
                filtered_late = filtered_late[filtered_late['Urgência'] == urgency_filter]
            
            # Tabela de deals atrasados
            safe_display_dataframe(filtered_late, 
                                 f"🚨 {len(filtered_late)} Deals Atrasados", 
                                 height=500)
            
            # Análise por BDR dos atrasos
            if not late_deals.empty and 'BDR' in late_deals.columns:
                st.subheader("👤 Atrasos por BDR")
                
                bdr_delays = late_deals.groupby('BDR').agg({
                    'Dias Atraso': ['count', 'mean', 'max']
                }).round(1)
                
                bdr_delays.columns = ['Qtd Atrasados', 'Atraso Médio', 'Maior Atraso']
                
                st.dataframe(bdr_delays, use_container_width=True)
                
                # Gráfico de atrasos por BDR
                fig_delays = px.bar(
                    x=bdr_delays.index,
                    y=bdr_delays['Qtd Atrasados'],
                    title="📊 Quantidade de Deals Atrasados por BDR",
                    labels={'x': 'BDR', 'y': 'Deals Atrasados'},
                    color=bdr_delays['Atraso Médio'],
                    color_continuous_scale='Reds'
                )
                st.plotly_chart(fig_delays, use_container_width=True)
        else:
            st.success("🎉 Parabéns! Nenhum deal está atrasado no momento!")
            st.balloons()
    
    # Footer informativo
    st.divider()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.caption("🔄 Última atualização dos dados")
        st.caption(datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
    
    with col2:
        st.caption("📊 Fonte dos dados")
        st.caption("Google Sheets (ID: ...76LM)")
    
    with col3:
        st.caption("🎯 Total de registros")
        st.caption(f"{len(df)} deals no pipeline")
    
    with col4:
        st.caption("⚙️ Configuração atual")
        st.caption(f"Lead time: {sum(lead_times.values())} dias")

if __name__ == "__main__":
    main()
