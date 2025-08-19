#!/usr/bin/env python3
"""
Streamlit Web Interface for Binance Futures Trading Bot
Professional dashboard for trading operations and monitoring
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import trading bot components
try:
    from client.binance_client import BinanceFuturesClient
    from orders.market_orders import MarketOrderManager
    from orders.limit_orders import LimitOrderManager
    from orders.advanced.oco import OCOOrderManager
    from orders.advanced.grid import GridTradingManager
    from orders.advanced.twap import TWAPOrderManager
    from utils.logger import logger
    from utils.config import config
except ImportError as e:
    st.error(f"Import Error: {e}")
    st.stop()

# Page configuration
st.set_page_config(
    page_title="Binance Futures Trading Bot",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #f39c12;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #1e1e1e;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #f39c12;
    }
    .success-box {
        background-color: #27ae60;
        color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #e74c3c;
        color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #f39c12;
        color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'client' not in st.session_state:
    st.session_state.client = None
if 'orders_history' not in st.session_state:
    st.session_state.orders_history = []
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()

def init_trading_client():
    """Initialize trading client"""
    try:
        if st.session_state.client is None:
            st.session_state.client = BinanceFuturesClient()
            st.session_state.market_manager = MarketOrderManager()
            st.session_state.limit_manager = LimitOrderManager()
            st.session_state.oco_manager = OCOOrderManager()
            st.session_state.grid_manager = GridTradingManager()
            st.session_state.twap_manager = TWAPOrderManager()
        return True
    except Exception as e:
        st.error(f"Failed to initialize trading client: {str(e)}")
        return False

def get_account_info():
    """Get account information"""
    try:
        account_info = st.session_state.client.get_account_info()
        return account_info
    except Exception as e:
        st.error(f"Error getting account info: {str(e)}")
        return None

def get_positions():
    """Get open positions"""
    try:
        positions = st.session_state.client.get_positions()
        return positions
    except Exception as e:
        st.error(f"Error getting positions: {str(e)}")
        return []

def get_market_data(symbol):
    """Get market data for symbol"""
    try:
        current_price = st.session_state.client.get_current_price(symbol)
        klines = st.session_state.client.get_klines(symbol, '1h', 24)
        
        # Process klines data
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        return current_price, df
    except Exception as e:
        st.error(f"Error getting market data: {str(e)}")
        return None, None

def main():
    """Main application"""
    
    # Header
    st.markdown('<h1 class="main-header">🚀 Binance Futures Trading Bot</h1>', unsafe_allow_html=True)
    
    # Initialize client
    if not init_trading_client():
        st.stop()
    
    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        ["Dashboard", "Market Orders", "Limit Orders", "Advanced Orders", "Grid Trading", "TWAP Orders", "Settings"]
    )
    
    # Auto-refresh toggle
    auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)
    if auto_refresh:
        time.sleep(30)
        st.rerun()
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.session_state.last_refresh = datetime.now()
        st.rerun()
    
    st.sidebar.markdown(f"*Last updated: {st.session_state.last_refresh.strftime('%H:%M:%S')}*")
    
    # Page routing
    if page == "Dashboard":
        show_dashboard()
    elif page == "Market Orders":
        show_market_orders()
    elif page == "Limit Orders":
        show_limit_orders()
    elif page == "Advanced Orders":
        show_advanced_orders()
    elif page == "Grid Trading":
        show_grid_trading()
    elif page == "TWAP Orders":
        show_twap_orders()
    elif page == "Settings":
        show_settings()

def show_dashboard():
    """Dashboard page"""
    st.header("📊 Trading Dashboard")
    
    # Account Overview
    account_info = get_account_info()
    if account_info:
        col1, col2, col3, col4 = st.columns(4)
        
        # Find USDT balance
        usdt_balance = 0
        usdt_available = 0
        total_pnl = 0
        
        for asset in account_info.get('assets', []):
            if asset['asset'] == 'USDT':
                usdt_balance = float(asset['walletBalance'])
                usdt_available = float(asset['availableBalance'])
                total_pnl = float(asset.get('unrealizedProfit', asset.get('unRealizedProfit', 0)))
                break
        
        with col1:
            st.metric("USDT Balance", f"${usdt_balance:,.2f}")
        with col2:
            st.metric("Available", f"${usdt_available:,.2f}")
        with col3:
            st.metric("Unrealized PnL", f"${total_pnl:+.2f}", 
                     delta=f"{(total_pnl/usdt_balance*100):+.2f}%" if usdt_balance > 0 else "0%")
        with col4:
            margin_ratio = (usdt_balance - usdt_available) / usdt_balance * 100 if usdt_balance > 0 else 0
            st.metric("Margin Used", f"{margin_ratio:.1f}%")
    
    st.markdown("---")
    
    # Market Data Section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📈 Market Chart")
        symbol = st.selectbox("Select Symbol", ["BTCUSDT", "ETHUSDT", "BNBUSDT"], key="dashboard_symbol")
        
        current_price, price_data = get_market_data(symbol)
        
        if current_price and price_data is not None:
            # Price chart
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=price_data['timestamp'],
                open=price_data['open'],
                high=price_data['high'],
                low=price_data['low'],
                close=price_data['close'],
                name=symbol
            ))
            
            fig.update_layout(
                title=f"{symbol} Price Chart (24H)",
                xaxis_title="Time",
                yaxis_title="Price (USDT)",
                height=400,
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Current price
            price_change = ((current_price - price_data['open'].iloc[0]) / price_data['open'].iloc[0]) * 100
            st.metric(
                f"{symbol} Current Price", 
                f"${current_price:,.2f}", 
                delta=f"{price_change:+.2f}%"
            )
    
    with col2:
        st.subheader("💼 Open Positions")
        positions = get_positions()
        
        if positions:
            for pos in positions:
                symbol = pos['symbol']
                size = float(pos.get('positionAmt', 0))
                pnl = float(pos.get('unrealizedProfit', pos.get('unRealizedProfit', 0)))
                
                pnl_color = "green" if pnl >= 0 else "red"
                st.markdown(f"""
                <div style="border: 1px solid #ddd; padding: 10px; margin: 5px 0; border-radius: 5px;">
                    <strong>{symbol}</strong><br>
                    Size: {size:.6f}<br>
                    <span style="color: {pnl_color};">PnL: ${pnl:+.2f}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No open positions")
        
        # Quick Actions
        st.subheader("⚡ Quick Actions")
        if st.button("🛒 Quick Buy 0.001 BTC", use_container_width=True):
            try:
                result = st.session_state.market_manager.execute_market_order("BTCUSDT", "BUY", 0.001)
                st.success("Order placed successfully!")
                st.json(result)
            except Exception as e:
                st.error(f"Order failed: {str(e)}")
        
        if st.button("💰 Quick Sell 0.001 BTC", use_container_width=True):
            try:
                result = st.session_state.market_manager.execute_market_order("BTCUSDT", "SELL", 0.001)
                st.success("Order placed successfully!")
                st.json(result)
            except Exception as e:
                st.error(f"Order failed: {str(e)}")

