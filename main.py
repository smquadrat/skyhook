import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from streamlit.components.v1 import html

import os
import sys

def calculate_vwap(data):
    return (data['Close'] * data['Volume']).cumsum() / data['Volume'].cumsum()

def get_stock_data(ticker):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)  # 1 year ago
    data = yf.download(ticker, start=start_date, end=end_date, interval="1d")
    
    latest_data = yf.download(ticker, period="1d", interval="1m")
    latest_price = latest_data['Close'].iloc[-1]
    current_volume = latest_data['Volume'].sum()
    
    data['SMA5'] = data['Close'].rolling(window=5).mean()
    data['SMA50'] = data['Close'].rolling(window=50).mean()
    data['SMA150'] = data['Close'].rolling(window=150).mean()
    data['SMA200'] = data['Close'].rolling(window=200).mean()
    
    # Calculate 20-day average volume
    avg_volume_20d = data['Volume'].rolling(window=20).mean().iloc[-1]
    
    year_start = pd.Timestamp(f'{datetime.now().year}-01-01')
    year_start_data = data[data.index >= year_start].copy()
    year_start_data['VWAP_YearStart'] = calculate_vwap(year_start_data)
    
    recent_high_date = data['Close'].idxmax()
    recent_high_data = data[data.index >= recent_high_date].copy()
    recent_high_data['VWAP_RecentHigh'] = calculate_vwap(recent_high_data)
    
    recent_low_date = data['Close'].idxmin()
    recent_low_data = data[data.index >= recent_low_date].copy()
    recent_low_data['VWAP_RecentLow'] = calculate_vwap(recent_low_data)
    
    ticker_info = yf.Ticker(ticker)
    earnings_dates = ticker_info.earnings_dates
    if earnings_dates is not None and not earnings_dates.empty:
        earnings_dates.index = pd.to_datetime(earnings_dates.index)
        current_time = datetime.now().astimezone(earnings_dates.index.tz)
        latest_past_earnings_date = earnings_dates.index[earnings_dates.index <= current_time].max()
        
        if latest_past_earnings_date.tzinfo:
            latest_past_earnings_date = latest_past_earnings_date.tz_localize(None)
        
        if latest_past_earnings_date <= data.index[-1]:
            earnings_data = data[data.index >= latest_past_earnings_date].copy()
            if not earnings_data.empty:
                earnings_data['VWAP_Earnings'] = calculate_vwap(earnings_data)
            else:
                earnings_data = None
        else:
            earnings_data = None
    else:
        earnings_data = None

    sma5 = data['SMA5'].iloc[-1]
    sma50 = data['SMA50'].iloc[-1]
    sma150 = data['SMA150'].iloc[-1]
    sma200 = data['SMA200'].iloc[-1]
    vwap_ytd = year_start_data['VWAP_YearStart'].iloc[-1]
    vwap_high = recent_high_data['VWAP_RecentHigh'].iloc[-1]
    vwap_low = recent_low_data['VWAP_RecentLow'].iloc[-1]
    vwap_earnings = earnings_data['VWAP_Earnings'].iloc[-1] if earnings_data is not None else None

    # Determine status
    if latest_price < sma5:
        status = 'AVOID'
    elif latest_price > sma5 and latest_price > sma50 and latest_price > sma150 and latest_price > sma200 and \
         latest_price > vwap_ytd and latest_price > vwap_low and \
         (vwap_earnings is None or latest_price > vwap_earnings) and \
         all(data[col].iloc[-1] > data[col].iloc[-2] for col in ['SMA5', 'SMA50', 'SMA150', 'SMA200']) and \
         year_start_data['VWAP_YearStart'].iloc[-1] > year_start_data['VWAP_YearStart'].iloc[-2] and \
         recent_low_data['VWAP_RecentLow'].iloc[-1] > recent_low_data['VWAP_RecentLow'].iloc[-2] and \
         (earnings_data is None or earnings_data['VWAP_Earnings'].iloc[-1] > earnings_data['VWAP_Earnings'].iloc[-2]):
        status = 'CLEAR'
    elif latest_price > sma5 and data['SMA5'].iloc[-1] <= data['SMA5'].iloc[-2]:
        status = 'CAUTION'
    else:
        status = ''

    # Calculate P/Sales and P/FCF
    stock = yf.Ticker(ticker)
    market_cap = stock.info.get('marketCap')
    
    income_stmt = stock.quarterly_financials.T
    cashflow_stmt = stock.quarterly_cashflow.T
    
    revenue_col = 'Total Revenue'
    free_cash_flow_col = 'Free Cash Flow'
    
    if revenue_col in income_stmt.columns and free_cash_flow_col in cashflow_stmt.columns:
        income_stmt = income_stmt.sort_index(ascending=False)
        cashflow_stmt = cashflow_stmt.sort_index(ascending=False)
        
        ttm_revenue = income_stmt[revenue_col].head(4).sum()
        ttm_free_cash_flow = cashflow_stmt[free_cash_flow_col].head(4).sum()
        
        p_s_ratio = market_cap / ttm_revenue if ttm_revenue and ttm_revenue != 0 else None
        p_fcf_ratio = market_cap / ttm_free_cash_flow if ttm_free_cash_flow and ttm_free_cash_flow != 0 else None

        # Calculate TTM trends
        prev_ttm_revenue = income_stmt[revenue_col].iloc[1:5].sum()
        prev_ttm_fcf = cashflow_stmt[free_cash_flow_col].iloc[1:5].sum()

        ttm_revenue_trend = 'R' if ttm_revenue > prev_ttm_revenue else 'F'
        ttm_fcf_trend = 'R' if ttm_free_cash_flow > prev_ttm_fcf else 'F'
    else:
        p_s_ratio = None
        p_fcf_ratio = None
        ttm_revenue_trend = None
        ttm_fcf_trend = None

    # Get the next earnings date
    earnings_dates = ticker_info.earnings_dates
    next_earnings_date = None
    days_to_earnings = None

    if earnings_dates is not None and not earnings_dates.empty:
        earnings_dates.index = pd.to_datetime(earnings_dates.index)
        current_time = datetime.now().astimezone(earnings_dates.index.tz)
        future_earnings_dates = earnings_dates.index[earnings_dates.index > current_time]
        
        if not future_earnings_dates.empty:
            next_earnings_date = future_earnings_dates.min()
            
            if next_earnings_date.tzinfo:
                next_earnings_date = next_earnings_date.tz_localize(None)
            
            days_to_earnings = (next_earnings_date - pd.Timestamp.now()).days

    return {
        'latest_price': latest_price,
        'status': status,
        'days_to_earnings': days_to_earnings,
        'SMA5': sma5,
        'SMA5_trend': 'R' if data['SMA5'].iloc[-1] > data['SMA5'].iloc[-2] else 'F',
        'SMA50': sma50,
        'SMA50_trend': 'R' if data['SMA50'].iloc[-1] > data['SMA50'].iloc[-2] else 'F',
        'SMA150': sma150,
        'SMA150_trend': 'R' if data['SMA150'].iloc[-1] > data['SMA150'].iloc[-2] else 'F',
        'SMA200': sma200,
        'SMA200_trend': 'R' if data['SMA200'].iloc[-1] > data['SMA200'].iloc[-2] else 'F',
        'VWAP_YearStart': vwap_ytd,
        'VWAP_YearStart_trend': 'R' if year_start_data['VWAP_YearStart'].iloc[-1] > year_start_data['VWAP_YearStart'].iloc[-2] else 'F',
        'VWAP_RecentHigh': vwap_high,
        'VWAP_RecentHigh_trend': 'R' if recent_high_data['VWAP_RecentHigh'].iloc[-1] > recent_high_data['VWAP_RecentHigh'].iloc[-2] else 'F',
        'VWAP_RecentLow': vwap_low,
        'VWAP_RecentLow_trend': 'R' if recent_low_data['VWAP_RecentLow'].iloc[-1] > recent_low_data['VWAP_RecentLow'].iloc[-2] else 'F',
        'VWAP_Earnings': vwap_earnings,
        'VWAP_Earnings_trend': 'R' if earnings_data is not None and earnings_data['VWAP_Earnings'].iloc[-1] > earnings_data['VWAP_Earnings'].iloc[-2] else 'F' if earnings_data is not None else None,
        'current_volume': current_volume,
        'avg_volume_20d': avg_volume_20d,
        'P/S': p_s_ratio,
        'P/S_trend': ttm_revenue_trend,
        'P/FCF': p_fcf_ratio,
        'P/FCF_trend': ttm_fcf_trend
    }

