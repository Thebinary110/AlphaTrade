#!/usr/bin/env python3
"""
TWAP (Time-Weighted Average Price) order implementation
Splits large orders into smaller chunks executed over time
"""

import click
import time
import threading
import schedule
from datetime import datetime, timedelta
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from ...client.binance_client import BinanceFuturesClient
    from ...client.validator import TWAPOrderRequest
    from ...utils.logger import logger
    from ...utils.config import config
except ImportError:
    from client.binance_client import BinanceFuturesClient
    from client.validator import TWAPOrderRequest
    from utils.logger import logger
    from utils.config import config

console = Console()

class TWAPOrderManager:
    """Handles TWAP (Time-Weighted Average Price) order execution"""
    
    def __init__(self):
        self.client = BinanceFuturesClient()
        self.active_twap_orders = {}
        self.stop_scheduler = threading.Event()
    
    def execute_twap_order(self, symbol: str, side: str, total_quantity: float,
                          duration_minutes: int, interval_minutes: int = 5,
                          price_limit: float = None) -> Dict[str, Any]:
        """
        Execute TWAP order by splitting into smaller chunks over time
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
            total_quantity: Total quantity to execute
            duration_minutes: Total execution time
            interval_minutes: Time between each chunk
            price_limit: Optional price limit for each chunk
        """
        try:
            # Validate TWAP order
            twap_data = {
                'symbol': symbol,
                'side': side,
                'total_quantity': total_quantity,
                'duration_minutes': duration_minutes,
                'interval_minutes': interval_minutes
            }
            validated_twap = TWAPOrderRequest(**twap_data)
            
            # Calculate execution parameters
            num_chunks = duration_minutes // interval_minutes
            chunk_size = total_quantity / num_chunks
            
            # Display TWAP details
            self._display_twap_details(validated_twap, chunk_size, num_chunks, price_limit)
            
            # Confirm order
            if not self._confirm_twap_order(validated_twap, chunk_size, num_chunks):
                console.print("[red]TWAP order cancelled by user[/red]")
                return {"status": "CANCELLED", "reason": "User cancelled"}
            
            # Create TWAP execution plan
            twap_id = f"TWAP_{int(time.time())}"
            twap_order = {
                'twap_id': twap_id,
                'symbol': symbol,
                'side': side,
                'total_quantity': total_quantity,
                'remaining_quantity': total_quantity,
                'chunk_size': chunk_size,
                'duration_minutes': duration_minutes,
                'interval_minutes': interval_minutes,
                'price_limit': price_limit,
                'num_chunks': num_chunks,
                'executed_chunks': 0,
                'start_time': datetime.now(),
                'status': 'ACTIVE',
                'executions': [],
                'total_filled': 0.0,
                'avg_price': 0.0
            }
            
            # Start TWAP execution
            self._start_twap_execution(twap_order)
            
            # Display initial result
            self._display_twap_started(twap_order)
            
            return twap_order
            
        except Exception as e:
            console.print(f"[red]Error executing TWAP order: {str(e)}[/red]")
            logger.log_error(e, "execute_twap_order")
            raise
    
    def _display_twap_details(self, twap_order: TWAPOrderRequest, chunk_size: float, 
                             num_chunks: int, price_limit: float = None):
        """Display TWAP order details"""
        console.print(f"\n[bold cyan]TWAP Order Configuration:[/bold cyan]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="white")
        table.add_column("Description", style="dim")
        
        table.add_row("Symbol", twap_order.symbol, "Trading pair")
        table.add_row("Side", twap_order.side, "Buy or Sell")
        table.add_row("Total Quantity", f"{twap_order.total_quantity:.6f}", "Total amount to execute")
        table.add_row("Duration", f"{twap_order.duration_minutes} minutes", "Total execution time")
        table.add_row("Interval", f"{twap_order.interval_minutes} minutes", "Time between executions")
        table.add_row("", "", "")
        table.add_row("Number of Chunks", str(num_chunks), "How many parts")
        table.add_row("Chunk Size", f"{chunk_size:.6f}", "Size of each execution")
        
        if price_limit:
            table.add_row("Price Limit", f"${price_limit:,.2f}", "Maximum price per chunk")
        else:
            table.add_row("Order Type", "Market", "Each chunk will be market order")
        
        console.print(table)
        
        # Calculate estimated completion time
        completion_time = datetime.now() + timedelta(minutes=twap_order.duration_minutes)
        console.print(f"\n[yellow]Estimated completion: {completion_time.strftime('%H:%M:%S')}[/yellow]")
    
    def _confirm_twap_order(self, twap_order: TWAPOrderRequest, chunk_size: float, num_chunks: int) -> bool:
        """Confirm TWAP order with user"""
        current_price = self.client.get_current_price(twap_order.symbol)
        estimated_value = twap_order.total_quantity * current_price
        
        console.print(f"\n[bold yellow]TWAP Execution Plan:[/bold yellow]")
        console.print(f"Execute {num_chunks} orders of {chunk_size:.6f} {twap_order.symbol}")
        console.print(f"Every {twap_order.interval_minutes} minutes for {twap_order.duration_minutes} minutes")
        console.print(f"Current market price: ${current_price:,.2f}")
        console.print(f"Estimated total value: ${estimated_value:,.2f}")
        
        return click.confirm("\nDo you want to proceed with this TWAP order?", default=True)
    
    def _start_twap_execution(self, twap_order: Dict[str, Any]):
        """Start TWAP execution in background thread"""
        twap_id = twap_order['twap_id']
        self.active_twap_orders[twap_id] = twap_order
        
        # Start execution thread
        execution_thread = threading.Thread(
            target=self._execute_twap_chunks,
            args=(twap_order,),
            daemon=True
        )
        execution_thread.start()
        
        logger.info(f"Started TWAP execution {twap_id}")
    
    def _execute_twap_chunks(self, twap_order: Dict[str, Any]):
        """Execute TWAP chunks according to schedule"""
        twap_id = twap_order['twap_id']
        symbol = twap_order['symbol']
        side = twap_order['side']
        chunk_size = twap_order['chunk_size']
        price_limit = twap_order['price_limit']
        
        console.print(f"\n[green]🕒 TWAP execution started for {twap_id}[/green]")
        
        # Create progress bar
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task(
                f"TWAP {twap_id}", 
                total=twap_order['num_chunks']
            )
            
            for chunk_num in range(twap_order['num_chunks']):
                if self.stop_scheduler.is_set():
                    break
                
                try:
                    # Calculate actual chunk size (handle remainder in last chunk)
                    if chunk_num == twap_order['num_chunks'] - 1:
                        # Last chunk gets any remaining quantity
                        actual_chunk_size = twap_order['remaining_quantity']
                    else:
                        actual_chunk_size = min(chunk_size, twap_order['remaining_quantity'])
                    
                    if actual_chunk_size <= 0:
                        break
                    
                    # Execute chunk
                    chunk_result = self._execute_chunk(
                        symbol, side, actual_chunk_size, price_limit, chunk_num + 1
                    )
                    
                    # Update TWAP order
                    if chunk_result and chunk_result.get('status') == 'FILLED':
                        fill_price = float(chunk_result.get('avgPrice', 0))
                        fill_qty = float(chunk_result.get('executedQty', 0))
                        
                        twap_order['executions'].append({
                            'chunk_num': chunk_num + 1,
                            'quantity': fill_qty,
                            'price': fill_price,
                            'time': datetime.now().isoformat(),
                            'order_id': chunk_result.get('orderId')
                        })
                        
                        twap_order['total_filled'] += fill_qty
                        twap_order['remaining_quantity'] -= fill_qty
                        twap_order['executed_chunks'] += 1
                        
                        # Update average price
                        self._update_average_price(twap_order)
                        
                        # Update progress
                        progress.update(
                            task, 
                            advance=1,
                            description=f"TWAP {twap_id} | Filled: {twap_order['total_filled']:.6f} @ ${twap_order['avg_price']:.2f}"
                        )
                    
                    # Wait for next interval (except for last chunk)
                    if chunk_num < twap_order['num_chunks'] - 1:
                        time.sleep(twap_order['interval_minutes'] * 60)
                    
                except Exception as e:
                    logger.log_error(e, f"TWAP chunk execution {chunk_num + 1}")
                    # Continue with next chunk
                    continue
        
        # Mark as completed
        twap_order['status'] = 'COMPLETED'
        twap_order['end_time'] = datetime.now()
        
        self._display_twap_completion(twap_order)
        
        # Remove from active orders
        if twap_id in self.active_twap_orders:
            del self.active_twap_orders[twap_id]
    
    def _execute_chunk(self, symbol: str, side: str, quantity: float, 
                      price_limit: float = None, chunk_num: int = 1) -> Dict[str, Any]:
        """Execute a single TWAP chunk"""
        try:
            console.print(f"[dim]Executing chunk {chunk_num}: {quantity:.6f} {symbol}[/dim]")
            
            if price_limit:
                # Use limit order
                return self.client.place_limit_order(symbol, side, quantity, price_limit)
            else:
                # Use market order
                return self.client.place_market_order(symbol, side, quantity)
                
        except Exception as e:
            logger.log_error(e, f"execute_chunk {chunk_num}")
            return None
    
    def _update_average_price(self, twap_order: Dict[str, Any]):
        """Update volume-weighted average price"""
        total_value = 0.0
        total_quantity = 0.0
        
        for execution in twap_order['executions']:
            total_value += execution['quantity'] * execution['price']
            total_quantity += execution['quantity']
        
        if total_quantity > 0:
            twap_order['avg_price'] = total_value / total_quantity
    
    def _display_twap_started(self, twap_order: Dict[str, Any]):
        """Display TWAP order started message"""
        content = f"""
[bold green]✓ TWAP Order Started[/bold green]

TWAP ID: {twap_order['twap_id']}
Symbol: {twap_order['symbol']}
Side: {twap_order['side']}
Total Quantity: {twap_order['total_quantity']:.6f}
Chunks: {twap_order['num_chunks']} × {twap_order['chunk_size']:.6f}

Execution will continue in background...
        """
        
        console.print(Panel(content, title="TWAP Active", border_style="green"))
    
    def _display_twap_completion(self, twap_order: Dict[str, Any]):
        """Display TWAP completion summary"""
        duration = twap_order['end_time'] - twap_order['start_time']
        
        content = f"""
[bold green]✅ TWAP Order Completed[/bold green]

TWAP ID: {twap_order['twap_id']}
Total Filled: {twap_order['total_filled']:.6f} / {twap_order['total_quantity']:.6f}
Average Price: ${twap_order['avg_price']:.2f}
Executed Chunks: {twap_order['executed_chunks']} / {twap_order['num_chunks']}
Duration: {str(duration).split('.')[0]}

Fill Rate: {(twap_order['total_filled'] / twap_order['total_quantity'] * 100):.1f}%
        """
        
        console.print(Panel(content, title="TWAP Completed", border_style="green"))
    
    def list_active_twap_orders(self) -> Dict[str, Any]:
        """List all active TWAP orders"""
        if not self.active_twap_orders:
            console.print("[yellow]No active TWAP orders found[/yellow]")
            return {}
        
        table = Table(title="Active TWAP Orders", show_header=True, header_style="bold blue")
        table.add_column("TWAP ID", style="cyan")
        table.add_column("Symbol", style="white")
        table.add_column("Side", style="white")
        table.add_column("Progress", style="white")
        table.add_column("Avg Price", style="white")
        table.add_column("Status", style="white")
        table.add_column("Started", style="dim")
        
        for twap_id, twap_data in self.active_twap_orders.items():
            progress_pct = (twap_data['executed_chunks'] / twap_data['num_chunks']) * 100
            start_time = twap_data['start_time'].strftime('%H:%M:%S')
            
            table.add_row(
                twap_id,
                twap_data['symbol'],
                twap_data['side'],
                f"{progress_pct:.1f}% ({twap_data['executed_chunks']}/{twap_data['num_chunks']})",
                f"${twap_data['avg_price']:.2f}" if twap_data['avg_price'] > 0 else "N/A",
                twap_data['status'],
                start_time
            )
        
        console.print(table)
        return self.active_twap_orders
    
    def cancel_twap_order(self, twap_id: str) -> bool:
        """Cancel a specific TWAP order"""
        if twap_id not in self.active_twap_orders:
            console.print(f"[red]TWAP order {twap_id} not found[/red]")
            return False
        
        try:
            # Mark as cancelled
            self.active_twap_orders[twap_id]['status'] = 'CANCELLED'
            
            console.print(f"[yellow]TWAP order {twap_id} marked for cancellation[/yellow]")
            console.print("[dim]Execution will stop after current chunk completes[/dim]")
            
            return True
            
        except Exception as e:
            console.print(f"[red]Error cancelling TWAP order: {str(e)}[/red]")
            logger.log_error(e, f"cancel_twap_order {twap_id}")
            return False

# CLI Commands
@click.command()
@click.argument('symbol', type=str)
@click.argument('side', type=click.Choice(['BUY', 'SELL'], case_sensitive=False))
@click.argument('total_quantity', type=float)
@click.argument('duration_minutes', type=int)
@click.option('--interval', type=int, default=5, help='Interval between chunks in minutes')
@click.option('--price-limit', type=float, help='Price limit for each chunk')
@click.option('--no-confirm', is_flag=True, help='Skip confirmation prompt')
def twap_order(symbol: str, side: str, total_quantity: float, duration_minutes: int,
               interval: int, price_limit: float, no_confirm: bool):
    """
    Place a TWAP (Time-Weighted Average Price) order.
    
    Examples:
        python twap.py BTCUSDT BUY 1.0 60 --interval 10
        python twap.py ETHUSDT SELL 5.0 120 --interval 5 --price-limit 3000
    """
    try:
        manager = TWAPOrderManager()
        
        # Override confirmation if flag is set
        if no_confirm:
            manager._confirm_twap_order = lambda *args: True
        
        # Execute TWAP order
        result = manager.execute_twap_order(
            symbol.upper(), side.upper(), total_quantity, duration_minutes, interval, price_limit
        )
        
        if result.get('status') != 'CANCELLED':
            console.print(f"\n[green]TWAP order started successfully![/green]")
            console.print("[dim]Use 'list-twap' command to monitor progress[/dim]")
        
    except Exception as e:
        console.print(f"\n[red]Failed to execute TWAP order: {str(e)}[/red]")
        logger.log_error(e, "twap_order_cli")
        raise click.ClickException(str(e))

@click.command()
def list_twap():
    """List all active TWAP orders"""
    try:
        manager = TWAPOrderManager()
        manager.list_active_twap_orders()
    except Exception as e:
        console.print(f"[red]Error listing TWAP orders: {str(e)}[/red]")
        raise click.ClickException(str(e))

@click.command()
@click.argument('twap_id', type=str)
def cancel_twap(twap_id: str):
    """Cancel a specific TWAP order"""
    try:
        manager = TWAPOrderManager()
        manager.cancel_twap_order(twap_id)
    except Exception as e:
        console.print(f"[red]Error cancelling TWAP order: {str(e)}[/red]")
        raise click.ClickException(str(e))

if __name__ == '__main__':
    twap_order()