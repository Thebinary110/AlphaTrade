#!/usr/bin/env python3
"""
Configuration management for Binance Trading Bot
Handles API credentials, trading parameters, and environment settings
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class BinanceConfig:
    """Binance API configuration"""
    api_key: str
    api_secret: str
    testnet: bool = True
    base_url: str = "https://testnet.binancefuture.com"

@dataclass
class TradingConfig:
    """Trading parameters and limits"""
    default_symbol: str = "BTCUSDT"
    min_quantity: float = 0.001
    max_quantity: float = 100.0
    price_precision: int = 2
    quantity_precision: int = 3

@dataclass
class LoggingConfig:
    """Logging configuration"""
    log_file: str = "bot.log"
    log_level: str = "INFO"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

class ConfigManager:
    """Centralized configuration management"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.binance = self._load_binance_config()
        self.trading = self._load_trading_config()
        self.logging = self._load_logging_config()
    
    def _load_binance_config(self) -> BinanceConfig:
        """Load Binance API configuration"""
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        
        if not api_key or not api_secret:
            raise ValueError(
                "Missing API credentials. Please set BINANCE_API_KEY and BINANCE_API_SECRET "
                "environment variables or create a .env file"
            )
        
        return BinanceConfig(
            api_key=api_key,
            api_secret=api_secret,
            testnet=os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'
        )
    
    def _load_trading_config(self) -> TradingConfig:
        """Load trading configuration"""
        config_data = self._load_json_config()
        trading_data = config_data.get('trading', {})
        
        return TradingConfig(
            default_symbol=trading_data.get('default_symbol', 'BTCUSDT'),
            min_quantity=trading_data.get('min_quantity', 0.001),
            max_quantity=trading_data.get('max_quantity', 100.0),
            price_precision=trading_data.get('price_precision', 2),
            quantity_precision=trading_data.get('quantity_precision', 3)
        )
    
    def _load_logging_config(self) -> LoggingConfig:
        """Load logging configuration"""
        config_data = self._load_json_config()
        logging_data = config_data.get('logging', {})
        
        return LoggingConfig(
            log_file=logging_data.get('log_file', 'bot.log'),
            log_level=logging_data.get('log_level', 'INFO'),
            max_file_size=logging_data.get('max_file_size', 10 * 1024 * 1024),
            backup_count=logging_data.get('backup_count', 5)
        )
    
    def _load_json_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_file):
            return {}
        
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    
    def save_config(self) -> None:
        """Save current configuration to JSON file"""
        config_data = {
            'trading': {
                'default_symbol': self.trading.default_symbol,
                'min_quantity': self.trading.min_quantity,
                'max_quantity': self.trading.max_quantity,
                'price_precision': self.trading.price_precision,
                'quantity_precision': self.trading.quantity_precision
            },
            'logging': {
                'log_file': self.logging.log_file,
                'log_level': self.logging.log_level,
                'max_file_size': self.logging.max_file_size,
                'backup_count': self.logging.backup_count
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f, indent=2)

# Global configuration instance
config = ConfigManager()