#!/usr/bin/env python3
"""
Main CLI application for Binance Futures Trading Bot
Provides unified interface for all trading operations
"""

import click
import sys
import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Fix imports for direct execution
try:
    # Try relative imports first (when run as module)
    from .client.binance_client import BinanceFuturesClient
    from .orders.market_orders import MarketOrderManager
    from .orders.limit_orders import LimitOrderManager
    from .orders.advanced.oco import OCOOrderManager
    from .orders.advanced.grid import GridTradingManager
    from .utils.logger import logger
    from .utils.config import config
except ImportError:
    # Fall back to absolute imports (when run directly)
    from client.binance_client import BinanceFuturesClient
    from orders.market_orders import MarketOrderManager
    from orders.limit_orders import LimitOrderManager
    from orders.advanced.oco import OCOOrderManager
    from orders.advanced.grid import GridTradingManager
    from utils.logger import logger
    from utils.config import config

console = Console()

class TradingBot:
    """Main trading bot application"""
    
    def __init__(self):
        self.client = None
        self.market_manager = None
        self.limit_manager = None
        self.oco_manager = None
        self.grid_manager = None
        
    def initialize(self):
        """Initialize trading bot components"""
        try:
            console.print("[bold blue]Initializing Binance Trading Bot...[/bold blue]")
            
            # Initialize client
            self.client = BinanceFuturesClient()
            
            # Initialize order managers
            self.market_manager = MarketOrderManager()
            self.limit_manager = LimitOrderManager()
            self.oco_manager = OCOOrderManager()
            self.grid_manager = GridTradingManager()
            
            # Test connection
            account_info = self.client.get_account_info()
            
            console.print("[green]✓ Bot initialized successfully[/green]")
            logger.info("Trading bot initialized successfully")
            
            return True
            
        except Exception as e:
            console.print(f"[red]✗ Failed to initialize bot: {str(e)}[/red]")
            logger.log_error(e, "bot_initialization")
            return False
    
    def display_welcome(self):
        """Display welcome message and account info"""
        welcome_text = """
[bold cyan]🚀 Binance Futures Trading Bot[/bold cyan]

[green]Features Available:[/green]
• Market Orders (instant execution)
• Limit Orders (price-specific execution)
• OCO Orders (one-cancels-other)
• TWAP Orders (time-weighted average price)
• Grid Trading (automated range trading)

[yellow]Environment:[/yellow] {'Testnet' if config.binance.testnet else 'Live Trading'}
        """
        
        console.print(Panel(welcome_text, border_style="blue"))
    
    def display_account_summary(self):
        """Display account summary"""
        try:
            account_info = self.client.get_account_info()
            positions = self.client.get_positions()
            
            # Account balance table
            balance_table = Table(title="Account Balance", show_header=True, header_style="bold green")
            balance_table.add_column("Asset", style="cyan")
            balance_table.add_column("Wallet Balance", style="white")
            balance_table.add_column("Available", style="green")
            balance_table.add_column("Unrealized PnL", style="white")
            
            for asset in account_info.get('assets', []):
                if float(asset['walletBalance']) > 0:
                    pnl_color = "green" if float(asset['unrealizedProfit']) >= 0 else "red"
                    balance_table.add_row(
                        asset['asset'],
                        f"{float(asset['walletBalance']):.4f}",
                        f"{float(asset['availableBalance']):.4f}",
                        f"[{pnl_color}]{float(asset['unrealizedProfit']):+.4f}[/{pnl_color}]"
                    )
            
            console.print(balance_table)
            
            # Positions table
            if positions:
                pos_table = Table(title="Open Positions", show_header=True, header_style="bold yellow")
                pos_table.add_column("Symbol", style="cyan")
                pos_table.add_column("Size", style="white")
                pos_table.add_column("Entry Price", style="white")
                pos_table.add_column("Mark Price", style="white")
                pos_table.add_column("PnL", style="white")
                pos_table.add_column("ROE %", style="white")
                
                for pos in positions:
                    pnl = float(pos['unrealizedProfit'])
                    roe = float(pos['percentage'])
                    pnl_color = "green" if pnl >= 0 else "red"
                    
                    pos_table.add_row(
                        pos['symbol'],
                        f"{float(pos['positionAmt']):.6f}",
                        f"${float(pos['entryPrice']):,.2f}",
                        f"${float(pos['markPrice']):,.2f}",
                        f"[{pnl_color}]{pnl:+.4f}[/{pnl_color}]",
                        f"[{pnl_color}]{roe:+.2f}%[/{pnl_color}]"
                    )
                
                console.print(pos_table)
            else:
                console.print("[dim]No open positions[/dim]")
                
        except Exception as e:
            console.print(f"[red]Error getting account info: {str(e)}[/red]")
            logger.log_error(e, "display_account_summary")

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """
    Binance Futures Trading Bot - Professional CLI Interface
    
    Use --help with any command for detailed usage information.
    """
    if ctx.invoked_subcommand is None:
        # Interactive mode when no subcommand is provided
        interactive_mode()