def create_table(data):
    headers = [
        'TICKER', 'STATUS', 'E', 'LAST', '5D SMA', '', '50D SMA', '', '150D SMA', '', '200D SMA', '',
        'VWAP YTD', '', 'VWAP H', '', 'VWAP L', '', 'VWAP E', '', 'VOL/20D AVG', 'P/S', '', 'P/FCF', ''
    ]

    table_data = []
    cell_colors = []
    font_colors = []

    for ticker, values in data.items():
        row = [
            ticker,
            values['status'],
            str(values['days_to_earnings']) if values['days_to_earnings'] is not None else 'N/A',
            f"{values['latest_price']:.2f}",
            f"{values['SMA5']:.2f}" if values['SMA5'] != 'N/A' else 'N/A', values['SMA5_trend'],
            f"{values['SMA50']:.2f}" if values['SMA50'] != 'N/A' else 'N/A', values['SMA50_trend'],
            f"{values['SMA150']:.2f}" if values['SMA150'] != 'N/A' else 'N/A', values['SMA150_trend'],
            f"{values['SMA200']:.2f}" if values['SMA200'] != 'N/A' else 'N/A', values['SMA200_trend'],
            f"{values['VWAP_YearStart']:.2f}" if values['VWAP_YearStart'] != 'N/A' else 'N/A', values['VWAP_YearStart_trend'],
            f"{values['VWAP_RecentHigh']:.2f}" if values['VWAP_RecentHigh'] != 'N/A' else 'N/A', values['VWAP_RecentHigh_trend'],
            f"{values['VWAP_RecentLow']:.2f}" if values['VWAP_RecentLow'] != 'N/A' else 'N/A', values['VWAP_RecentLow_trend'],
            f"{values['VWAP_Earnings']:.2f}" if values['VWAP_Earnings'] not in ['N/A', None] else 'N/A',
            values['VWAP_Earnings_trend'] if values['VWAP_Earnings_trend'] else '',
            f"{values['current_volume'] / values['avg_volume_20d']:.2f}" if values['avg_volume_20d'] != 0 else 'N/A',
            f"{values['P/S']:.1f}" if values['P/S'] not in ['N/A', None] else 'N/A',
            values['P/S_trend'] if values['P/S_trend'] else '',
            f"{values['P/FCF']:.1f}" if values['P/FCF'] not in ['N/A', None] else 'N/A',
            values['P/FCF_trend'] if values['P/FCF_trend'] else ''
        ]
        
        row_colors = ['black'] * len(row)
        row_font_colors = ['white'] * len(row)
        
        # Set colors for STATUS column
        if values['status'] == 'AVOID':
            row_colors[1] = 'red'
            row_font_colors[1] = 'white'
        elif values['status'] == 'CLEAR':
            row_colors[1] = 'green'
            row_font_colors[1] = 'white'
        elif values['status'] == 'CAUTION':
            row_colors[1] = 'darkorange'
            row_font_colors[1] = 'white'
        
        # Set color for 'E' column
        if values['days_to_earnings'] is not None and values['days_to_earnings'] <= 21:
            row_colors[2] = 'darkorange'
            row_font_colors[2] = 'white'
        
        # Set colors for SMA and VWAP columns
        value_indices = [4, 6, 8, 10, 12, 14, 16, 18]
        for i in value_indices:
            if row[i] != 'N/A' and values['latest_price'] != 'N/A':
                try:
                    if float(row[i].replace('$', '')) > values['latest_price']:
                        row_colors[i] = 'red'
                    elif float(row[i].replace('$', '')) < values['latest_price']:
                        row_colors[i] = 'green'
                except ValueError:
                    # If conversion fails, leave the color as black
                    pass
        
        # Set colors for trend columns
        trend_indices = [5, 7, 9, 11, 13, 15, 17, 19, 22, 24]
        for i in trend_indices:
            if row[i] == 'R':
                row_colors[i] = 'green'
                row_font_colors[i] = 'white'
            elif row[i] == 'F':
                row_colors[i] = 'red'
                row_font_colors[i] = 'white'
        
        # Set color for volume comparison
        if row[-5] != 'N/A':
            try:
                if float(row[-5]) > 1:
                    row_colors[-5] = 'darkorange'
            except ValueError:
                # If conversion fails, leave the color as black
                pass
        
        table_data.append(row)
        cell_colors.append(row_colors)
        font_colors.append(row_font_colors)

    # Define column widths
    column_widths = [
        25,  # TICKER
        30,  # STATUS
        15,  # E (Days to Earnings)
        25,  # LAST
        30, 10,  # 5D SMA and trend
        30, 10,  # 50D SMA and trend
        30, 10,  # 150D SMA and trend
        30, 10,  # 200D SMA and trend
        30, 10,  # VWAP YTD and trend
        30, 10,  # VWAP HIGH and trend
        30, 10,  # VWAP LOW and trend
        30, 10,  # VWAP EARN and trend
        40,  # VOL/20D AVG
        20, 10,  # P/S and trend
        20, 10   # P/FCF and trend
    ]

    column_alignment = [
        'left',   # TICKER
        'center', # STATUS
        'center', # E (Days to Earnings)
        'right',  # LAST
        'right', 'center', # 5D SMA and trend
        'right', 'center', # 50D SMA and trend
        'right', 'center', # 150D SMA and trend
        'right', 'center', # 200D SMA and trend
        'right', 'center', # VWAP YTD and trend
        'right', 'center', # VWAP HIGH and trend
        'right', 'center', # VWAP LOW and trend
        'right', 'center', # VWAP EARN and trend
        'center', # VOL/20D AVG
        'right', 'center', # P/S and trend
        'right', 'center'  # P/FCF and trend
    ]

    fig = go.Figure(data=[go.Table(
        header=dict(
            values=[f"<b>{h}</b>" for h in headers],
            fill_color='black',
            align=column_alignment,
            font=dict(color='#FF9933', size=18),
            height=40
        ),
        cells=dict(
            values=[list(col) for col in zip(*table_data)],
            align=column_alignment,
            font=dict(color=[list(col) for col in zip(*font_colors)], size=18),
            fill=dict(color=[list(col) for col in zip(*cell_colors)]),
            height=30,
            line_color='darkslategray',
            line_width=1
        ),
        columnwidth=column_widths
    )])

    # Calculate the total width of all columns
    total_width = sum(column_widths)

    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='black',
        plot_bgcolor='black',
        height=len(data) * 30 + 40,  # Adjust table height based on number of rows
        width=max(total_width * 5, 1000),  # Set a minimum width for the table
        autosize=False,
        font=dict(size=18),  # Increase overall font size
    )

    return fig