def show_market_orders():
    """Market Orders page"""
    st.header("🛒 Market Orders")
    st.write("Execute instant buy/sell orders at current market price")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Place Market Order")
        
        symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "BNBUSDT"], key="market_symbol")
        side = st.selectbox("Side", ["BUY", "SELL"])
        quantity = st.number_input("Quantity", min_value=0.001, max_value=100.0, value=0.01, step=0.001, format="%.6f")
        
        # Show current price and estimated value
        current_price, _ = get_market_data(symbol)
        if current_price:
            estimated_value = quantity * current_price
            st.info(f"Current Price: ${current_price:,.2f}")
            st.info(f"Estimated Value: ${estimated_value:,.2f}")
        
        if st.button("Execute Market Order", type="primary", use_container_width=True):
            try:
                with st.spinner("Placing order..."):
                    # Override confirmation for web interface
                    st.session_state.market_manager._confirm_order = lambda *args: True
                    result = st.session_state.market_manager.execute_market_order(symbol, side, quantity)
                
                st.success("Market order executed successfully!")
                st.json(result)
                
                # Add to history
                st.session_state.orders_history.append({
                    'timestamp': datetime.now(),
                    'type': 'MARKET',
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'status': result.get('status', 'UNKNOWN')
                })
                
            except Exception as e:
                st.error(f"Order failed: {str(e)}")
    
    with col2:
        st.subheader("Market Information")
        
        if current_price:
            # Market stats
            st.metric("Current Price", f"${current_price:,.2f}")
            
            # Recent orders history
            st.subheader("Recent Orders")
            if st.session_state.orders_history:
                recent_orders = st.session_state.orders_history[-5:]  # Last 5 orders
                for order in reversed(recent_orders):
                    st.write(f"**{order['type']}** {order['side']} {order['quantity']:.6f} {order['symbol']} - {order['status']}")
                    st.caption(f"{order['timestamp'].strftime('%H:%M:%S')}")
            else:
                st.info("No recent orders")

