import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from io import StringIO
import requests

# Configuração da página
st.set_page_config(
    page_title="Calculadora Pipeline CAX",
    page_icon="📊",
    layout="wide"
)

# Configurações globais
GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/1L0nO-rchxshEufLANyH3aEz6hFulvpq1OMPUzTw76LM/export?format=csv&gid=0"
ETAPAS_FUNIL = ['SAL', 'SQL', 'OPP', 'BC', 'ONB_AGEND', 'ONB']

@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_data():
    """Carrega dados do Google Sheets"""
    try:
        response = requests.get(GOOGLE_SHEETS_URL)
        response.raise_for_status()
        
        # Lê o CSV
        df = pd.read_csv(StringIO(response.text))
        
        # Limpeza básica dos dados
        df.columns = df.columns.str.strip()
        
        # Converte datas
        date_columns = ['data_entrada', 'data_prevista_onboarding']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Remove linhas vazias
        df = df.dropna(subset=['dealname'])
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

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
    """Calcula previsão de conversões"""
    if df.empty:
        return pd.DataFrame()
    
    # Configurações padrão
    lead_times = config.get('lead_times', {
        'SAL': 2, 'SQL': 3, 'OPP': 5, 'BC': 7, 'ONB_AGEND': 2, 'ONB': 0
    })
    conversion_rates = config.get('conversion_rates', {
        'SAL': 0.6, 'SQL': 0.7, 'OPP': 0.8, 'BC': 0.9, 'ONB_AGEND': 0.95, 'ONB': 1.0
    })
    
    # Próximos dias úteis
    next_days = get_next_business_days(15)
    results = []
    
    # Deals existentes
    for _, deal in df.iterrows():
        if deal['etapa'] not in ETAPAS_FUNIL or deal['etapa'] == 'ONB':
            continue
        
        # Data atual para cálculo
        base_date = datetime.now().date()
        if pd.notna(deal.get('data_entrada')):
            base_date = max(base_date, deal['data_entrada'].date())
        
        # Calcula conversão por etapa
        current_stage_idx = ETAPAS_FUNIL.index(deal['etapa'])
        probability = 1.0
        
        for stage_idx in range(current_stage_idx, len(ETAPAS_FUNIL)):
            stage = ETAPAS_FUNIL[stage_idx]
            if stage == 'ONB':
                break
                
            probability *= conversion_rates.get(stage, 0.5)
            lead_time = sum([lead_times.get(ETAPAS_FUNIL[i], 2) for i in range(current_stage_idx, stage_idx + 1)])
            
            conversion_date = add_business_days(base_date, lead_time)
            
            if conversion_date in next_days:
                results.append({
                    'data': conversion_date,
                    'deal': deal['dealname'],
                    'etapa_origem': deal['etapa'],
                    'etapa_destino': 'ONB',
                    'probabilidade': probability,
                    'bdr': deal.get('bdr', 'N/A'),
                    'tipo': 'Existente'
                })
    
    # Cenários de teste
    if test_scenarios:
        for scenario in test_scenarios:
            stage = scenario.get('etapa', 'SAL')
            quantity = scenario.get('quantidade', 1)
            target_date = scenario.get('data_entrada', datetime.now().date())
            
            if stage not in ETAPAS_FUNIL or stage == 'ONB':
                continue
            
            current_stage_idx = ETAPAS_FUNIL.index(stage)
            probability = 1.0
            
            for stage_idx in range(current_stage_idx, len(ETAPAS_FUNIL)):
                current_stage = ETAPAS_FUNIL[stage_idx]
                if current_stage == 'ONB':
                    break
                    
                probability *= conversion_rates.get(current_stage, 0.5)
                lead_time = sum([lead_times.get(ETAPAS_FUNIL[i], 2) for i in range(current_stage_idx, stage_idx + 1)])
                
                conversion_date = add_business_days(target_date, lead_time)
                
                if conversion_date in next_days:
                    for i in range(quantity):
                        results.append({
                            'data': conversion_date,
                            'deal': f"Cenário {scenario.get('nome', 'Teste')} #{i+1}",
                            'etapa_origem': stage,
                            'etapa_destino': 'ONB',
                            'probabilidade': probability,
                            'bdr': scenario.get('bdr', 'Teste'),
                            'tipo': 'Cenário'
                        })
    
    if not results:
        return pd.DataFrame()
    
    # Cria DataFrame dos resultados
    prediction_df = pd.DataFrame(results)
    
    # Agrupa por data
    summary = prediction_df.groupby('data').agg({
        'probabilidade': 'sum',
        'deal': 'count'
    }).round(2)
    
    summary.columns = ['Conversões Previstas', 'Total Deals']
    summary['Data'] = summary.index
    summary['Dia Semana'] = summary['Data'].apply(lambda x: x.strftime('%A'))
    summary['É Quarta'] = summary['Data'].apply(lambda x: x.weekday() == 2)
    
    # Reordena colunas
    summary = summary[['Data', 'Dia Semana', 'É Quarta', 'Conversões Previstas', 'Total Deals']].reset_index(drop=True)
    
    return summary

