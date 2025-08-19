#!/usr/bin/env python3
"""
Limit order implementation for Binance Futures
Places orders at specific price levels with execution controls
"""

import click
import time
from typing import Dict, Any, Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
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

class LimitOrderManager:
    """Handles limit order operations"""
    
    def __init__(self):
        self.client = BinanceFuturesClient()
    
    def execute_limit_order(self, symbol: str, side: str, quantity: float, 
                           price: float, wait_for_fill: bool = False) -> Dict[str, Any]:
        """Execute a limit order"""
        try:
            # Get current market price for comparison
            current_price = self.client.get_current_price(symbol)
            price_diff_pct = ((price - current_price) / current_price) * 100
            
            console.print(f"\n[yellow]Executing limit order:[/yellow]")
            
            # Create order details table
            table = Table(title="Limit Order Details", show_header=True, header_style="bold cyan")
            table.add_column("Parameter", style="cyan")
            table.add_column("Value", style="white")
            
            table.add_row("Symbol", symbol)
            table.add_row("Side", side)
            table.add_row("Quantity", f"{quantity:.6f}")
            table.add_row("Limit Price", f"${price:,.2f}")
            table.add_row("Current Market Price", f"${current_price:,.2f}")
            
            # Color code price difference
            diff_color = "green" if price_diff_pct > 0 else "red"
            table.add_row("Price Difference", f"[{diff_color}]{price_diff_pct:+.2f}%[/{diff_color}]")
            table.add_row("Estimated Value", f"${price * quantity:,.2f}")
            
            console.print(table)
            
            # Warn if price is far from market
            if abs(price_diff_pct) > 5:
                warning_msg = f"⚠️  Limit price is {abs(price_diff_pct):.1f}% {'above' if price_diff_pct > 0 else 'below'} market price"
                console.print(f"[yellow]{warning_msg}[/yellow]")
            
            # Confirm order
            if not self._confirm_limit_order(symbol, side, quantity, price, current_price):
                console.print("[red]Order cancelled by user[/red]")
                return {"status": "CANCELLED", "reason": "User cancelled"}
            
            # Execute order
            with console.status("[bold green]Placing limit order..."):
                order_result = self.client.place_limit_order(symbol, side, quantity, price)
            
            # Display initial result
            self._display_order_result(order_result)
            
            # Wait for fill if requested
            if wait_for_fill and order_result.get('status') != 'FILLED':
                order_result = self._wait_for_fill(symbol, order_result.get('orderId'), price)
            
            return order_result
            
        except Exception as e:
            console.print(f"[red]Error executing limit order: {str(e)}[/red]")
            logger.log_error(e, "execute_limit_order")
            raise
    
    def _confirm_limit_order(self, symbol: str, side: str, quantity: float, 
                            price: float, current_price: float) -> bool:
        """Confirm limit order with user"""
        
        # Determine order type based on price vs market
        if side.upper() == 'BUY':
            order_type = "Limit Buy (will execute when price drops to or below limit)"
            favorable = price < current_price
        else:
            order_type = "Limit Sell (will execute when price rises to or above limit)"
            favorable = price > current_price
        
        console.print(f"\n[bold]{order_type}[/bold]")
        
        if favorable:
            console.print("[green]✓ Limit price is favorable (better than current market)[/green]")
        else:
            console.print("[yellow]⚠ Limit price may execute immediately (market order-like)[/yellow]")
        
        return click.confirm("\nDo you want to proceed with this limit order?", default=True)
    
    def _display_order_result(self, order_result: Dict[str, Any]):
        """Display order execution results"""
        status = order_result.get('status', 'UNKNOWN')
        order_id = order_result.get('orderId', 'N/A')
        
        if status == 'FILLED':
            fill_price = float(order_result.get('avgPrice', 0))
            filled_qty = float(order_result.get('executedQty', 0))
            
            success_content = f"""
[bold green]✓ Limit Order Filled Immediately[/bold green]

Order ID: {order_id}
Status: {status}
Filled Quantity: {filled_qty:.6f}
Fill Price: ${fill_price:,.2f}
Total Value: ${fill_price * filled_qty:,.2f}
            """
            
            console.print(Panel(success_content, title="Order Filled", border_style="green"))
            
        elif status == 'NEW':
            pending_content = f"""
[bold yellow]⏳ Limit Order Placed Successfully[/bold yellow]

Order ID: {order_id}
Status: Waiting for execution
The order will execute when market price reaches your limit price.
            """
            
            console.print(Panel(pending_content, title="Order Pending", border_style="yellow"))
            
        else:
            console.print(Panel(
                f"Order ID: {order_id}\nStatus: {status}",
                title="Order Status",
                border_style="blue"
            ))
    
    def _wait_for_fill(self, symbol: str, order_id: int, limit_price: float, 
                      timeout: int = 300) -> Dict[str, Any]:
        """Wait for order to fill with progress indicator"""
        console.print(f"\n[yellow]Waiting for order {order_id} to fill...[/yellow]")
        
        start_time = time.time()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            task = progress.add_task(
                f"Monitoring order {order_id} (limit: ${limit_price:,.2f})", 
                total=None
            )
            
            while time.time() - start_time < timeout:
                try:
                    # Check order status
                    order_status = self.client.get_order_status(symbol, order_id)
                    current_price = self.client.get_current_price(symbol)
                    
                    # Update progress description
                    progress.update(
                        task, 
                        description=f"Order {order_id} | Market: ${current_price:,.2f} | Limit: ${limit_price:,.2f}"
                    )
                    
                    if order_status.get('status') == 'FILLED':
                        progress.update(task, description="✓ Order Filled!")
                        console.print(f"\n[green]Order {order_id} filled successfully![/green]")
                        self._display_order_result(order_status)
                        return order_status
                    
                    elif order_status.get('status') == 'CANCELED':
                        progress.update(task, description="✗ Order Cancelled")
                        console.print(f"\n[red]Order {order_id} was cancelled[/red]")
                        return order_status
                    
                    time.sleep(2)  # Check every 2 seconds
                    
                except Exception as e:
                    logger.log_error(e, f"wait_for_fill monitoring order {order_id}")
                    time.sleep(5)  # Wait longer on error
        
        # Timeout reached
        console.print(f"\n[yellow]Timeout reached. Order {order_id} is still pending.[/yellow]")
        final_status = self.client.get_order_status(symbol, order_id)
        return final_status
    
    def cancel_limit_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel a specific limit order"""
        try:
            console.print(f"\n[yellow]Cancelling order {order_id} for {symbol}...[/yellow]")
            
            result = self.client.cancel_order(symbol, order_id)
            
            console.print(Panel(
                f"Order {order_id} cancelled successfully",
                title="Order Cancelled",
                border_style="yellow"
            ))
            
            return result
            
        except Exception as e:
            console.print(f"[red]Error cancelling order: {str(e)}[/red]")
            logger.log_error(e, f"cancel_limit_order {order_id}")
            raise
    
    def list_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all open limit orders"""
        try:
            orders = self.client.get_open_orders(symbol)
            
            if not orders:
                console.print("[yellow]No open orders found[/yellow]")
                return []
            
            # Create orders table
            table = Table(title=f"Open Orders{' for ' + symbol if symbol else ''}", 
                         show_header=True, header_style="bold blue")
            
            table.add_column("Order ID", style="cyan")
            table.add_column("Symbol", style="white")
            table.add_column("Side", style="white")
            table.add_column("Quantity", style="white")
            table.add_column("Price", style="white")
            table.add_column("Status", style="white")
            table.add_column("Time", style="dim")
            
            for order in orders:
                # Format time
                time_str = time.strftime('%H:%M:%S', time.localtime(order['time'] / 1000))
                
                # Color code side
                side_color = "green" if order['side'] == 'BUY' else "red"
                
                table.add_row(
                    str(order['orderId']),
                    order['symbol'],
                    f"[{side_color}]{order['side']}[/{side_color}]",
                    f"{float(order['origQty']):.6f}",
                    f"${float(order['price']):,.2f}",
                    order['status'],
                    time_str
                )
            
            console.print(table)
            return orders
            
        except Exception as e:
            console.print(f"[red]Error listing orders: {str(e)}[/red]")
            logger.log_error(e, "list_open_orders")
            raise

