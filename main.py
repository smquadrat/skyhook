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

    return {
        'latest_price': latest_price,
        'status': status,
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
    }

def create_table(data):
    headers = [
        'TICKER', 'STATUS', 'LAST', '5D SMA', '', '50D SMA', '', '150D SMA', '', '200D SMA', '',
        'VWAP YTD', '', 'VWAP H', '', 'VWAP L', '', 'VWAP E', '', 'VOL/20D AVG'
    ]

    table_data = []
    cell_colors = []
    font_colors = []

    for ticker, values in data.items():
        row = [
            ticker,
            values['status'],
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
            f"{values['current_volume'] / values['avg_volume_20d']:.2f}" if values['avg_volume_20d'] != 0 else 'N/A'
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
        
        # Set colors for SMA and VWAP columns
        value_indices = [3, 5, 7, 9, 11, 13, 15, 17]
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
        trend_indices = [4, 6, 8, 10, 12, 14, 16, 18]
        for i in trend_indices:
            if row[i] == 'R':
                row_colors[i] = 'green'
                row_font_colors[i] = 'white'
            elif row[i] == 'F':
                row_colors[i] = 'red'
                row_font_colors[i] = 'white'
        
        # Set color for volume comparison
        if row[-1] != 'N/A':
            try:
                if float(row[-1]) > 1:
                    row_colors[-1] = 'darkorange'
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
        25,  # LAST
        30, 10,  # 5D SMA and trend
        30, 10,  # 50D SMA and trend
        30, 10,  # 150D SMA and trend
        30, 10,  # 200D SMA and trend
        30, 10,  # VWAP YTD and trend
        30, 10,  # VWAP HIGH and trend
        30, 10,  # VWAP LOW and trend
        30, 10,  # VWAP EARN and trend
        40   # VOL/20D AVG
    ]

    column_alignment = [
        'left', # TICKER
        'center', # STATUS
        'right', # LAST
        'right', 'center', # 5D SMA and trend
        'right', 'center', # 50D SMA and trend
        'right', 'center', # 150D SMA and trend
        'right', 'center', # 200D SMA and trend
        'right', 'center', # VWAP YTD and trend
        'right', 'center', # VWAP HIGH and trend
        'right', 'center', # VWAP LOW and trend
        'right', 'center', # VWAP EARN and trend
        'center', # VOL/20D AVG
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

def main():
    st.set_page_config(page_title="Skyhook v0.1", layout="wide")
    
    # Custom CSS for Bloomberg Terminal look
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono&display=swap');
    body {
        background-color: black;
        color: #FF9933;
        font-family: 'Roboto Mono', monospace;
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
        margin: 0;  /* Remove default margin */
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
        padding: 20px 0;  /* Add padding to the top and bottom */
    }
    .info-button {
        background-color: #FF9933;
        color: black;
        border: none;
        padding: 5px 10px;
        font-size: 16px;  /* Match the size with the title */
        cursor: pointer;
        border-radius: 15px;
        transition: background-color 0.3s ease;
        height: 30px;  /* Set a specific height */
        line-height: 20px;  /* Adjust line height for vertical centering */
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
    </style>
    """, unsafe_allow_html=True)

    # Header with title and info button
    st.markdown("""
    <div class="header-container">
        <h1>SKYHOOK スカイフック v0.1</h1>
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