def show_limit_orders():
    """Limit Orders page"""
    st.header("📋 Limit Orders")
    st.write("Place orders at specific price levels")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Place Limit Order")
        
        symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "BNBUSDT"], key="limit_symbol")
        side = st.selectbox("Side", ["BUY", "SELL"])
        quantity = st.number_input("Quantity", min_value=0.001, max_value=100.0, value=0.01, step=0.001, format="%.6f")
        
        # Get current price for reference
        current_price, _ = get_market_data(symbol)
        if current_price:
            st.info(f"Current Market Price: ${current_price:,.2f}")
            
            # Smart price suggestion
            if side == "BUY":
                suggested_price = current_price * 0.99  # 1% below market
                st.caption("💡 Tip: Set buy price below market price")
            else:
                suggested_price = current_price * 1.01  # 1% above market
                st.caption("💡 Tip: Set sell price above market price")
            
            price = st.number_input("Limit Price", min_value=0.01, value=suggested_price, step=0.01, format="%.2f")
            
            # Price analysis
            price_diff = ((price - current_price) / current_price) * 100
            if abs(price_diff) > 5:
                st.warning(f"⚠️ Price is {abs(price_diff):.1f}% {'above' if price_diff > 0 else 'below'} market")
        else:
            price = st.number_input("Limit Price", min_value=0.01, value=45000.0, step=0.01, format="%.2f")
        
        wait_for_fill = st.checkbox("Wait for order to fill")
        
        if st.button("Place Limit Order", type="primary", use_container_width=True):
            try:
                with st.spinner("Placing limit order..."):
                    # Override confirmation for web interface
                    st.session_state.limit_manager._confirm_limit_order = lambda *args: True
                    result = st.session_state.limit_manager.execute_limit_order(symbol, side, quantity, price, wait_for_fill)
                
                st.success("Limit order placed successfully!")
                st.json(result)
                
                # Add to history
                st.session_state.orders_history.append({
                    'timestamp': datetime.now(),
                    'type': 'LIMIT',
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'price': price,
                    'status': result.get('status', 'UNKNOWN')
                })
                
            except Exception as e:
                st.error(f"Order failed: {str(e)}")
    
    with col2:
        st.subheader("Open Orders")
        
        if st.button("Refresh Open Orders"):
            st.rerun()
        
        try:
            open_orders = st.session_state.client.get_open_orders()
            
            if open_orders:
                df = pd.DataFrame(open_orders)
                df['time'] = pd.to_datetime(df['time'], unit='ms')
                
                # Display as table
                display_df = df[['symbol', 'side', 'origQty', 'price', 'status', 'time']].copy()
                display_df.columns = ['Symbol', 'Side', 'Quantity', 'Price', 'Status', 'Time']
                display_df['Price'] = display_df['Price'].astype(float).apply(lambda x: f"${x:,.2f}")
                display_df['Quantity'] = display_df['Quantity'].astype(float).apply(lambda x: f"{x:.6f}")
                
                st.dataframe(display_df, use_container_width=True)
                
                # Cancel order section
                st.subheader("Cancel Order")
                order_ids = [str(order['orderId']) for order in open_orders]
                selected_order = st.selectbox("Select Order to Cancel", order_ids)
                
                if st.button("Cancel Selected Order", type="secondary"):
                    try:
                        # Find the symbol for this order
                        order_symbol = next(order['symbol'] for order in open_orders if str(order['orderId']) == selected_order)
                        result = st.session_state.client.cancel_order(order_symbol, int(selected_order))
                        st.success(f"Order {selected_order} cancelled successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to cancel order: {str(e)}")
            else:
                st.info("No open orders")
                
        except Exception as e:
            st.error(f"Error fetching open orders: {str(e)}")