def safe_display_dataframe(df, title="", height=400):
    """Exibe DataFrame de forma segura sem formatação problemática"""
    if title:
        st.subheader(title)
    
    if df.empty:
        st.info("📭 Nenhum dado disponível")
        return
    
    try:
        # Destaca quartas-feiras de forma simples
        if 'É Quarta' in df.columns:
            # Cria uma cópia para exibição
            display_df = df.copy()
            
            # Adiciona emoji para quartas-feiras
            display_df.loc[display_df['É Quarta'] == True, 'Dia Semana'] = '🎯 ' + display_df.loc[display_df['É Quarta'] == True, 'Dia Semana']
            
            # Remove coluna booleana
            display_df = display_df.drop('É Quarta', axis=1)
            
            st.dataframe(display_df, use_container_width=True, height=height)
        else:
            st.dataframe(df, use_container_width=True, height=height)
            
    except Exception as e:
        st.warning(f"⚠️ Problema na formatação: {str(e)[:100]}")
        st.dataframe(df, use_container_width=True, height=height)

def create_conversion_chart(df):
    """Cria gráfico de conversões previstas"""
    if df.empty:
        return None
    
    fig = go.Figure()
    
    # Barras normais
    normal_days = df[df['É Quarta'] == False]
    if not normal_days.empty:
        fig.add_trace(go.Bar(
            x=normal_days['Data'],
            y=normal_days['Conversões Previstas'],
            name='Dias Normais',
            marker_color='#1f77b4',
            hovertemplate='<b>%{x}</b><br>Conversões: %{y:.1f}<extra></extra>'
        ))
    
    # Barras para quartas-feiras
    wednesdays = df[df['É Quarta'] == True]
    if not wednesdays.empty:
        fig.add_trace(go.Bar(
            x=wednesdays['Data'],
            y=wednesdays['Conversões Previstas'],
            name='🎯 Quartas-feiras (ONB)',
            marker_color='#ff7f0e',
            hovertemplate='<b>%{x} (Quarta-feira)</b><br>Conversões: %{y:.1f}<extra></extra>'
        ))
    
    fig.update_layout(
        title='📈 Previsão de Conversões por Dia',
        xaxis_title='Data',
        yaxis_title='Conversões Previstas',
        hovermode='x unified',
        showlegend=True
    )
    
    return fig

def get_deals_late(df):
    """Identifica deals atrasados"""
    if df.empty:
        return pd.DataFrame()
    
    today = datetime.now().date()
    
    # Deals com data prevista passada
    late_deals = df[
        (pd.notna(df['data_prevista_onboarding'])) &
        (df['data_prevista_onboarding'].dt.date < today) &
        (df['etapa'] != 'ONB')
    ].copy()
    
    if late_deals.empty:
        return pd.DataFrame()
    
    # Calcula dias de atraso
    late_deals['dias_atraso'] = (today - late_deals['data_prevista_onboarding'].dt.date).dt.days
    
    # Classifica urgência
    def classify_urgency(days):
        if days >= 7:
            return '🔴 Crítico'
        elif days >= 3:
            return '🟡 Atenção'
        else:
            return '🟢 Baixo'
    
    late_deals['urgencia'] = late_deals['dias_atraso'].apply(classify_urgency)
    
    # Seleciona e ordena colunas
    result = late_deals[[
        'dealname', 'etapa', 'data_prevista_onboarding', 
        'dias_atraso', 'urgencia', 'bdr'
    ]].sort_values('dias_atraso', ascending=False)
    
    result.columns = ['Deal', 'Etapa', 'Data Prevista', 'Dias Atraso', 'Urgência', 'BDR']
    
    return result

