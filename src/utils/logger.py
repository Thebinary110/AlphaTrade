#!/usr/bin/env python3
"""
Logging system for Binance Trading Bot
Provides structured logging with file rotation and console output
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from .config import config

class TradingLogger:
    """Enhanced logger for trading operations"""
    
    def __init__(self, name: str = "trading_bot"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, config.logging.log_level.upper()))
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup file and console handlers"""
        # Create logs directory if it doesn't exist
        log_path = Path(config.logging.log_file)
        log_path.parent.mkdir(exist_ok=True)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            config.logging.log_file,
            maxBytes=config.logging.max_file_size,
            backupCount=config.logging.backup_count
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log_order(self, action: str, symbol: str, side: str, 
                  quantity: float, price: Optional[float] = None, 
                  order_type: str = "MARKET", **kwargs):
        """Log trading order details"""
        order_data = {
            'action': action,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'order_type': order_type,
            'timestamp': datetime.now().isoformat()
        }
        
        if price:
            order_data['price'] = price
        
        order_data.update(kwargs)
        
        message = f"ORDER {action}: {side} {quantity} {symbol}"
        if price:
            message += f" @ {price}"
        message += f" ({order_type})"
        
        self.logger.info(message)
        self.logger.debug(f"Order details: {order_data}")
    
    def log_api_call(self, endpoint: str, method: str, params: Dict[str, Any], 
                     response_code: int, response_time: float):
        """Log API call details"""
        message = f"API {method} {endpoint} -> {response_code} ({response_time:.3f}s)"
        self.logger.debug(message)
        self.logger.debug(f"Request params: {params}")
    
    def log_error(self, error: Exception, context: str = ""):
        """Log error with context"""
        message = f"ERROR in {context}: {type(error).__name__}: {str(error)}"
        self.logger.error(message, exc_info=True)
    
    def log_position_update(self, symbol: str, position_amt: float, 
                           unrealized_pnl: float, entry_price: float):
        """Log position updates"""
        message = f"POSITION {symbol}: {position_amt} @ {entry_price} (PnL: {unrealized_pnl})"
        self.logger.info(message)
    
    def log_balance_update(self, asset: str, balance: float, available: float):
        """Log balance updates"""
        message = f"BALANCE {asset}: {balance} (Available: {available})"
        self.logger.info(message)
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)

# Global logger instance
logger = TradingLogger()

def log_execution_time(func):
    """Decorator to log function execution time"""
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        try:
            result = func(*args, **kwargs)
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.debug(f"{func.__name__} executed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.log_error(e, f"{func.__name__} (failed after {execution_time:.3f}s)")
            raise
    return wrapper