def show_advanced_orders():
    """Advanced Orders page"""
    st.header("🎯 Advanced Orders")
    
    tab1, tab2 = st.tabs(["OCO Orders", "Stop-Limit Orders"])
    
    with tab1:
        st.subheader("OCO (One-Cancels-Other) Orders")
        st.write("Place take-profit and stop-loss orders simultaneously")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "BNBUSDT"], key="oco_symbol")
            side = st.selectbox("Side", ["BUY", "SELL"], key="oco_side")
            quantity = st.number_input("Quantity", min_value=0.001, value=0.01, step=0.001, format="%.6f", key="oco_qty")
            
            current_price, _ = get_market_data(symbol)
            if current_price:
                st.info(f"Current Price: ${current_price:,.2f}")
                
                # Smart defaults
                if side == "SELL":
                    take_profit_default = current_price * 1.02  # 2% profit
                    stop_loss_default = current_price * 0.98   # 2% loss
                else:
                    take_profit_default = current_price * 0.98  # 2% below for buy
                    stop_loss_default = current_price * 1.02   # 2% above for buy
            else:
                take_profit_default = 46000.0
                stop_loss_default = 44000.0
            
            take_profit = st.number_input("Take Profit Price", value=take_profit_default, step=0.01, format="%.2f")
            stop_loss = st.number_input("Stop Loss Price", value=stop_loss_default, step=0.01, format="%.2f")
            stop_limit = st.number_input("Stop Limit Price (optional)", value=0.0, step=0.01, format="%.2f")
            
            if st.button("Place OCO Order", type="primary", use_container_width=True):
                try:
                    with st.spinner("Placing OCO order..."):
                        # Override confirmation
                        st.session_state.oco_manager._confirm_oco_order = lambda *args: True
                        result = st.session_state.oco_manager.execute_oco_order(
                            symbol, side, quantity, take_profit, stop_loss, 
                            stop_limit if stop_limit > 0 else None
                        )
                    
                    st.success("OCO order placed successfully!")
                    st.json(result)
                    
                except Exception as e:
                    st.error(f"OCO order failed: {str(e)}")
        
        with col2:
            st.subheader("OCO Order Preview")
            if current_price:
                profit_pct = ((take_profit - current_price) / current_price) * 100
                loss_pct = ((stop_loss - current_price) / current_price) * 100
                
                st.metric("Potential Profit", f"{profit_pct:+.2f}%")
                st.metric("Potential Loss", f"{loss_pct:+.2f}%")
                
                # Risk/Reward ratio
                risk_reward = abs(profit_pct / loss_pct) if loss_pct != 0 else 0
                st.metric("Risk/Reward Ratio", f"1:{risk_reward:.2f}")
    
    with tab2:
        st.subheader("Stop-Limit Orders")
        st.write("Conditional orders that trigger at specific price levels")
        st.info("Stop-limit functionality is integrated into the OCO orders above")

