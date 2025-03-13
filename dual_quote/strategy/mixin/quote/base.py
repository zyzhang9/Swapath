import logging
from collections.abc import Callable
from functools import wraps
from typing import List

from bot.drivers.trading_data.order import Order
from bot.executor.account import Account
from bot.executor.impl import Executor
from bot.trader.leg.base import Leg

LOGGER = logging.getLogger(__name__)


class _Base:
    quoting_leg: Leg
    quoting_account: Account
    executor: Executor

    @staticmethod
    def check_sign(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            res = func(*args, **kwargs)
            if res < -1e-6:
                LOGGER.error(f"method {func.__name__} return {res}")
            return res

        return wrapper


class _Asset(_Base):
    @_Base.check_sign
    def _get_base_total(self) -> float:
        asset = self.quoting_leg.symbol_info.base_asset
        return self.quoting_account.get_balance(asset).net

    @_Base.check_sign
    def _get_base_available(self) -> float:
        asset = self.quoting_leg.symbol_info.base_asset
        return self.quoting_account.get_balance(asset).available

    @_Base.check_sign
    def _get_quote_total(self) -> float:
        asset = self.quoting_leg.symbol_info.quote_asset
        return self.quoting_account.get_balance(asset).net

    @_Base.check_sign
    def _get_quote_available(self) -> float:
        asset = self.quoting_leg.symbol_info.quote_asset
        return self.quoting_account.get_balance(asset).available

    @_Base.check_sign
    def _get_max_base_position(self) -> float:
        # get current position
        base_asset_total = self._get_base_total()
        quote_asset_total = self._get_quote_total()

        # get depth and calculate net
        mid = self.quoting_leg.depth[4]
        asset_total_in_base = base_asset_total + quote_asset_total / mid

        # apply rel-max and abs-max
        res = min(asset_total_in_base * self.rel_max_balance, self.abs_max_balance)
        return max(res, 0)


class _Order(_Asset):
    def _get_current_bid_orders(self) -> List[Order]:
        return list(
            sorted(
                self.quoting_account.get_orders(symbol=self.quoting_leg.symbol, active=True, side="buy").values(),
                key=lambda order: order.price,
                reverse=True,
            )
        )

    def _get_current_ask_orders(self) -> List[Order]:
        return list(
            sorted(
                self.quoting_account.get_orders(symbol=self.quoting_leg.symbol, active=True, side="sell").values(),
                key=lambda order: order.price,
            )
        )


class QuoteMixinBase(_Order):
    pass
