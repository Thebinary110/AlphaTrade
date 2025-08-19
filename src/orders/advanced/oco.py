#!/usr/bin/env python3
"""
OCO (One-Cancels-Other) order implementation for Binance Futures
Combines take-profit and stop-loss orders for risk management
"""

import click
import time
import threading
from typing import Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from ...client.binance_client import BinanceFuturesClient
    from ...client.validator import OCOOrderRequest
    from ...utils.logger import logger
    from ...utils.config import config
except ImportError:
    from client.binance_client import BinanceFuturesClient
    from client.validator import OCOOrderRequest
    from utils.logger import logger
    from utils.config import config

console = Console()

class OCOOrderManager:
    """Handles OCO (One-Cancels-Other) order operations"""
    
    def __init__(self):
        self.client = BinanceFuturesClient()
        self.monitoring_orders = {}
        self.stop_monitoring = threading.Event()
    
    def execute_oco_order(self, symbol: str, side: str, quantity: float,
                         price: float, stop_price: float, 
                         stop_limit_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Execute OCO order by placing both limit and stop orders
        Note: Binance Futures doesn't have native OCO, so we simulate it
        """
        try:
            # Validate OCO order request
            oco_data = {
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'price': price,
                'stop_price': stop_price,
                'stop_limit_price': stop_limit_price
            }
            validated_oco = OCOOrderRequest(**oco_data)
            
            # Get current market price
            current_price = self.client.get_current_price(symbol)
            
            # Display OCO order details
            self._display_oco_details(validated_oco, current_price)
            
            # Confirm order
            if not self._confirm_oco_order(validated_oco, current_price):
                console.print("[red]OCO order cancelled by user[/red]")
                return {"status": "CANCELLED", "reason": "User cancelled"}
            
            # Place both orders
            console.print("\n[yellow]Placing OCO orders...[/yellow]")
            
            limit_order_result = None
            stop_order_result = None
            
            try:
                # Place limit order (take profit)
                with console.status("[bold green]Placing limit order..."):
                    limit_order_result = self.client.place_limit_order(
                        symbol, side, quantity, price
                    )
                
                console.print(f"[green]✓ Limit order placed: {limit_order_result.get('orderId')}[/green]")
                
                # Place stop order (stop loss)
                with console.status("[bold yellow]Placing stop order..."):
                    if stop_limit_price:
                        stop_order_result = self.client.place_stop_limit_order(
                            symbol, side, quantity, stop_price, stop_limit_price
                        )
                    else:
                        # Use stop market order if no stop limit price provided
                        stop_order_result = self._place_stop_market_order(
                            symbol, side, quantity, stop_price
                        )
                
                console.print(f"[green]✓ Stop order placed: {stop_order_result.get('orderId')}[/green]")
                
                # Create OCO tracking entry
                oco_id = f"OCO_{int(time.time())}"
                oco_result = {
                    'oco_id': oco_id,
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'limit_order': limit_order_result,
                    'stop_order': stop_order_result,
                    'status': 'ACTIVE',
                    'created_time': time.time()
                }
                
                # Start monitoring
                self._start_oco_monitoring(oco_result)
                
                # Display results
                self._display_oco_result(oco_result)
                
                return oco_result
                
            except Exception as e:
                # Clean up any placed orders on error
                self._cleanup_failed_oco(limit_order_result, stop_order_result, symbol)
                raise
                
        except Exception as e:
            console.print(f"[red]Error executing OCO order: {str(e)}[/red]")
            logger.log_error(e, "execute_oco_order")
            raise
    
    def _place_stop_market_order(self, symbol: str, side: str, quantity: float, stop_price: float) -> Dict[str, Any]:
        """Place a stop market order (fallback for when stop-limit not available)"""
        # Note: This is a simplified implementation
        # In practice, you might need to monitor price and place market order when triggered
        return self.client.place_stop_limit_order(symbol, side, quantity, stop_price, stop_price)
    
    def _display_oco_details(self, oco_order: OCOOrderRequest, current_price: float):
        """Display OCO order details"""
        console.print(f"\n[bold cyan]OCO Order Configuration:[/bold cyan]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="white")
        table.add_column("Description", style="dim")
        
        table.add_row("Symbol", oco_order.symbol, "Trading pair")
        table.add_row("Side", oco_order.side, "Buy or Sell")
        table.add_row("Quantity", f"{oco_order.quantity:.6f}", "Order size")
        table.add_row("Current Price", f"${current_price:,.2f}", "Market price")
        table.add_row("", "", "")
        table.add_row("Limit Price", f"${oco_order.price:,.2f}", "Take profit level")
        table.add_row("Stop Price", f"${oco_order.stop_price:,.2f}", "Stop loss trigger")
        
        if oco_order.stop_limit_price:
            table.add_row("Stop Limit", f"${oco_order.stop_limit_price:,.2f}", "Stop loss execution price")
        
        console.print(table)
        
        # Calculate potential profit/loss
        if oco_order.side == 'SELL':
            profit_pct = ((oco_order.price - current_price) / current_price) * 100
            loss_pct = ((oco_order.stop_price - current_price) / current_price) * 100
        else:
            profit_pct = ((current_price - oco_order.price) / oco_order.price) * 100
            loss_pct = ((current_price - oco_order.stop_price) / oco_order.stop_price) * 100
        
        console.print(f"\n[green]Potential Profit: {profit_pct:+.2f}%[/green]")
        console.print(f"[red]Potential Loss: {loss_pct:+.2f}%[/red]")
    
    def _confirm_oco_order(self, oco_order: OCOOrderRequest, current_price: float) -> bool:
        """Confirm OCO order with user"""
        estimated_value = oco_order.quantity * current_price
        
        console.print(f"\n[bold yellow]This will place 2 orders:[/bold yellow]")
        console.print(f"1. Limit {oco_order.side} @ ${oco_order.price:,.2f} (Take Profit)")
        console.print(f"2. Stop {oco_order.side} @ ${oco_order.stop_price:,.2f} (Stop Loss)")
        console.print(f"Estimated Value: ${estimated_value:,.2f}")
        
        return click.confirm("\nDo you want to proceed with this OCO order?", default=True)
    
    def _display_oco_result(self, oco_result: Dict[str, Any]):
        """Display OCO order execution results"""
        content = f"""
[bold green]✓ OCO Orders Placed Successfully[/bold green]

OCO ID: {oco_result['oco_id']}
Symbol: {oco_result['symbol']}
Side: {oco_result['side']}
Quantity: {oco_result['quantity']:.6f}

Limit Order ID: {oco_result['limit_order'].get('orderId')}
Stop Order ID: {oco_result['stop_order'].get('orderId')}

Status: Monitoring for execution...
        """
        
        console.print(Panel(content, title="OCO Order Active", border_style="green"))
    
    def _start_oco_monitoring(self, oco_result: Dict[str, Any]):
        """Start monitoring OCO orders in background thread"""
        oco_id = oco_result['oco_id']
        self.monitoring_orders[oco_id] = oco_result
        
        # Start monitoring thread
        monitor_thread = threading.Thread(
            target=self._monitor_oco_order,
            args=(oco_result,),
            daemon=True
        )
        monitor_thread.start()
        
        console.print(f"[dim]Started monitoring OCO {oco_id}[/dim]")
    
    def _monitor_oco_order(self, oco_result: Dict[str, Any]):
        """Monitor OCO order execution"""
        oco_id = oco_result['oco_id']
        symbol = oco_result['symbol']
        limit_order_id = oco_result['limit_order'].get('orderId')
        stop_order_id = oco_result['stop_order'].get('orderId')
        
        logger.info(f"Started monitoring OCO {oco_id}")
        
        while not self.stop_monitoring.is_set():
            try:
                # Check limit order status
                limit_status = self.client.get_order_status(symbol, limit_order_id)
                stop_status = self.client.get_order_status(symbol, stop_order_id)
                
                # Check if either order is filled
                if limit_status.get('status') == 'FILLED':
                    # Limit order filled - cancel stop order
                    console.print(f"\n[green]🎯 Take profit hit for OCO {oco_id}![/green]")
                    self._cancel_remaining_order(symbol, stop_order_id, "stop order")
                    oco_result['status'] = 'LIMIT_FILLED'
                    break
                
                elif stop_status.get('status') == 'FILLED':
                    # Stop order filled - cancel limit order
                    console.print(f"\n[red]🛑 Stop loss triggered for OCO {oco_id}![/red]")
                    self._cancel_remaining_order(symbol, limit_order_id, "limit order")
                    oco_result['status'] = 'STOP_FILLED'
                    break
                
                elif (limit_status.get('status') == 'CANCELED' and 
                      stop_status.get('status') == 'CANCELED'):
                    # Both orders cancelled
                    console.print(f"\n[yellow]OCO {oco_id} cancelled[/yellow]")
                    oco_result['status'] = 'CANCELLED'
                    break
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.log_error(e, f"monitor_oco_order {oco_id}")
                time.sleep(10)  # Wait longer on error
        
        # Remove from monitoring
        if oco_id in self.monitoring_orders:
            del self.monitoring_orders[oco_id]
        
        logger.info(f"Stopped monitoring OCO {oco_id}")
    
    def _cancel_remaining_order(self, symbol: str, order_id: int, order_type: str):
        """Cancel the remaining order when one leg of OCO is filled"""
        try:
            self.client.cancel_order(symbol, order_id)
            console.print(f"[dim]Cancelled remaining {order_type} (ID: {order_id})[/dim]")
        except Exception as e:
            logger.log_error(e, f"cancel_remaining_order {order_id}")
    
    def _cleanup_failed_oco(self, limit_order: Optional[Dict], stop_order: Optional[Dict], symbol: str):
        """Clean up orders if OCO placement fails"""
        if limit_order and limit_order.get('orderId'):
            try:
                self.client.cancel_order(symbol, limit_order['orderId'])
                console.print(f"[yellow]Cancelled limit order {limit_order['orderId']} due to error[/yellow]")
            except:
                pass
        
        if stop_order and stop_order.get('orderId'):
            try:
                self.client.cancel_order(symbol, stop_order['orderId'])
                console.print(f"[yellow]Cancelled stop order {stop_order['orderId']} due to error[/yellow]")
            except:
                pass
    
    def list_active_oco_orders(self) -> Dict[str, Any]:
        """List all active OCO orders"""
        if not self.monitoring_orders:
            console.print("[yellow]No active OCO orders found[/yellow]")
            return {}
        
        table = Table(title="Active OCO Orders", show_header=True, header_style="bold blue")
        table.add_column("OCO ID", style="cyan")
        table.add_column("Symbol", style="white")
        table.add_column("Side", style="white")
        table.add_column("Quantity", style="white")
        table.add_column("Limit Order", style="green")
        table.add_column("Stop Order", style="red")
        table.add_column("Status", style="white")
        
        for oco_id, oco_data in self.monitoring_orders.items():
            table.add_row(
                oco_id,
                oco_data['symbol'],
                oco_data['side'],
                f"{oco_data['quantity']:.6f}",
                str(oco_data['limit_order'].get('orderId')),
                str(oco_data['stop_order'].get('orderId')),
                oco_data['status']
            )
        
        console.print(table)
        return self.monitoring_orders
    
    def cancel_oco_order(self, oco_id: str) -> bool:
        """Cancel a specific OCO order"""
        if oco_id not in self.monitoring_orders:
            console.print(f"[red]OCO order {oco_id} not found[/red]")
            return False
        
        oco_data = self.monitoring_orders[oco_id]
        symbol = oco_data['symbol']
        
        try:
            # Cancel both orders
            self.client.cancel_order(symbol, oco_data['limit_order']['orderId'])
            self.client.cancel_order(symbol, oco_data['stop_order']['orderId'])
            
            # Update status
            oco_data['status'] = 'CANCELLED'
            
            console.print(f"[green]OCO order {oco_id} cancelled successfully[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]Error cancelling OCO order: {str(e)}[/red]")
            logger.log_error(e, f"cancel_oco_order {oco_id}")
            return False

# CLI Commands
@click.command()
@click.argument('symbol', type=str)
@click.argument('side', type=click.Choice(['BUY', 'SELL'], case_sensitive=False))
@click.argument('quantity', type=float)
@click.argument('limit_price', type=float)
@click.argument('stop_price', type=float)
@click.option('--stop-limit', type=float, help='Stop limit price (optional)')
@click.option('--no-confirm', is_flag=True, help='Skip confirmation prompt')
def oco_order(symbol: str, side: str, quantity: float, limit_price: float, 
              stop_price: float, stop_limit: Optional[float], no_confirm: bool):
    """
    Place an OCO (One-Cancels-Other) order.
    
    Examples:
        python oco.py BTCUSDT SELL 0.01 46000 44000
        python oco.py ETHUSDT BUY 0.1 2900 3100 --stop-limit 3110
    """
    try:
        manager = OCOOrderManager()
        
        # Override confirmation if flag is set
        if no_confirm:
            manager._confirm_oco_order = lambda *args: True
        
        # Execute OCO order
        result = manager.execute_oco_order(
            symbol.upper(), side.upper(), quantity, limit_price, stop_price, stop_limit
        )
        
        if result.get('status') != 'CANCELLED':
            console.print(f"\n[green]OCO order operation completed![/green]")
            console.print("[dim]Use 'list-oco' command to monitor active OCO orders[/dim]")
        
    except Exception as e:
        console.print(f"\n[red]Failed to execute OCO order: {str(e)}[/red]")
        logger.log_error(e, "oco_order_cli")
        raise click.ClickException(str(e))

@click.command()
def list_oco():
    """List all active OCO orders"""
    try:
        manager = OCOOrderManager()
        manager.list_active_oco_orders()
    except Exception as e:
        console.print(f"[red]Error listing OCO orders: {str(e)}[/red]")
        raise click.ClickException(str(e))

@click.command()
@click.argument('oco_id', type=str)
def cancel_oco(oco_id: str):
    """Cancel a specific OCO order"""
    try:
        manager = OCOOrderManager()
        manager.cancel_oco_order(oco_id)
    except Exception as e:
        console.print(f"[red]Error cancelling OCO order: {str(e)}[/red]")
        raise click.ClickException(str(e))

if __name__ == '__main__':
    oco_order()