def get_vix_data():
    tickers = ["^VIX", "VXX", "VXZ", "QQQ", "SPY"]
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)  # Fetch 1 year of data to ensure enough for 150-day MA
    data = yf.download(tickers, start=start_date, end=end_date)
    
    vix_data = data['Close']['^VIX']
    vxx_data = data['Close']['VXX']
    vxz_data = data['Close']['VXZ']
    qqq_data = data['Close']['QQQ']
    spy_data = data['Close']['SPY']
    
    vix_spot = vix_data.iloc[-1]
    vxx_price = vxx_data.iloc[-1]
    vxz_price = vxz_data.iloc[-1]
    qqq_price = qqq_data.iloc[-1]
    spy_price = spy_data.iloc[-1]
    
    vix_ma20 = vix_data.rolling(window=20).mean().iloc[-1]
    vxx_ma20 = vxx_data.rolling(window=20).mean().iloc[-1]
    vxz_ma20 = vxz_data.rolling(window=20).mean().iloc[-1]
    
    vix_ratio = vix_spot / vix_ma20
    vxx_ratio = vxx_price / vxx_ma20
    vxz_ratio = vxz_price / vxz_ma20

    # Calculate SMAs for QQQ and SPY
    qqq_sma5 = qqq_data.rolling(window=5).mean().iloc[-1]
    qqq_sma150 = qqq_data.rolling(window=150).mean().iloc[-1]
    spy_sma5 = spy_data.rolling(window=5).mean().iloc[-1]
    spy_sma150 = spy_data.rolling(window=150).mean().iloc[-1]

    # Determine short-term and long-term trends
    qqq_st = 'green' if qqq_price > qqq_sma5 else 'red'
    qqq_lt = 'green' if qqq_price > qqq_sma150 else 'red'
    spy_st = 'green' if spy_price > spy_sma5 else 'red'
    spy_lt = 'green' if spy_price > spy_sma150 else 'red'

    # Debug output
    print(f"QQQ Price: {qqq_price:.2f}, QQQ 5 SMA: {qqq_sma5:.2f}, QQQ 150 SMA: {qqq_sma150:.2f}, QQQ ST Color: {qqq_st}, QQQ LT Color: {qqq_lt}")
    print(f"SPY Price: {spy_price:.2f}, SPY 5 SMA: {spy_sma5:.2f}, SPY 150 SMA: {spy_sma150:.2f}, SPY ST Color: {spy_st}, SPY LT Color: {spy_lt}")
    
    return vix_spot, vxx_price, vxz_price, vix_ratio, vxx_ratio, vxz_ratio, qqq_price, qqq_st, qqq_lt, spy_price, spy_st, spy_lt, qqq_sma5, qqq_sma150, spy_sma5, spy_sma150

