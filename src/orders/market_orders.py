#!/usr/bin/env python3
"""
Market order implementation for Binance Futures
Executes immediate buy/sell orders at current market price
"""

import click
from typing import Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from ..client.binance_client import BinanceFuturesClient
    from ..utils.logger import logger
    from ..utils.config import config
except ImportError:
    from client.binance_client import BinanceFuturesClient
    from utils.logger import logger
    from utils.config import config

console = Console()

class MarketOrderManager:
    """Handles market order operations"""
    
    def __init__(self):
        self.client = BinanceFuturesClient()
    
    def execute_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """Execute a market order"""
        try:
            # Get current price for reference
            current_price = self.client.get_current_price(symbol)
            
            console.print(f"\n[yellow]Executing market order:[/yellow]")
            console.print(f"Symbol: [bold]{symbol}[/bold]")
            console.print(f"Side: [bold]{side}[/bold]")
            console.print(f"Quantity: [bold]{quantity}[/bold]")
            console.print(f"Current Price: [bold]${current_price:,.2f}[/bold]")
            
            # Confirm order
            if not self._confirm_order(symbol, side, quantity, current_price):
                console.print("[red]Order cancelled by user[/red]")
                return {"status": "CANCELLED", "reason": "User cancelled"}
            
            # Execute order
            with console.status("[bold green]Placing market order..."):
                order_result = self.client.place_market_order(symbol, side, quantity)
            
            # Display results
            self._display_order_result(order_result)
            
            return order_result
            
        except Exception as e:
            console.print(f"[red]Error executing market order: {str(e)}[/red]")
            logger.log_error(e, "execute_market_order")
            raise
    
    def _confirm_order(self, symbol: str, side: str, quantity: float, price: float) -> bool:
        """Confirm order with user"""
        estimated_value = quantity * price
        
        # Create confirmation table
        table = Table(title="Order Confirmation", show_header=True, header_style="bold magenta")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Symbol", symbol)
        table.add_row("Side", side)
        table.add_row("Quantity", f"{quantity:.6f}")
        table.add_row("Market Price", f"${price:,.2f}")
        table.add_row("Estimated Value", f"${estimated_value:,.2f}")
        table.add_row("Order Type", "MARKET")
        
        console.print(table)
        
        return click.confirm("\nDo you want to proceed with this market order?", default=True)
    
    def _display_order_result(self, order_result: Dict[str, Any]):
        """Display order execution results"""
        status = order_result.get('status', 'UNKNOWN')
        order_id = order_result.get('orderId', 'N/A')
        
        if status == 'FILLED':
            fill_price = float(order_result.get('avgPrice', 0))
            filled_qty = float(order_result.get('executedQty', 0))
            
            # Success panel
            success_content = f"""
[bold green]✓ Market Order Executed Successfully[/bold green]

Order ID: {order_id}
Status: {status}
Filled Quantity: {filled_qty:.6f}
Average Fill Price: ${fill_price:,.2f}
Total Value: ${fill_price * filled_qty:,.2f}
            """
            
            console.print(Panel(success_content, title="Order Result", border_style="green"))
            
        else:
            # Partial fill or pending
            console.print(Panel(
                f"Order ID: {order_id}\nStatus: {status}",
                title="Order Status",
                border_style="yellow"
            ))
    
    def get_market_summary(self, symbol: str) -> Dict[str, Any]:
        """Get market summary for symbol"""
        try:
            current_price = self.client.get_current_price(symbol)
            klines = self.client.get_klines(symbol, '1d', 1)
            
            if klines:
                open_price = float(klines[0][1])
                high_price = float(klines[0][2])
                low_price = float(klines[0][3])
                volume = float(klines[0][5])
                
                change_24h = ((current_price - open_price) / open_price) * 100
                
                return {
                    'symbol': symbol,
                    'current_price': current_price,
                    'open_24h': open_price,
                    'high_24h': high_price,
                    'low_24h': low_price,
                    'volume_24h': volume,
                    'change_24h': change_24h
                }
            
            return {'symbol': symbol, 'current_price': current_price}
            
        except Exception as e:
            logger.log_error(e, f"get_market_summary for {symbol}")
            return {}
    
    def display_market_summary(self, symbol: str):
        """Display market summary table"""
        summary = self.get_market_summary(symbol)
        
        if not summary:
            console.print(f"[red]Could not retrieve market data for {symbol}[/red]")
            return
        
        table = Table(title=f"{symbol} Market Summary", show_header=True, header_style="bold blue")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Current Price", f"${summary.get('current_price', 0):,.2f}")
        
        if 'open_24h' in summary:
            change_color = "green" if summary.get('change_24h', 0) >= 0 else "red"
            table.add_row("24h Open", f"${summary.get('open_24h', 0):,.2f}")
            table.add_row("24h High", f"${summary.get('high_24h', 0):,.2f}")
            table.add_row("24h Low", f"${summary.get('low_24h', 0):,.2f}")
            table.add_row("24h Change", f"[{change_color}]{summary.get('change_24h', 0):+.2f}%[/{change_color}]")
            table.add_row("24h Volume", f"{summary.get('volume_24h', 0):,.0f}")
        
        console.print(table)

# CLI Commands
@click.command()
@click.argument('symbol', type=str)
@click.argument('side', type=click.Choice(['BUY', 'SELL'], case_sensitive=False))
@click.argument('quantity', type=float)
@click.option('--no-confirm', is_flag=True, help='Skip confirmation prompt')
@click.option('--market-info', is_flag=True, help='Show market info before order')
def market_order(symbol: str, side: str, quantity: float, no_confirm: bool, market_info: bool):
    """
    Place a market order for the specified symbol.
    
    Examples:
        python market_orders.py BTCUSDT BUY 0.01
        python market_orders.py ETHUSDT SELL 0.1 --no-confirm
    """
    try:
        manager = MarketOrderManager()
        
        # Show market info if requested
        if market_info:
            manager.display_market_summary(symbol.upper())
            console.print()
        
        # Override confirmation if flag is set
        if no_confirm:
            manager._confirm_order = lambda *args: True
        
        # Execute order
        result = manager.execute_market_order(symbol.upper(), side.upper(), quantity)
        
        if result.get('status') != 'CANCELLED':
            console.print(f"\n[green]Market order completed![/green]")
        
    except Exception as e:
        console.print(f"\n[red]Failed to execute market order: {str(e)}[/red]")
        logger.log_error(e, "market_order_cli")
        raise click.ClickException(str(e))

@click.command()
@click.argument('symbol', type=str)
def market_info(symbol: str):
    """Display market information for a symbol"""
    try:
        manager = MarketOrderManager()
        manager.display_market_summary(symbol.upper())
    except Exception as e:
        console.print(f"[red]Error getting market info: {str(e)}[/red]")
        raise click.ClickException(str(e))

if __name__ == '__main__':
    market_order()