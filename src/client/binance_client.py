#!/usr/bin/env python3
"""
Binance API client for futures trading
Handles authentication, order placement, and account management
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from binance import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
import requests
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from ..utils.config import config
    from ..utils.logger import logger, log_execution_time
    from .validator import validator
except ImportError:
    from utils.config import config
    from utils.logger import logger, log_execution_time
    from client.validator import validator

class BinanceFuturesClient:
    """Enhanced Binance Futures API client"""
    
    def __init__(self):
        self.client = Client(
            api_key=config.binance.api_key,
            api_secret=config.binance.api_secret,
            testnet=config.binance.testnet
        )
        
        logger.info(f"Binance client initialized (Testnet: {config.binance.testnet})")
        
        # Cache for symbol info
        self._symbol_info_cache = {}
        self._last_cache_update = 0
        self._cache_ttl = 300  # 5 minutes
    
    @log_execution_time
    def get_account_info(self) -> Dict[str, Any]:
        """Get futures account information"""
        try:
            account_info = self.client.futures_account()
            
            # Log balance updates
            for asset in account_info.get('assets', []):
                if float(asset['walletBalance']) > 0:
                    logger.log_balance_update(
                        asset['asset'],
                        float(asset['walletBalance']),
                        float(asset['availableBalance'])
                    )
            
            return account_info
        except BinanceAPIException as e:
            logger.log_error(e, "get_account_info")
            raise
    
    @log_execution_time
    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Get symbol trading information with caching"""
        current_time = time.time()
        
        # Check cache
        if (symbol in self._symbol_info_cache and 
            current_time - self._last_cache_update < self._cache_ttl):
            return self._symbol_info_cache[symbol]
        
        try:
            exchange_info = self.client.futures_exchange_info()
            
            # Update cache
            self._symbol_info_cache.clear()
            for sym_info in exchange_info['symbols']:
                self._symbol_info_cache[sym_info['symbol']] = sym_info
            
            self._last_cache_update = current_time
            
            if symbol not in self._symbol_info_cache:
                raise ValueError(f"Symbol {symbol} not found")
            
            return self._symbol_info_cache[symbol]
            
        except BinanceAPIException as e:
            logger.log_error(e, f"get_symbol_info for {symbol}")
            raise
    
    @log_execution_time
    def get_current_price(self, symbol: str) -> float:
        """Get current market price for symbol"""
        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            logger.log_error(e, f"get_current_price for {symbol}")
            raise
    
    @log_execution_time
    def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """Place a market order"""
        try:
            # Validate inputs
            order_data = {
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'order_type': 'MARKET'
            }
            validated_order = validator.validate_order_request(order_data)
            
            # Log order attempt
            logger.log_order(
                action="PLACING",
                symbol=validated_order.symbol,
                side=validated_order.side,
                quantity=validated_order.quantity,
                order_type="MARKET"
            )
            
            # Place order
            order_result = self.client.futures_create_order(
                symbol=validated_order.symbol,
                side=validated_order.side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=validated_order.quantity
            )
            
            # Log successful order
            logger.log_order(
                action="PLACED",
                symbol=validated_order.symbol,
                side=validated_order.side,
                quantity=validated_order.quantity,
                order_type="MARKET",
                order_id=order_result.get('orderId'),
                status=order_result.get('status')
            )
            
            return order_result
            
        except (BinanceAPIException, BinanceOrderException) as e:
            logger.log_error(e, f"place_market_order {side} {quantity} {symbol}")
            raise
    
    @log_execution_time
    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> Dict[str, Any]:
        """Place a limit order"""
        try:
            # Validate inputs
            order_data = {
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'price': price,
                'order_type': 'LIMIT'
            }
            validated_order = validator.validate_order_request(order_data)
            
            # Log order attempt
            logger.log_order(
                action="PLACING",
                symbol=validated_order.symbol,
                side=validated_order.side,
                quantity=validated_order.quantity,
                price=price,
                order_type="LIMIT"
            )
            
            # Place order
            order_result = self.client.futures_create_order(
                symbol=validated_order.symbol,
                side=validated_order.side,
                type=Client.ORDER_TYPE_LIMIT,
                timeInForce=Client.TIME_IN_FORCE_GTC,
                quantity=validated_order.quantity,
                price=price
            )
            
            # Log successful order
            logger.log_order(
                action="PLACED",
                symbol=validated_order.symbol,
                side=validated_order.side,
                quantity=validated_order.quantity,
                price=price,
                order_type="LIMIT",
                order_id=order_result.get('orderId'),
                status=order_result.get('status')
            )
            
            return order_result
            
        except (BinanceAPIException, BinanceOrderException) as e:
            logger.log_error(e, f"place_limit_order {side} {quantity} {symbol} @ {price}")
            raise
    
    @log_execution_time
    def place_stop_limit_order(self, symbol: str, side: str, quantity: float, 
                              stop_price: float, price: float) -> Dict[str, Any]:
        """Place a stop-limit order"""
        try:
            # Log order attempt
            logger.log_order(
                action="PLACING",
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                order_type="STOP_LIMIT"
            )
            
            # Place order
            order_result = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_STOP,
                timeInForce=Client.TIME_IN_FORCE_GTC,
                quantity=quantity,
                price=price,
                stopPrice=stop_price
            )
            
            # Log successful order
            logger.log_order(
                action="PLACED",
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                order_type="STOP_LIMIT",
                order_id=order_result.get('orderId'),
                status=order_result.get('status')
            )
            
            return order_result
            
        except (BinanceAPIException, BinanceOrderException) as e:
            logger.log_error(e, f"place_stop_limit_order {side} {quantity} {symbol}")
            raise
    
    @log_execution_time
    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an existing order"""
        try:
            result = self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            logger.info(f"Order {order_id} cancelled for {symbol}")
            return result
        except BinanceAPIException as e:
            logger.log_error(e, f"cancel_order {order_id} for {symbol}")
            raise
    
    @log_execution_time
    def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Get all open orders"""
        try:
            orders = self.client.futures_get_open_orders(symbol=symbol)
            logger.debug(f"Retrieved {len(orders)} open orders")
            return orders
        except BinanceAPIException as e:
            logger.log_error(e, "get_open_orders")
            raise
    
    @log_execution_time
    def get_order_status(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Get order status"""
        try:
            order = self.client.futures_get_order(symbol=symbol, orderId=order_id)
            return order
        except BinanceAPIException as e:
            logger.log_error(e, f"get_order_status {order_id}")
            raise
    
    @log_execution_time
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions"""
        try:
            positions = self.client.futures_position_information()
            
            # Log non-zero positions
            for position in positions:
                if float(position['positionAmt']) != 0:
                    logger.log_position_update(
                        position['symbol'],
                        float(position['positionAmt']),
                        float(position['unrealizedProfit']),
                        float(position['entryPrice'])
                    )
            
            return [pos for pos in positions if float(pos['positionAmt']) != 0]
        except BinanceAPIException as e:
            logger.log_error(e, "get_positions")
            raise
    
    @log_execution_time
    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[List]:
        """Get kline/candlestick data"""
        try:
            klines = self.client.futures_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            return klines
        except BinanceAPIException as e:
            logger.log_error(e, f"get_klines {symbol}")
            raise
    
    def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol exists and is tradable"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            return symbol_info.get('status') == 'TRADING'
        except:
            return False
    
    def get_min_notional(self, symbol: str) -> float:
        """Get minimum notional value for symbol"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            for filter_info in symbol_info.get('filters', []):
                if filter_info['filterType'] == 'MIN_NOTIONAL':
                    return float(filter_info['notional'])
            return 0.0
        except:
            return 0.0
    
    def get_price_precision(self, symbol: str) -> int:
        """Get price precision for symbol"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            return symbol_info.get('pricePrecision', 2)
        except:
            return 2
    
    def get_quantity_precision(self, symbol: str) -> int:
        """Get quantity precision for symbol"""
        try:
            symbol_info = self.get_symbol_info(symbol)
            return symbol_info.get('quantityPrecision', 3)
        except:
            return 3