def main():
    st.set_page_config(page_title="Skyhook v0.2", layout="wide")
    
# Update the CSS to include styles for spacing
    st.markdown("""
    <style>
    body {
        background-color: black;
        color: #FF9933;
        font-family: 'Arial', monospace;
        font-size: 14px;
    }
    .stApp {
        background-color: black;
    }
    .stTextInput>div>div>input {
        color: #FF9933;
        background-color: black;
        border: 1px solid #FF9933;
        border-radius: 0px;
        font-family: 'Roboto Mono', monospace;
        font-size: 16px;
        padding: 5px 10px;
        text-transform: uppercase;
    }
    h1 {
        color: #FF9933;
        font-size: 24px;
        font-weight: bold;
        margin: 0;
    }
    .status-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: #FF9933;
        color: black;
        padding: 5px 10px;
        font-size: 12px;
        font-weight: bold;
        z-index: 1000;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .status-bar a {
        color: black;
        text-decoration: none;
    }
    .status-bar a:hover {
        text-decoration: underline;
    }
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 0;
    }
    .info-button {
        background-color: #FF9933;
        color: black;
        border: none;
        padding: 5px 10px;
        font-size: 16px;
        cursor: pointer;
        border-radius: 15px;
        transition: background-color 0.3s ease;
        height: 30px;
        line-height: 20px;
    }
    .info-button:hover {
        background-color: #E68A00;
    }
    .info-section {
        display: none;
        position: fixed;
        bottom: 30px;
        left: 0;
        right: 0;
        background-color: #1E1E1E;
        color: #FF9933;
        padding: 20px;
        border-top: 1px solid #FF9933;
        z-index: 999;
    }
    .info-content {
        display: flex;
        justify-content: space-between;
    }
    .info-column {
        flex: 1;
        padding: 0 10px;
    }
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 0;
    }
    .vix-container {
        display: flex;
        justify-content: center;
        align-items: center;
    }
    .vix-box {
        padding: 5px 10px;
        border-radius: 5px;
        font-weight: bold;
        text-align: center;
        margin: 0 5px;
        font-size: 14px;
    }
    .title-and-vix {
        display: flex;
        align-items: center;
    }
    .spacer {
        width: 30px;  /* Adjust this value to increase or decrease spacing */
    }
    </style>
    """, unsafe_allow_html=True)

    # Fetch VIX, QQQ, and SPY data
    vix_spot, vxx_price, vxz_price, vix_ratio, vxx_ratio, vxz_ratio, qqq_price, qqq_st, qqq_lt, spy_price, spy_st, spy_lt, qqq_sma5, qqq_sma150, spy_sma5, spy_sma150 = get_vix_data()

    # Determine colors based on conditions
    vix_color = "red" if vix_spot > vxx_price or vix_spot > vxz_price else "green"
    vxx_color = "red" if vxx_price > vxz_price else "green"

    # Ensure LT colors are set correctly
    qqq_lt = 'green' if qqq_price > qqq_sma150 else 'red' if not pd.isna(qqq_sma150) else 'gray'
    spy_lt = 'green' if spy_price > spy_sma150 else 'red' if not pd.isna(spy_sma150) else 'gray'

    # Header with title, VIX boxes, QQQ and SPY boxes, and info button
    st.markdown(f"""
    <div class="header-container">
        <div class="title-and-vix">
            <h1>SKYHOOK スカイフック v0.2</h1>
            <div class="vix-container">
                <div class="vix-box" style="background-color: {vix_color}; color: white;">
                    VIX: {vix_spot:.2f} [{vix_ratio:.2f}]
                </div>
                <div class="vix-box" style="background-color: {vxx_color}; color: white;">
                    VXX: {vxx_price:.2f} [{vxx_ratio:.2f}]
                </div>
                <div class="vix-box" style="background-color: black; color: #FF9933; border: 1px solid #FF9933;">
                    VXZ: {vxz_price:.2f} [{vxz_ratio:.2f}]
                </div>
                <div class="spacer"></div>
                <div class="vix-box" style="background-color: black; color: #FF9933; border: 1px solid #FF9933;">
                    QQQ: {qqq_price:.2f}
                </div>
                <div class="vix-box" style="background-color: {qqq_st}; color: white;">
                    ST
                </div>
                <div class="vix-box" style="background-color: {qqq_lt}; color: white;">
                    LT
                </div>
                <div class="spacer"></div>
                <div class="vix-box" style="background-color: black; color: #FF9933; border: 1px solid #FF9933;">
                    SPY: {spy_price:.2f}
                </div>
                <div class="vix-box" style="background-color: {spy_st}; color: white;">
                    ST
                </div>
                <div class="vix-box" style="background-color: {spy_lt}; color: white;">
                    LT
                </div>
            </div>
        </div>
        <button class="info-button" onclick="toggleInfo()">Press i for info</button>
    </div>
    """, unsafe_allow_html=True)

    # Info section (initially hidden)
    st.markdown("""
    <div id="info-section" class="info-section">
        <div class="info-content">
            <div class="info-column">
                <strong>SHORTCUTS:</strong><br>
                - PRESS `/` FOR SEARCH BAR<br>
                - PRESS `ESC` TO CLEAR INPUT<br>
                - PRESS `ENTER` TO ANALYZE
            </div>
            <div class="info-column">
                <strong>VWAPs:</strong><br>
                - YTD: Anchored on start of current year<br>
                - H: Anchored on recent high<br>
                - L: Anchored on recent low<br>
                - E: Anchored on last quarterly earnings
            </div>
            <div class="info-column">
                <strong>TREND LETTERS:</strong><br>
                - R: Rising trend<br>
                - F: Falling trend
            </div>
            <div class="info-column">
                <strong>Status:</strong><br>
                - Avoid: Refrain from accumulating<br>
                - Caution: Proceed cautiously<br>
                - Clear: Safe to accumulate
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Input for stock tickers
    tickers_input = st.text_input("ENTER TICKERS (SPACE-SEPARATED):", key="tickers")
    
    # Keyboard shortcut handling
    js = """
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        const doc = window.parent.document;
        function toggleInfo() {
            const infoSection = doc.getElementById('info-section');
            infoSection.style.display = infoSection.style.display === 'none' ? 'block' : 'none';
        }
        doc.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const inputField = doc.querySelector('.stTextInput input');
                if (inputField && inputField.value.trim() !== '') {
                    inputField.blur();
                    inputField.form.requestSubmit();
                }
            } else if (e.key === 'Escape') {
                e.preventDefault();
                const inputField = doc.querySelector('.stTextInput input');
                if (inputField) {
                    inputField.value = '';
                    inputField.dispatchEvent(new Event('input', { bubbles: true }));
                }
            } else if (e.key === '/') {
                e.preventDefault();
                const inputField = doc.querySelector('.stTextInput input');
                if (inputField) inputField.focus();
            } else if (e.key === 'i' || e.key === 'I') {
                toggleInfo();
            }
        });
    });
    </script>
    """
    html(js, height=0)
    
    if tickers_input:
        tickers = [ticker.strip().upper() for ticker in tickers_input.split() if ticker.strip()]
        with st.spinner("FETCHING DATA..."):
            data = {}
            for ticker in tickers:
                try:
                    data[ticker] = get_stock_data(ticker)
                except Exception as e:
                    st.error(f"ERROR FETCHING DATA FOR {ticker}: {str(e)}")
            
            if data:
                fig = create_table(data)
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
                # Add custom CSS for horizontal scrolling
                st.markdown("""
                <style>
                .stPlotlyChart {
                    overflow-x: auto;
                    white-space: nowrap;
                }
                </style>
                """, unsafe_allow_html=True)
            else:
                st.warning("NO VALID DATA TO DISPLAY.")
    
    # Status bar
    st.markdown(
        """
        <div class='status-bar'>
            <div>i: TOGGLE INFO | /: SEARCH | ESC: CLEAR | ENTER: ANALYZE </div>
            <div>&copy 2024 <a href="https://www.sebastianquadrat.com" target="_blank">Sebastian Quadrat</a></div>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    # Check if the script is being run directly
    if os.environ.get("STREAMLIT_SCRIPT_MODE") != "true":
        os.environ["STREAMLIT_SCRIPT_MODE"] = "true"
        os.system(f"{sys.executable} -m streamlit run '{__file__}'")
    else:
        main()