def interactive_mode():
    """Interactive mode for the trading bot"""
    bot = TradingBot()
    
    # Initialize bot
    if not bot.initialize():
        console.print("[red]Failed to initialize bot. Please check your configuration.[/red]")
        sys.exit(1)
    
    # Display welcome
    bot.display_welcome()
    
    while True:
        try:
            console.print("\n[bold cyan]Main Menu:[/bold cyan]")
            console.print("1. Account Summary")
            console.print("2. Market Order")
            console.print("3. Limit Order")
            console.print("4. OCO Order")
            console.print("5. Grid Trading")
            console.print("6. List Open Orders")
            console.print("7. Market Info")
            console.print("8. Exit")
            
            choice = click.prompt("\nSelect an option", type=int, default=1)
            
            if choice == 1:
                bot.display_account_summary()
            
            elif choice == 2:
                symbol = click.prompt("Symbol", default="BTCUSDT").upper()
                side = click.prompt("Side (BUY/SELL)", type=click.Choice(['BUY', 'SELL'], case_sensitive=False)).upper()
                quantity = click.prompt("Quantity", type=float)
                
                bot.market_manager.execute_market_order(symbol, side, quantity)
            
            elif choice == 3:
                symbol = click.prompt("Symbol", default="BTCUSDT").upper()
                side = click.prompt("Side (BUY/SELL)", type=click.Choice(['BUY', 'SELL'], case_sensitive=False)).upper()
                quantity = click.prompt("Quantity", type=float)
                price = click.prompt("Limit Price", type=float)
                wait = click.confirm("Wait for fill?", default=False)
                
                bot.limit_manager.execute_limit_order(symbol, side, quantity, price, wait)
            
            elif choice == 4:
                symbol = click.prompt("Symbol", default="BTCUSDT").upper()
                side = click.prompt("Side (BUY/SELL)", type=click.Choice(['BUY', 'SELL'], case_sensitive=False)).upper()
                quantity = click.prompt("Quantity", type=float)
                limit_price = click.prompt("Take Profit Price", type=float)
                stop_price = click.prompt("Stop Loss Price", type=float)
                stop_limit = click.prompt("Stop Limit Price (optional)", type=float, default=0)
                
                bot.oco_manager.execute_oco_order(
                    symbol, side, quantity, limit_price, stop_price,
                    stop_limit if stop_limit > 0 else None
                )
            
            elif choice == 5:
                symbol = click.prompt("Symbol", default="BTCUSDT").upper()
                quantity_per_grid = click.prompt("Quantity per grid level", type=float)
                grid_count = click.prompt("Number of grid levels", type=int, default=10)
                lower_price = click.prompt("Lower price boundary", type=float)
                upper_price = click.prompt("Upper price boundary", type=float)
                
                bot.grid_manager.execute_grid_strategy(
                    symbol, quantity_per_grid, grid_count, lower_price, upper_price
                )
            
            elif choice == 6:
                symbol = click.prompt("Symbol (optional)", default="", show_default=False)
                bot.limit_manager.list_open_orders(symbol.upper() if symbol else None)
            
            elif choice == 7:
                symbol = click.prompt("Symbol", default="BTCUSDT").upper()
                bot.market_manager.display_market_summary(symbol)
            
            elif choice == 8:
                console.print("[green]Goodbye! Happy trading! 🚀[/green]")
                break
            
            else:
                console.print("[red]Invalid option. Please try again.[/red]")
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            logger.log_error(e, "interactive_mode")