# CLI Commands
@click.command()
@click.argument('symbol', type=str)
@click.argument('side', type=click.Choice(['BUY', 'SELL'], case_sensitive=False))
@click.argument('quantity', type=float)
@click.argument('price', type=float)
@click.option('--wait', is_flag=True, help='Wait for order to fill')
@click.option('--no-confirm', is_flag=True, help='Skip confirmation prompt')
def limit_order(symbol: str, side: str, quantity: float, price: float, wait: bool, no_confirm: bool):
    """
    Place a limit order for the specified symbol.
    
    Examples:
        python limit_orders.py BTCUSDT BUY 0.01 45000
        python limit_orders.py ETHUSDT SELL 0.1 3000 --wait
    """
    try:
        manager = LimitOrderManager()
        
        # Override confirmation if flag is set
        if no_confirm:
            manager._confirm_limit_order = lambda *args: True
        
        # Execute order
        result = manager.execute_limit_order(symbol.upper(), side.upper(), quantity, price, wait)
        
        if result.get('status') != 'CANCELLED':
            console.print(f"\n[green]Limit order operation completed![/green]")
        
    except Exception as e:
        console.print(f"\n[red]Failed to execute limit order: {str(e)}[/red]")
        logger.log_error(e, "limit_order_cli")
        raise click.ClickException(str(e))

@click.command()
@click.option('--symbol', type=str, help='Filter by symbol')
def list_orders(symbol: Optional[str]):
    """List all open orders"""
    try:
        manager = LimitOrderManager()
        manager.list_open_orders(symbol.upper() if symbol else None)
    except Exception as e:
        console.print(f"[red]Error listing orders: {str(e)}[/red]")
        raise click.ClickException(str(e))

@click.command()
@click.argument('symbol', type=str)
@click.argument('order_id', type=int)
def cancel_order(symbol: str, order_id: int):
    """Cancel a specific order"""
    try:
        manager = LimitOrderManager()
        manager.cancel_limit_order(symbol.upper(), order_id)
    except Exception as e:
        console.print(f"[red]Error cancelling order: {str(e)}[/red]")
        raise click.ClickException(str(e))

if __name__ == '__main__':
    limit_order()