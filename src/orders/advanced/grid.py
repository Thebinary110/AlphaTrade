#!/usr/bin/env python3
"""
Grid Trading implementation for Binance Futures
Automated buy-low/sell-high strategy within a price range
"""

import click
import time
import threading
import math
from datetime import datetime
from typing import Dict, Any, List, Optional
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
    from ...client.validator import GridOrderRequest
    from ...utils.logger import logger
    from ...utils.config import config
except ImportError:
    from client.binance_client import BinanceFuturesClient
    from client.validator import GridOrderRequest
    from utils.logger import logger
    from utils.config import config

console = Console()

class GridTradingManager:
    """Handles Grid Trading strategy execution"""
    
    def __init__(self):
        self.client = BinanceFuturesClient()
        self.active_grids = {}
        self.stop_monitoring = threading.Event()
    
    def execute_grid_strategy(self, symbol: str, quantity_per_grid: float,
                             grid_count: int, lower_price: float, upper_price: float,
                             base_side: str = "BOTH") -> Dict[str, Any]:
        """
        Execute grid trading strategy
        
        Args:
            symbol: Trading symbol
            quantity_per_grid: Quantity per grid level
            grid_count: Number of grid levels
            lower_price: Lower price boundary
            upper_price: Upper price boundary
            base_side: BOTH, BUY_ONLY, or SELL_ONLY
        """
        try:
            # Validate grid order
            grid_data = {
                'symbol': symbol,
                'quantity_per_grid': quantity_per_grid,
                'grid_count': grid_count,
                'lower_price': lower_price,
                'upper_price': upper_price
            }
            validated_grid = GridOrderRequest(**grid_data)
            
            # Get current market price
            current_price = self.client.get_current_price(symbol)
            
            # Calculate grid levels
            grid_levels = self._calculate_grid_levels(
                lower_price, upper_price, grid_count, current_price
            )
            
            # Display grid configuration
            self._display_grid_details(validated_grid, current_price, grid_levels, base_side)
            
            # Confirm grid strategy
            if not self._confirm_grid_strategy(validated_grid, current_price, grid_levels):
                console.print("[red]Grid strategy cancelled by user[/red]")
                return {"status": "CANCELLED", "reason": "User cancelled"}
            
            # Create grid execution plan
            grid_id = f"GRID_{int(time.time())}"
            grid_strategy = {
                'grid_id': grid_id,
                'symbol': symbol,
                'quantity_per_grid': quantity_per_grid,
                'grid_count': grid_count,
                'lower_price': lower_price,
                'upper_price': upper_price,
                'base_side': base_side,
                'current_price': current_price,
                'grid_levels': grid_levels,
                'buy_orders': {},
                'sell_orders': {},
                'executed_trades': [],
                'total_profit': 0.0,
                'status': 'ACTIVE',
                'start_time': datetime.now()
            }
            
            # Place initial grid orders
            self._place_initial_grid_orders(grid_strategy)
            
            # Start grid monitoring
            self._start_grid_monitoring(grid_strategy)
            
            # Display grid started
            self._display_grid_started(grid_strategy)
            
            return grid_strategy
            
        except Exception as e:
            console.print(f"[red]Error executing grid strategy: {str(e)}[/red]")
            logger.log_error(e, "execute_grid_strategy")
            raise
    
    def _calculate_grid_levels(self, lower_price: float, upper_price: float, 
                              grid_count: int, current_price: float) -> List[Dict[str, Any]]:
        """Calculate grid price levels with proper tick size alignment"""
        price_range = upper_price - lower_price
        grid_gap = price_range / (grid_count - 1)
        
        # Get symbol info for tick size
        try:
            symbol_info = self.client.get_symbol_info("BTCUSDT")
            tick_size = 0.1  # Default tick size for BTCUSDT
            
            # Find tick size from filters
            for filter_info in symbol_info.get('filters', []):
                if filter_info['filterType'] == 'PRICE_FILTER':
                    tick_size = float(filter_info['tickSize'])
                    break
        except:
            tick_size = 0.1  # Fallback tick size
        
        levels = []
        for i in range(grid_count):
            raw_price = lower_price + (i * grid_gap)
            
            # Round to tick size
            price = round(raw_price / tick_size) * tick_size
            price = round(price, 1)  # Round to 1 decimal for BTCUSDT
            
            # Determine order type based on current price
            if price < current_price:
                order_type = "BUY"
                side_color = "green"
            elif price > current_price:
                order_type = "SELL"  
                side_color = "red"
            else:
                order_type = "MARKET"  # Current price level
                side_color = "yellow"
            
            levels.append({
                'level': i + 1,
                'price': price,
                'order_type': order_type,
                'side_color': side_color,
                'status': 'PENDING'
            })
        
        return levels
    
    def _display_grid_details(self, grid_order: GridOrderRequest, current_price: float,
                             grid_levels: List[Dict], base_side: str):
        """Display grid strategy details"""
        console.print(f"\n[bold cyan]Grid Trading Strategy Configuration:[/bold cyan]")
        
        # Summary table
        summary_table = Table(show_header=True, header_style="bold magenta")
        summary_table.add_column("Parameter", style="cyan")
        summary_table.add_column("Value", style="white")
        summary_table.add_column("Description", style="dim")
        
        summary_table.add_row("Symbol", grid_order.symbol, "Trading pair")
        summary_table.add_row("Current Price", f"${current_price:,.2f}", "Market price")
        summary_table.add_row("Price Range", f"${grid_order.lower_price:,.2f} - ${grid_order.upper_price:,.2f}", "Grid boundaries")
        summary_table.add_row("Grid Levels", str(grid_order.grid_count), "Number of price levels")
        summary_table.add_row("Quantity per Level", f"{grid_order.quantity_per_grid:.6f}", "Size per grid order")
        summary_table.add_row("Total Quantity", f"{grid_order.grid_count * grid_order.quantity_per_grid:.6f}", "Maximum position size")
        summary_table.add_row("Strategy Type", base_side, "Trading direction")
        
        console.print(summary_table)
        
        # Grid levels table
        console.print(f"\n[bold yellow]Grid Levels:[/bold yellow]")
        grid_table = Table(show_header=True, header_style="bold blue")
        grid_table.add_column("Level", style="white")
        grid_table.add_column("Price", style="white")
        grid_table.add_column("Order Type", style="white")
        grid_table.add_column("Distance from Market", style="white")
        
        for level in grid_levels:
            distance_pct = ((level['price'] - current_price) / current_price) * 100
            distance_str = f"{distance_pct:+.2f}%"
            
            if level['order_type'] == 'MARKET':
                distance_str = "Current Price"
            
            grid_table.add_row(
                str(level['level']),
                f"${level['price']:,.2f}",
                f"[{level['side_color']}]{level['order_type']}[/{level['side_color']}]",
                distance_str
            )
        
        console.print(grid_table)
        
        # Calculate potential profit
        grid_gap = (grid_order.upper_price - grid_order.lower_price) / (grid_order.grid_count - 1)
        potential_profit_per_cycle = grid_gap * grid_order.quantity_per_grid
        max_cycles = grid_order.grid_count - 1
        max_potential_profit = potential_profit_per_cycle * max_cycles
        
        console.print(f"\n[green]Potential profit per cycle: ${potential_profit_per_cycle:.2f}[/green]")
        console.print(f"[green]Maximum potential profit: ${max_potential_profit:.2f}[/green]")
    
    def _confirm_grid_strategy(self, grid_order: GridOrderRequest, current_price: float,
                              grid_levels: List[Dict]) -> bool:
        """Confirm grid strategy with user"""
        total_value = grid_order.grid_count * grid_order.quantity_per_grid * current_price
        
        console.print(f"\n[bold yellow]Grid Strategy Summary:[/bold yellow]")
        console.print(f"This will place {grid_order.grid_count} orders across the price range")
        console.print(f"Buy orders below ${current_price:,.2f}, Sell orders above ${current_price:,.2f}")
        console.print(f"Estimated total value: ${total_value:,.2f}")
        console.print(f"Strategy will automatically buy low and sell high within the range")
        
        return click.confirm("\nDo you want to proceed with this grid strategy?", default=True)
    
    def _place_initial_grid_orders(self, grid_strategy: Dict[str, Any]):
        """Place initial grid orders"""
        console.print(f"\n[yellow]Placing initial grid orders...[/yellow]")
        
        symbol = grid_strategy['symbol']
        quantity = grid_strategy['quantity_per_grid']
        current_price = grid_strategy['current_price']
        
        placed_orders = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            task = progress.add_task(f"Placing grid orders for {symbol}", total=len(grid_strategy['grid_levels']))
            
            for level in grid_strategy['grid_levels']:
                try:
                    price = level['price']
                    
                    if level['order_type'] == 'BUY' and price < current_price:
                        # Place buy limit order
                        order_result = self.client.place_limit_order(symbol, 'BUY', quantity, price)
                        if order_result:
                            grid_strategy['buy_orders'][level['level']] = order_result
                            level['status'] = 'PLACED'
                            level['order_id'] = order_result.get('orderId')
                            placed_orders += 1
                    
                    elif level['order_type'] == 'SELL' and price > current_price:
                        # Place sell limit order  
                        order_result = self.client.place_limit_order(symbol, 'SELL', quantity, price)
                        if order_result:
                            grid_strategy['sell_orders'][level['level']] = order_result
                            level['status'] = 'PLACED'
                            level['order_id'] = order_result.get('orderId')
                            placed_orders += 1
                    
                    progress.update(task, advance=1)
                    time.sleep(0.1)  # Small delay to avoid rate limits
                    
                except Exception as e:
                    logger.log_error(e, f"place_grid_order_level_{level['level']}")
                    level['status'] = 'FAILED'
                    continue
        
        console.print(f"[green]✓ Placed {placed_orders} grid orders successfully[/green]")
        grid_strategy['placed_orders_count'] = placed_orders
    
    def _start_grid_monitoring(self, grid_strategy: Dict[str, Any]):
        """Start monitoring grid strategy in background"""
        grid_id = grid_strategy['grid_id']
        self.active_grids[grid_id] = grid_strategy
        
        # Start monitoring thread
        monitor_thread = threading.Thread(
            target=self._monitor_grid_strategy,
            args=(grid_strategy,),
            daemon=True
        )
        monitor_thread.start()
        
        logger.info(f"Started monitoring grid strategy {grid_id}")
    
    def _monitor_grid_strategy(self, grid_strategy: Dict[str, Any]):
        """Monitor grid strategy execution"""
        grid_id = grid_strategy['grid_id']
        symbol = grid_strategy['symbol']
        
        logger.info(f"Started monitoring grid strategy {grid_id}")
        
        while not self.stop_monitoring.is_set() and grid_strategy['status'] == 'ACTIVE':
            try:
                # Check buy orders
                for level, order_data in grid_strategy['buy_orders'].items():
                    if order_data.get('status') != 'FILLED':
                        order_status = self.client.get_order_status(symbol, order_data['orderId'])
                        if order_status.get('status') == 'FILLED':
                            self._handle_grid_order_fill(grid_strategy, level, 'BUY', order_status)
                
                # Check sell orders
                for level, order_data in grid_strategy['sell_orders'].items():
                    if order_data.get('status') != 'FILLED':
                        order_status = self.client.get_order_status(symbol, order_data['orderId'])
                        if order_status.get('status') == 'FILLED':
                            self._handle_grid_order_fill(grid_strategy, level, 'SELL', order_status)
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.log_error(e, f"monitor_grid_strategy {grid_id}")
                time.sleep(30)  # Wait longer on error
        
        logger.info(f"Stopped monitoring grid strategy {grid_id}")
    
    def _handle_grid_order_fill(self, grid_strategy: Dict[str, Any], level: int, 
                               side: str, order_status: Dict[str, Any]):
        """Handle when a grid order is filled"""
        fill_price = float(order_status.get('avgPrice', 0))
        fill_qty = float(order_status.get('executedQty', 0))
        
        # Log the fill
        console.print(f"\n[green]🎯 Grid {side} order filled at level {level}: {fill_qty:.6f} @ ${fill_price:,.2f}[/green]")
        
        # Record the trade
        trade_record = {
            'level': level,
            'side': side,
            'quantity': fill_qty,
            'price': fill_price,
            'time': datetime.now().isoformat(),
            'order_id': order_status.get('orderId')
        }
        grid_strategy['executed_trades'].append(trade_record)
        
        # Update order status
        if side == 'BUY':
            grid_strategy['buy_orders'][level]['status'] = 'FILLED'
            # Place corresponding sell order at higher level
            self._place_counter_order(grid_strategy, level, 'SELL')
        else:
            grid_strategy['sell_orders'][level]['status'] = 'FILLED'
            # Place corresponding buy order at lower level
            self._place_counter_order(grid_strategy, level, 'BUY')
        
        # Calculate profit if this completes a cycle
        self._calculate_grid_profit(grid_strategy, trade_record)
    
    def _place_counter_order(self, grid_strategy: Dict[str, Any], filled_level: int, side: str):
        """Place counter order after a fill"""
        try:
            symbol = grid_strategy['symbol']
            quantity = grid_strategy['quantity_per_grid']
            
            # Find appropriate level for counter order
            if side == 'SELL' and filled_level < len(grid_strategy['grid_levels']):
                # Place sell order at next higher level
                target_level = filled_level + 1
                if target_level <= len(grid_strategy['grid_levels']):
                    price = grid_strategy['grid_levels'][target_level - 1]['price']
                    order_result = self.client.place_limit_order(symbol, 'SELL', quantity, price)
                    if order_result:
                        grid_strategy['sell_orders'][target_level] = order_result
                        console.print(f"[dim]Placed counter SELL order at level {target_level}: ${price:,.2f}[/dim]")
            
            elif side == 'BUY' and filled_level > 1:
                # Place buy order at next lower level
                target_level = filled_level - 1
                if target_level >= 1:
                    price = grid_strategy['grid_levels'][target_level - 1]['price']
                    order_result = self.client.place_limit_order(symbol, 'BUY', quantity, price)
                    if order_result:
                        grid_strategy['buy_orders'][target_level] = order_result
                        console.print(f"[dim]Placed counter BUY order at level {target_level}: ${price:,.2f}[/dim]")
        
        except Exception as e:
            logger.log_error(e, f"place_counter_order {side} level {filled_level}")
    
    def _calculate_grid_profit(self, grid_strategy: Dict[str, Any], trade_record: Dict[str, Any]):
        """Calculate profit from completed grid cycles"""
        # Simple profit calculation - can be enhanced
        if len(grid_strategy['executed_trades']) >= 2:
            # Look for buy-sell pairs
            recent_trades = grid_strategy['executed_trades'][-10:]  # Last 10 trades
            
            for buy_trade in recent_trades:
                if buy_trade['side'] == 'BUY':
                    for sell_trade in recent_trades:
                        if (sell_trade['side'] == 'SELL' and 
                            sell_trade['price'] > buy_trade['price'] and
                            sell_trade['level'] > buy_trade['level']):
                            
                            profit = (sell_trade['price'] - buy_trade['price']) * min(buy_trade['quantity'], sell_trade['quantity'])
                            grid_strategy['total_profit'] += profit
                            
                            console.print(f"[green]💰 Grid cycle profit: ${profit:.2f} (Total: ${grid_strategy['total_profit']:.2f})[/green]")
                            break
    
    def _display_grid_started(self, grid_strategy: Dict[str, Any]):
        """Display grid strategy started message"""
        content = f"""
[bold green]✓ Grid Strategy Started[/bold green]

Grid ID: {grid_strategy['grid_id']}
Symbol: {grid_strategy['symbol']}
Grid Levels: {grid_strategy['grid_count']}
Price Range: ${grid_strategy['lower_price']:,.2f} - ${grid_strategy['upper_price']:,.2f}
Orders Placed: {grid_strategy['placed_orders_count']}

Grid trading is now active and monitoring for opportunities...
        """
        
        console.print(Panel(content, title="Grid Trading Active", border_style="green"))
    
    def list_active_grids(self) -> Dict[str, Any]:
        """List all active grid strategies"""
        if not self.active_grids:
            console.print("[yellow]No active grid strategies found[/yellow]")
            return {}
        
        table = Table(title="Active Grid Strategies", show_header=True, header_style="bold blue")
        table.add_column("Grid ID", style="cyan")
        table.add_column("Symbol", style="white")
        table.add_column("Levels", style="white")
        table.add_column("Range", style="white")
        table.add_column("Trades", style="white")
        table.add_column("Profit", style="green")
        table.add_column("Status", style="white")
        
        for grid_id, grid_data in self.active_grids.items():
            table.add_row(
                grid_id,
                grid_data['symbol'],
                str(grid_data['grid_count']),
                f"${grid_data['lower_price']:,.0f}-${grid_data['upper_price']:,.0f}",
                str(len(grid_data['executed_trades'])),
                f"${grid_data['total_profit']:.2f}",
                grid_data['status']
            )
        
        console.print(table)
        return self.active_grids
    
    def stop_grid_strategy(self, grid_id: str) -> bool:
        """Stop a specific grid strategy"""
        if grid_id not in self.active_grids:
            console.print(f"[red]Grid strategy {grid_id} not found[/red]")
            return False
        
        try:
            grid_data = self.active_grids[grid_id]
            symbol = grid_data['symbol']
            
            # Cancel all pending orders
            cancelled_count = 0
            
            # Cancel buy orders
            for level, order_data in grid_data['buy_orders'].items():
                if order_data.get('status') != 'FILLED':
                    try:
                        self.client.cancel_order(symbol, order_data['orderId'])
                        cancelled_count += 1
                    except:
                        pass
            
            # Cancel sell orders
            for level, order_data in grid_data['sell_orders'].items():
                if order_data.get('status') != 'FILLED':
                    try:
                        self.client.cancel_order(symbol, order_data['orderId'])
                        cancelled_count += 1
                    except:
                        pass
            
            # Update status
            grid_data['status'] = 'STOPPED'
            grid_data['end_time'] = datetime.now()
            
            console.print(f"[green]Grid strategy {grid_id} stopped successfully[/green]")
            console.print(f"[dim]Cancelled {cancelled_count} pending orders[/dim]")
            console.print(f"[green]Total profit: ${grid_data['total_profit']:.2f}[/green]")
            
            return True
            
        except Exception as e:
            console.print(f"[red]Error stopping grid strategy: {str(e)}[/red]")
            logger.log_error(e, f"stop_grid_strategy {grid_id}")
            return False