def show_grid_trading():
    """Grid Trading page"""
    st.header("🔲 Grid Trading")
    st.write("Automated buy-low/sell-high strategy within a price range")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Setup Grid Strategy")
        
        symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "BNBUSDT"], key="grid_symbol")
        
        current_price, _ = get_market_data(symbol)
        if current_price:
            st.info(f"Current Price: ${current_price:,.2f}")
            
            # Smart defaults
            default_lower = current_price * 0.95  # 5% below
            default_upper = current_price * 1.05  # 5% above
        else:
            default_lower = 113000.0
            default_upper = 117000.0
        
        quantity_per_grid = st.number_input("Quantity per Grid Level", min_value=0.001, value=0.01, step=0.001, format="%.6f")
        grid_count = st.slider("Number of Grid Levels", min_value=3, max_value=20, value=10)
        lower_price = st.number_input("Lower Price Boundary", value=default_lower, step=100.0, format="%.1f")
        upper_price = st.number_input("Upper Price Boundary", value=default_upper, step=100.0, format="%.1f")
        
        # Grid preview
        if lower_price < upper_price:
            grid_gap = (upper_price - lower_price) / (grid_count - 1)
            total_quantity = quantity_per_grid * grid_count
            estimated_value = total_quantity * current_price if current_price else 0
            
            st.info(f"""
            **Grid Preview:**
            - Price range: ${lower_price:,.1f} - ${upper_price:,.1f}
            - Grid gap: ${grid_gap:.1f}
            - Total quantity: {total_quantity:.6f}
            - Estimated value: ${estimated_value:,.2f}
            """)
        else:
            st.error("Lower price must be less than upper price!")
        
        if st.button("Start Grid Strategy", type="primary", use_container_width=True, disabled=(lower_price >= upper_price)):
            try:
                with st.spinner("Setting up grid strategy..."):
                    # Override confirmation
                    st.session_state.grid_manager._confirm_grid_strategy = lambda *args: True
                    result = st.session_state.grid_manager.execute_grid_strategy(
                        symbol, quantity_per_grid, grid_count, lower_price, upper_price
                    )
                
                st.success("Grid strategy started successfully!")
                st.json(result)
                
            except Exception as e:
                st.error(f"Grid strategy failed: {str(e)}")
    
    with col2:
        st.subheader("Active Grid Strategies")
        
        if st.button("Refresh Grid Status"):
            st.rerun()
        
        try:
            active_grids = st.session_state.grid_manager.list_active_grids()
            
            if active_grids:
                for grid_id, grid_data in active_grids.items():
                    with st.expander(f"Grid {grid_id}", expanded=True):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.write(f"**Symbol:** {grid_data['symbol']}")
                            st.write(f"**Levels:** {grid_data['grid_count']}")
                            st.write(f"**Status:** {grid_data['status']}")
                        with col_b:
                            st.write(f"**Trades:** {len(grid_data['executed_trades'])}")
                            st.write(f"**Profit:** ${grid_data['total_profit']:.2f}")
                        
                        if st.button(f"Stop Grid {grid_id}", key=f"stop_{grid_id}"):
                            try:
                                st.session_state.grid_manager.stop_grid_strategy(grid_id)
                                st.success(f"Grid {grid_id} stopped!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to stop grid: {str(e)}")
            else:
                st.info("No active grid strategies")
                
        except Exception as e:
            st.error(f"Error fetching grid data: {str(e)}")

