#!/usr/bin/env python3
"""
Input validation for trading operations
Validates symbols, quantities, prices, and other trading parameters
"""

import re
from typing import Union, List, Optional
from decimal import Decimal, InvalidOperation
from pydantic import BaseModel, validator, Field
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from ..utils.config import config
    from ..utils.logger import logger
except ImportError:
    from utils.config import config
    from utils.logger import logger

class OrderRequest(BaseModel):
    """Base order request validation model"""
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    side: str = Field(..., description="Order side: BUY or SELL")
    quantity: float = Field(..., gt=0, description="Order quantity")
    order_type: str = Field(default="MARKET", description="Order type")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not v or len(v) < 6:
            raise ValueError("Symbol must be at least 6 characters")
        
        # Basic format validation (letters and numbers only)
        if not re.match(r'^[A-Z0-9]+$', v.upper()):
            raise ValueError("Symbol must contain only uppercase letters and numbers")
        
        return v.upper()
    
    @validator('side')
    def validate_side(cls, v):
        valid_sides = ['BUY', 'SELL']
        if v.upper() not in valid_sides:
            raise ValueError(f"Side must be one of: {valid_sides}")
        return v.upper()
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be positive")
        
        if v < config.trading.min_quantity:
            raise ValueError(f"Quantity must be at least {config.trading.min_quantity}")
        
        if v > config.trading.max_quantity:
            raise ValueError(f"Quantity cannot exceed {config.trading.max_quantity}")
        
        return round(v, config.trading.quantity_precision)
    
    @validator('order_type')
    def validate_order_type(cls, v):
        valid_types = ['MARKET', 'LIMIT', 'STOP_MARKET', 'STOP', 'TAKE_PROFIT_MARKET', 'TAKE_PROFIT']
        if v.upper() not in valid_types:
            raise ValueError(f"Order type must be one of: {valid_types}")
        return v.upper()

class LimitOrderRequest(OrderRequest):
    """Limit order validation model"""
    price: float = Field(..., gt=0, description="Limit price")
    order_type: str = Field(default="LIMIT")
    
    @validator('price')
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError("Price must be positive")
        return round(v, config.trading.price_precision)

class StopOrderRequest(OrderRequest):
    """Stop order validation model"""
    stop_price: float = Field(..., gt=0, description="Stop trigger price")
    price: Optional[float] = Field(None, gt=0, description="Limit price for stop-limit orders")
    
    @validator('stop_price')
    def validate_stop_price(cls, v):
        if v <= 0:
            raise ValueError("Stop price must be positive")
        return round(v, config.trading.price_precision)
    
    @validator('price')
    def validate_limit_price(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Limit price must be positive")
        if v is not None:
            return round(v, config.trading.price_precision)
        return v

class OCOOrderRequest(BaseModel):
    """OCO (One-Cancels-Other) order validation model"""
    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., description="Order side: BUY or SELL")
    quantity: float = Field(..., gt=0, description="Order quantity")
    price: float = Field(..., gt=0, description="Limit order price")
    stop_price: float = Field(..., gt=0, description="Stop order trigger price")
    stop_limit_price: Optional[float] = Field(None, gt=0, description="Stop limit price")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        return OrderRequest.validate_symbol(v)
    
    @validator('side')
    def validate_side(cls, v):
        return OrderRequest.validate_side(v)
    
    @validator('quantity')
    def validate_quantity(cls, v):
        return OrderRequest.validate_quantity(v)
    
    @validator('price', 'stop_price', 'stop_limit_price')
    def validate_prices(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Price must be positive")
        if v is not None:
            return round(v, config.trading.price_precision)
        return v

class TWAPOrderRequest(BaseModel):
    """TWAP order validation model"""
    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., description="Order side: BUY or SELL")
    total_quantity: float = Field(..., gt=0, description="Total quantity to execute")
    duration_minutes: int = Field(..., gt=0, le=1440, description="Execution duration in minutes")
    interval_minutes: int = Field(default=5, gt=0, description="Interval between orders in minutes")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        return OrderRequest.validate_symbol(v)
    
    @validator('side')
    def validate_side(cls, v):
        return OrderRequest.validate_side(v)
    
    @validator('total_quantity')
    def validate_total_quantity(cls, v):
        if v <= 0:
            raise ValueError("Total quantity must be positive")
        if v > config.trading.max_quantity * 10:  # Allow larger total for TWAP
            raise ValueError(f"Total quantity too large")
        return v
    
    @validator('interval_minutes')
    def validate_interval(cls, v, values):
        if 'duration_minutes' in values and v >= values['duration_minutes']:
            raise ValueError("Interval must be less than total duration")
        return v

class GridOrderRequest(BaseModel):
    """Grid trading validation model"""
    symbol: str = Field(..., description="Trading symbol")
    quantity_per_grid: float = Field(..., gt=0, description="Quantity per grid level")
    grid_count: int = Field(..., gt=1, le=50, description="Number of grid levels")
    lower_price: float = Field(..., gt=0, description="Lower price boundary")
    upper_price: float = Field(..., gt=0, description="Upper price boundary")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        return OrderRequest.validate_symbol(v)
    
    @validator('upper_price')
    def validate_price_range(cls, v, values):
        if 'lower_price' in values and v <= values['lower_price']:
            raise ValueError("Upper price must be greater than lower price")
        return round(v, config.trading.price_precision)
    
    @validator('lower_price')
    def validate_lower_price(cls, v):
        return round(v, config.trading.price_precision)

class TradingValidator:
    """Main validation class for trading operations"""
    
    @staticmethod
    def validate_symbol_format(symbol: str) -> bool:
        """Validate symbol format"""
        try:
            OrderRequest.validate_symbol(symbol)
            return True
        except ValueError as e:
            logger.warning(f"Symbol validation failed: {e}")
            return False
    
    @staticmethod
    def validate_price_precision(price: float, symbol: str = None) -> float:
        """Validate and round price to appropriate precision"""
        try:
            return round(price, config.trading.price_precision)
        except (TypeError, ValueError) as e:
            logger.error(f"Price precision validation failed: {e}")
            raise ValueError(f"Invalid price format: {price}")
    
    @staticmethod
    def validate_quantity_precision(quantity: float) -> float:
        """Validate and round quantity to appropriate precision"""
        try:
            return round(quantity, config.trading.quantity_precision)
        except (TypeError, ValueError) as e:
            logger.error(f"Quantity precision validation failed: {e}")
            raise ValueError(f"Invalid quantity format: {quantity}")
    
    @staticmethod
    def validate_percentage(percentage: float) -> bool:
        """Validate percentage value (0-100)"""
        return 0 <= percentage <= 100
    
    @staticmethod
    def sanitize_symbol(symbol: str) -> str:
        """Sanitize and format symbol"""
        if not symbol:
            raise ValueError("Symbol cannot be empty")
        return symbol.upper().strip()
    
    @staticmethod
    def validate_order_request(order_data: dict) -> OrderRequest:
        """Validate complete order request"""
        try:
            if order_data.get('order_type') == 'LIMIT' and 'price' in order_data:
                return LimitOrderRequest(**order_data)
            else:
                return OrderRequest(**order_data)
        except Exception as e:
            logger.log_error(e, "Order validation")
            raise ValueError(f"Order validation failed: {str(e)}")

# Create global validator instance
validator = TradingValidator()