# CLI Commands
@click.command()
@click.argument('symbol', type=str)
@click.argument('quantity_per_grid', type=float)
@click.argument('grid_count', type=int)
@click.argument('lower_price', type=float)
@click.argument('upper_price', type=float)
@click.option('--side', type=click.Choice(['BOTH', 'BUY_ONLY', 'SELL_ONLY']), default='BOTH', help='Grid trading direction')
@click.option('--no-confirm', is_flag=True, help='Skip confirmation prompt')
def grid_strategy(symbol: str, quantity_per_grid: float, grid_count: int,
                 lower_price: float, upper_price: float, side: str, no_confirm: bool):
    """
    Start a grid trading strategy.
    
    Examples:
        python grid.py BTCUSDT 0.001 10 44000 46000
        python grid.py ETHUSDT 0.01 15 4000 4300 --side BUY_ONLY
    """
    try:
        manager = GridTradingManager()
        
        # Override confirmation if flag is set
        if no_confirm:
            manager._confirm_grid_strategy = lambda *args: True
        
        # Execute grid strategy
        result = manager.execute_grid_strategy(
            symbol.upper(), quantity_per_grid, grid_count, lower_price, upper_price, side
        )
        
        if result.get('status') != 'CANCELLED':
            console.print(f"\n[green]Grid strategy started successfully![/green]")
            console.print("[dim]Use 'list-grid' command to monitor progress[/dim]")
        
    except Exception as e:
        console.print(f"\n[red]Failed to start grid strategy: {str(e)}[/red]")
        logger.log_error(e, "grid_strategy_cli")
        raise click.ClickException(str(e))

@click.command()
def list_grid():
    """List all active grid strategies"""
    try:
        manager = GridTradingManager()
        manager.list_active_grids()
    except Exception as e:
        console.print(f"[red]Error listing grid strategies: {str(e)}[/red]")
        raise click.ClickException(str(e))

@click.command()
@click.argument('grid_id', type=str)
def stop_grid(grid_id: str):
    """Stop a specific grid strategy"""
    try:
        manager = GridTradingManager()
        manager.stop_grid_strategy(grid_id)
    except Exception as e:
        console.print(f"[red]Error stopping grid strategy: {str(e)}[/red]")
        raise click.ClickException(str(e))

if __name__ == '__main__':
    grid_strategy()