def main():
    # Título
    st.title("📊 Calculadora Pipeline CAX")
    st.markdown("*Dashboard e previsões de conversão em tempo real*")
    
    # Sidebar - Configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Atualização automática
        auto_refresh = st.checkbox("🔄 Auto-atualização (5min)", value=True)
        if auto_refresh:
            st.rerun()
        
        st.divider()
        
        # Configurações de conversão
        st.subheader("📈 Taxas de Conversão")
        conversion_rates = {}
        for etapa in ETAPAS_FUNIL[:-1]:  # Exclui ONB
            conversion_rates[etapa] = st.slider(
                f"{etapa}", 0.0, 1.0, 
                value={'SAL': 0.6, 'SQL': 0.7, 'OPP': 0.8, 'BC': 0.9, 'ONB_AGEND': 0.95}.get(etapa, 0.5),
                step=0.05,
                key=f"conv_{etapa}"
            )
        
        st.divider()
        
        # Lead times
        st.subheader("⏱️ Lead Times (dias úteis)")
        lead_times = {}
        for etapa in ETAPAS_FUNIL[:-1]:  # Exclui ONB
            lead_times[etapa] = st.number_input(
                f"{etapa}", min_value=0, max_value=30,
                value={'SAL': 2, 'SQL': 3, 'OPP': 5, 'BC': 7, 'ONB_AGEND': 2}.get(etapa, 2),
                key=f"lead_{etapa}"
            )
    
    # Carrega dados
    with st.spinner("📥 Carregando dados..."):
        df = load_data()
    
    if df.empty:
        st.error("❌ Não foi possível carregar os dados do Google Sheets")
        return
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_deals = len(df[df['etapa'] != 'ONB'])
        st.metric("📋 Deals Ativos", total_deals)
    
    with col2:
        deals_onb = len(df[df['etapa'] == 'ONB'])
        st.metric("✅ Onboardings", deals_onb)
    
    with col3:
        deals_bc = len(df[df['etapa'] == 'BC'])
        st.metric("🔥 Business Case", deals_bc)
    
    with col4:
        if total_deals > 0:
            conversion_rate = (deals_onb / (total_deals + deals_onb)) * 100
            st.metric("📊 Taxa Conversão", f"{conversion_rate:.1f}%")
        else:
            st.metric("📊 Taxa Conversão", "0%")
    
    # Abas principais
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Previsões", "🧪 Cenários", "📋 Deals", "📊 Análises"])
    
    with tab1:
        st.header("📅 Previsão de Conversões - Próximos 15 dias úteis")
        
        # Filtros
        col1, col2 = st.columns(2)
        with col1:
            bdrs = ['Todos'] + list(df['bdr'].dropna().unique())
            selected_bdr = st.selectbox("👤 Filtrar por BDR", bdrs)
        
        with col2:
            etapas = ['Todas'] + ETAPAS_FUNIL
            selected_etapa = st.selectbox("🎯 Filtrar por Etapa", etapas)
        
        # Aplica filtros
        filtered_df = df.copy()
        if selected_bdr != 'Todos':
            filtered_df = filtered_df[filtered_df['bdr'] == selected_bdr]
        if selected_etapa != 'Todas':
            filtered_df = filtered_df[filtered_df['etapa'] == selected_etapa]
        
        # Calcula previsões
        config = {
            'conversion_rates': conversion_rates,
            'lead_times': lead_times
        }
        
        prediction_df = calculate_conversion_prediction(filtered_df, config)
        
        if not prediction_df.empty:
            # Gráfico
            chart = create_conversion_chart(prediction_df)
            if chart:
                st.plotly_chart(chart, use_container_width=True)
            
            # Tabela
            safe_display_dataframe(prediction_df, "📊 Detalhes das Previsões")
            
            # Resumo
            total_conversoes = prediction_df['Conversões Previstas'].sum()
            quartas_conversoes = prediction_df[prediction_df['É Quarta'] == True]['Conversões Previstas'].sum()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🎯 Total Previsto", f"{total_conversoes:.1f}")
            with col2:
                st.metric("📅 Em Quartas-feiras", f"{quartas_conversoes:.1f}")
            with col3:
                if total_conversoes > 0:
                    perc_quartas = (quartas_conversoes / total_conversoes) * 100
                    st.metric("📊 % em Quartas", f"{perc_quartas:.1f}%")
        else:
            st.info("📭 Nenhuma conversão prevista com os filtros atuais")
    
    with tab2:
        st.header("🧪 Teste de Cenários")
        st.markdown("*Simule novos deals e veja o impacto nas previsões*")
        
        # Formulário para cenários
        with st.form("scenario_form"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                scenario_name = st.text_input("📝 Nome do Cenário", "Cenário Teste")
                scenario_stage = st.selectbox("🎯 Etapa Inicial", ETAPAS_FUNIL[:-1])
            
            with col2:
                scenario_quantity = st.number_input("📊 Quantidade de Deals", min_value=1, max_value=100, value=5)
                scenario_bdr = st.text_input("👤 BDR", "Teste")
            
            with col3:
                scenario_date = st.date_input("📅 Data de Entrada", datetime.now().date())
                submit_scenario = st.form_submit_button("🚀 Simular Cenário")
        
        if submit_scenario:
            # Cria cenário
            test_scenarios = [{
                'nome': scenario_name,
                'etapa': scenario_stage,
                'quantidade': scenario_quantity,
                'bdr': scenario_bdr,
                'data_entrada': scenario_date
            }]
            
            # Calcula previsão com cenário
            scenario_prediction = calculate_conversion_prediction(df, config, test_scenarios)
            
            if not scenario_prediction.empty:
                st.success(f"✅ Cenário '{scenario_name}' simulado com sucesso!")
                
                # Mostra apenas deals do cenário
                scenario_only = scenario_prediction[scenario_prediction['Total Deals'] > 0]
                
                if not scenario_only.empty:
                    # Gráfico do cenário
                    chart = create_conversion_chart(scenario_only)
                    if chart:
                        st.plotly_chart(chart, use_container_width=True)
                    
                    # Tabela do cenário
                    safe_display_dataframe(scenario_only, f"📊 Impacto do Cenário: {scenario_name}")
                    
                    # Métricas do cenário
                    col1, col2 = st.columns(2)
                    with col1:
                        total_scenario = scenario_only['Conversões Previstas'].sum()
                        st.metric("🎯 Conversões Previstas", f"{total_scenario:.1f}")
                    with col2:
                        scenario_wednesdays = scenario_only[scenario_only['É Quarta'] == True]['Conversões Previstas'].sum()
                        st.metric("📅 Em Quartas-feiras", f"{scenario_wednesdays:.1f}")
            else:
                st.warning("⚠️ O cenário não gerou previsões no período analisado")
    
    with tab3:
        st.header("📋 Lista Completa de Deals")
        
        # Filtros
        col1, col2 = st.columns(2)
        with col1:
            bdrs_filter = ['Todos'] + list(df['bdr'].dropna().unique())
            bdr_filter = st.selectbox("👤 BDR", bdrs_filter, key="deals_bdr")
        
        with col2:
            etapas_filter = ['Todas'] + ETAPAS_FUNIL
            etapa_filter = st.selectbox("🎯 Etapa", etapas_filter, key="deals_etapa")
        
        # Aplica filtros
        deals_df = df.copy()
        if bdr_filter != 'Todos':
            deals_df = deals_df[deals_df['bdr'] == bdr_filter]
        if etapa_filter != 'Todas':
            deals_df = deals_df[deals_df['etapa'] == etapa_filter]
        
        # Deals atrasados
        late_deals = get_deals_late(deals_df)
        if not late_deals.empty:
            st.subheader("🚨 Deals Atrasados")
            safe_display_dataframe(late_deals, height=300)
            st.divider()
        
        # Lista geral
        if not deals_df.empty:
            # Preparar dados para exibição
            display_cols = ['dealname', 'etapa', 'bdr', 'data_entrada', 'data_prevista_onboarding']
            available_cols = [col for col in display_cols if col in deals_df.columns]
            
            deals_display = deals_df[available_cols].copy()
            
            # Renomear colunas
            column_rename = {
                'dealname': 'Deal',
                'etapa': 'Etapa',
                'bdr': 'BDR',
                'data_entrada': 'Data Entrada',
                'data_prevista_onboarding': 'Data Prev. ONB'
            }
            deals_display = deals_display.rename(columns=column_rename)
            
            safe_display_dataframe(deals_display, f"📊 Total: {len(deals_display)} deals")
        else:
            st.info("📭 Nenhum deal encontrado com os filtros aplicados")
    
    with tab4:
        st.header("📊 Análises Avançadas")
        
        if not df.empty:
            # Distribuição por etapa
            col1, col2 = st.columns(2)
            
            with col1:
                etapa_counts = df['etapa'].value_counts()
                fig_pie = px.pie(
                    values=etapa_counts.values,
                    names=etapa_counts.index,
                    title="📊 Distribuição por Etapa"
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                # Análise por BDR
                if 'bdr' in df.columns:
                    bdr_counts = df.groupby('bdr')['etapa'].count().sort_values(ascending=False)
                    fig_bar = px.bar(
                        x=bdr_counts.index,
                        y=bdr_counts.values,
                        title="👤 Deals por BDR",
                        labels={'x': 'BDR', 'y': 'Número de Deals'}
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
            
            # Evolução temporal
            if 'data_entrada' in df.columns:
                df_with_dates = df.dropna(subset=['data_entrada'])
                if not df_with_dates.empty:
                    df_with_dates['mes'] = df_with_dates['data_entrada'].dt.to_period('M')
                    monthly_deals = df_with_dates.groupby('mes').size()
                    
                    fig_line = px.line(
                        x=monthly_deals.index.astype(str),
                        y=monthly_deals.values,
                        title="📈 Evolução de Deals por Mês",
                        labels={'x': 'Mês', 'y': 'Número de Deals'}
                    )
                    st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("📭 Dados insuficientes para análises")
    
    # Footer
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption("🔄 Atualização automática a cada 5 minutos")
    with col2:
        st.caption("📊 Dados: Google Sheets")
    with col3:
        st.caption(f"🕒 Última atualização: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()
