import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from streamlit.components.v1 import html

import os
import streamlit.web.cli as stcli
import sys
from streamlit.components.v1 import html

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
    
    return {
        'latest_price': latest_price,
        'SMA5': data['SMA5'].iloc[-1],
        'SMA50': data['SMA50'].iloc[-1],
        'SMA150': data['SMA150'].iloc[-1],
        'SMA200': data['SMA200'].iloc[-1],
        'VWAP_YearStart': year_start_data['VWAP_YearStart'].iloc[-1],
        'VWAP_RecentHigh': recent_high_data['VWAP_RecentHigh'].iloc[-1],
        'VWAP_RecentLow': recent_low_data['VWAP_RecentLow'].iloc[-1],
        'VWAP_Earnings': earnings_data['VWAP_Earnings'].iloc[-1] if earnings_data is not None else None,
        'current_volume': current_volume,
        'avg_volume_20d': avg_volume_20d
    }

def create_table(data):
    headers = [
        'TICKER', 'LAST', '5D SMA', '50D SMA', '150D SMA', '200D SMA',
        'VWAP YTD', 'VWAP HIGH', 'VWAP LOW', 'VWAP EARN', 'VOL/20D AVG'
    ]

    table_data = []
    cell_colors = []

    for ticker, values in data.items():
        row = [ticker, f"${values['latest_price']:.2f}"]
        row_colors = ['black', 'black']  # No background color for "TICKER" and "LAST" columns

        for key in ['SMA5', 'SMA50', 'SMA150', 'SMA200', 'VWAP_YearStart', 'VWAP_RecentHigh', 'VWAP_RecentLow', 'VWAP_Earnings']:
            if values[key] is not None:
                value = values[key]
                if value > values['latest_price']:
                    color = 'red'
                elif value < values['latest_price']:
                    color = 'green'
                else:
                    color = 'black'
                row.append(f"${value:.2f}")
                row_colors.append(color)
            else:
                row.append("N/A")
                row_colors.append('black')
        
        # Add volume comparison column
        volume_ratio = values['current_volume'] / values['avg_volume_20d']
        row.append(f"{volume_ratio:.2f}")
        if volume_ratio > 1:
            row_colors.append('darkorange')
        else:
            row_colors.append('black')

        table_data.append(row)
        cell_colors.append(row_colors)

    fig = go.Figure(data=[go.Table(
        header=dict(
            values=[f"<b>{h}</b>" for h in headers],
            fill_color='black',
            align='left',
            font=dict(color='#FF9933', size=18)  # Increased font size
        ),
        cells=dict(
            values=[list(col) for col in zip(*table_data)],  # Transpose the data
            align='left',
            font=dict(color='white', size=18),  # Increased font size and kept text color white
            fill=dict(color=[list(col) for col in zip(*cell_colors)]),  # Transpose the background colors
            height=40  # Increased cell height to accommodate larger text
        )
    )])

    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='black',
        plot_bgcolor='black',
        height=600
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
        font-size: 14px;
        padding: 5px 10px;
    }
    h1 {
        color: #FF9933;
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 20px;
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
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1>SKYHOOK スカイフック v0.1</h1>", unsafe_allow_html=True)
    
    # Input for stock tickers
    tickers_input = st.text_input("ENTER TICKERS (SPACE-SEPARATED):", key="tickers")
    
    # Instructions
    st.markdown("""
    **SHORTCUTS:**
    - PRESS `ENTER` TO ANALYZE
    - PRESS `ESC` TO CLEAR INPUT
    - PRESS `/` FOR SEARCH BAR
    """)
    
    # Keyboard shortcut handling
    js = """
    <script>
    const doc = window.parent.document;
    doc.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const inputField = doc.querySelector('.stTextInput input');
            if (inputField && inputField.value.trim() !== '') {
                inputField.blur();  // This is the key part that triggers submission in Streamlit
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
            else:
                st.warning("NO VALID DATA TO DISPLAY.")
    
    # Status bar
    st.markdown(
        "<div class='status-bar'>ENTER: ANALYZE | ESC: CLEAR | /: SEARCH</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    # Check if the script is being run directly
    if os.environ.get("STREAMLIT_SCRIPT_MODE") != "true":
        os.environ["STREAMLIT_SCRIPT_MODE"] = "true"
        os.system(f"{sys.executable} -m streamlit run '/Users/sebastian/Desktop/Skyhook System/main.py'")
    else:
        main()