# Subcommands
@cli.command()
@click.argument('symbol', type=str)
@click.argument('side', type=click.Choice(['BUY', 'SELL'], case_sensitive=False))
@click.argument('quantity', type=float)
@click.option('--no-confirm', is_flag=True, help='Skip confirmation')
def market(symbol: str, side: str, quantity: float, no_confirm: bool):
    """Place a market order"""
    try:
        bot = TradingBot()
        if bot.initialize():
            if no_confirm:
                bot.market_manager._confirm_order = lambda *args: True
            bot.market_manager.execute_market_order(symbol.upper(), side.upper(), quantity)
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
@click.argument('symbol', type=str)
@click.argument('side', type=click.Choice(['BUY', 'SELL'], case_sensitive=False))
@click.argument('quantity', type=float)
@click.argument('price', type=float)
@click.option('--wait', is_flag=True, help='Wait for order to fill')
@click.option('--no-confirm', is_flag=True, help='Skip confirmation')
def limit(symbol: str, side: str, quantity: float, price: float, wait: bool, no_confirm: bool):
    """Place a limit order"""
    try:
        bot = TradingBot()
        if bot.initialize():
            if no_confirm:
                bot.limit_manager._confirm_limit_order = lambda *args: True
            bot.limit_manager.execute_limit_order(symbol.upper(), side.upper(), quantity, price, wait)
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
@click.argument('symbol', type=str)
@click.argument('side', type=click.Choice(['BUY', 'SELL'], case_sensitive=False))
@click.argument('quantity', type=float)
@click.argument('limit_price', type=float)
@click.argument('stop_price', type=float)
@click.option('--stop-limit', type=float, help='Stop limit price')
@click.option('--no-confirm', is_flag=True, help='Skip confirmation')
def oco(symbol: str, side: str, quantity: float, limit_price: float, stop_price: float, 
        stop_limit: float, no_confirm: bool):
    """Place an OCO order"""
    try:
        bot = TradingBot()
        if bot.initialize():
            if no_confirm:
                bot.oco_manager._confirm_oco_order = lambda *args: True
            bot.oco_manager.execute_oco_order(
                symbol.upper(), side.upper(), quantity, limit_price, stop_price, stop_limit
            )
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
@click.argument('symbol', type=str)
@click.argument('quantity_per_grid', type=float)
@click.argument('grid_count', type=int)
@click.argument('lower_price', type=float)
@click.argument('upper_price', type=float)
@click.option('--side', type=click.Choice(['BOTH', 'BUY_ONLY', 'SELL_ONLY']), default='BOTH', help='Grid direction')
@click.option('--no-confirm', is_flag=True, help='Skip confirmation')
def grid(symbol: str, quantity_per_grid: float, grid_count: int, lower_price: float, 
         upper_price: float, side: str, no_confirm: bool):
    """Start a grid trading strategy"""
    try:
        bot = TradingBot()
        if bot.initialize():
            if no_confirm:
                bot.grid_manager._confirm_grid_strategy = lambda *args: True
            bot.grid_manager.execute_grid_strategy(
                symbol.upper(), quantity_per_grid, grid_count, lower_price, upper_price, side
            )
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
@click.option('--symbol', type=str, help='Filter by symbol')
def orders(symbol: str):
    """List open orders"""
    try:
        bot = TradingBot()
        if bot.initialize():
            bot.limit_manager.list_open_orders(symbol.upper() if symbol else None)
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
@click.argument('symbol', type=str)
def info(symbol: str):
    """Show market information for a symbol"""
    try:
        bot = TradingBot()
        if bot.initialize():
            bot.market_manager.display_market_summary(symbol.upper())
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
def account():
    """Show account summary"""
    try:
        bot = TradingBot()
        if bot.initialize():
            bot.display_account_summary()
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
def grid_list():
    """List active grid strategies"""
    try:
        bot = TradingBot()
        if bot.initialize():
            bot.grid_manager.list_active_grids()
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
@click.argument('grid_id', type=str)
def grid_stop(grid_id: str):
    """Stop a grid strategy"""
    try:
        bot = TradingBot()
        if bot.initialize():
            bot.grid_manager.stop_grid_strategy(grid_id)
    except Exception as e:
        raise click.ClickException(str(e))

@cli.command()
def version():
    """Show version information"""
    console.print("[bold blue]Binance Futures Trading Bot v1.0.0[/bold blue]")
    console.print(f"Configuration: {config.binance.testnet and 'Testnet' or 'Live'}")
    console.print(f"Log Level: {config.logging.log_level}")

def main():
    """Main entry point"""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Unexpected error: {str(e)}[/red]")
        logger.log_error(e, "main")
        sys.exit(1)

if __name__ == '__main__':
    main()