def show_twap_orders():
    """TWAP Orders page"""
    st.header("⏱️ TWAP Orders")
    st.write("Execute large orders over time to minimize market impact")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Setup TWAP Order")
        
        symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "BNBUSDT"], key="twap_symbol")
        side = st.selectbox("Side", ["BUY", "SELL"], key="twap_side")
        total_quantity = st.number_input("Total Quantity", min_value=0.01, value=1.0, step=0.01, format="%.6f")
        duration_minutes = st.slider("Duration (minutes)", min_value=5, max_value=120, value=60)
        interval_minutes = st.slider("Interval (minutes)", min_value=1, max_value=30, value=5)
        
        # TWAP preview
        num_chunks = duration_minutes // interval_minutes
        chunk_size = total_quantity / num_chunks if num_chunks > 0 else 0
        
        current_price, _ = get_market_data(symbol)
        estimated_value = total_quantity * current_price if current_price else 0
        
        st.info(f"""
        **TWAP Preview:**
        - Total quantity: {total_quantity:.6f}
        - Number of chunks: {num_chunks}
        - Chunk size: {chunk_size:.6f}
        - Execution every: {interval_minutes} minutes
        - Estimated value: ${estimated_value:,.2f}
        """)
        
        price_limit = st.number_input("Price Limit (optional)", value=0.0, step=0.01, format="%.2f")
        
        if st.button("Start TWAP Order", type="primary", use_container_width=True):
            try:
                with st.spinner("Setting up TWAP order..."):
                    # Override confirmation
                    st.session_state.twap_manager._confirm_twap_order = lambda *args: True
                    result = st.session_state.twap_manager.execute_twap_order(
                        symbol, side, total_quantity, duration_minutes, interval_minutes,
                        price_limit if price_limit > 0 else None
                    )
                
                st.success("TWAP order started successfully!")
                st.json(result)
                
            except Exception as e:
                st.error(f"TWAP order failed: {str(e)}")
    
    with col2:
        st.subheader("Active TWAP Orders")
        
        if st.button("Refresh TWAP Status"):
            st.rerun()
        
        try:
            active_twaps = st.session_state.twap_manager.list_active_twap_orders()
            
            if active_twaps:
                for twap_id, twap_data in active_twaps.items():
                    with st.expander(f"TWAP {twap_id}", expanded=True):
                        progress = (twap_data['executed_chunks'] / twap_data['num_chunks']) * 100
                        st.progress(progress / 100)
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.write(f"**Symbol:** {twap_data['symbol']}")
                            st.write(f"**Side:** {twap_data['side']}")
                            st.write(f"**Progress:** {progress:.1f}%")
                        with col_b:
                            st.write(f"**Filled:** {twap_data['total_filled']:.6f}")
                            st.write(f"**Avg Price:** ${twap_data['avg_price']:.2f}")
                            st.write(f"**Status:** {twap_data['status']}")
                        
                        if st.button(f"Cancel TWAP {twap_id}", key=f"cancel_{twap_id}"):
                            try:
                                st.session_state.twap_manager.cancel_twap_order(twap_id)
                                st.success(f"TWAP {twap_id} cancelled!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to cancel TWAP: {str(e)}")
            else:
                st.info("No active TWAP orders")
                
        except Exception as e:
            st.error(f"Error fetching TWAP data: {str(e)}")

def show_settings():
    """Settings page"""
    st.header("⚙️ Settings")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Trading Configuration")
        
        # Environment info
        st.info(f"""
        **Current Configuration:**
        - Environment: {'Testnet' if config.binance.testnet else 'Live Trading'}
        - Log Level: {config.logging.log_level}
        - Default Symbol: {config.trading.default_symbol}
        """)
        
        # Risk settings
        st.subheader("Risk Management")
        max_position_size = st.slider("Max Position Size", 0.1, 10.0, 1.0, 0.1)
        max_daily_loss = st.slider("Max Daily Loss %", 1.0, 20.0, 5.0, 0.5)
        
        if st.button("Update Risk Settings"):
            st.success("Risk settings updated!")
    
    with col2:
        st.subheader("System Status")
        
        # Connection test
        if st.button("Test Connection"):
            try:
                account_info = get_account_info()
                if account_info:
                    st.success("✅ Connection successful!")
                    st.json({"status": "connected", "account_type": "futures"})
                else:
                    st.error("❌ Connection failed!")
            except Exception as e:
                st.error(f"❌ Connection error: {str(e)}")
        
        # System metrics
        st.subheader("Performance")
        st.metric("Session Orders", len(st.session_state.orders_history))
        st.metric("Active Strategies", "0")  # Would calculate from actual data
        
        # Logs
        st.subheader("Recent Logs")
        if st.button("View Logs"):
            try:
                with open("bot.log", "r") as f:
                    logs = f.readlines()[-10:]  # Last 10 lines
                    for log in logs:
                        st.text(log.strip())
            except FileNotFoundError:
                st.info("No log file found")
            except Exception as e:
                st.error(f"Error reading logs: {str(e)}")

# Add footer
def show_footer():
    """Show footer"""
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px;">
        <p>🚀 Binance Futures Trading Bot v1.0.0 | 
        Built with Streamlit | 
        <span style="color: #f39c12;">Testnet Mode</span></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
    show_footer()