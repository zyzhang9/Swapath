import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Any

from bot.strategy.base import StrategyBase
from bot.trader.leg.base import Leg

from .mixin.quote.impl import QuoteMixin
from .mixin.status import ArbitrageStatusMixin

LOGGER = logging.getLogger(__name__)


MINIMUM_QUOTE_AGE = None
SAME_TRADE_MINIMUM_PERIOD = 0.01 

@dataclass
class DualHitStrategy(StrategyBase, ArbitrageStatusMixin, QuoteMixin):
    """
    Implements an arbitrage trading strategy, inheriting core functionality from Strategy
    and adding additional behavior for status tracking via StatusMixin.

    Attributes:
        quoting_leg (Leg): The leg used for quoting trades.
    """

    quoting_leg: Leg = None
    order_size: float = None

    latest_exposure: float = None
    to_buy: Any = (None, 0)
    to_sell: Any = (None, 0)
    bought: Any = (None, 0)
    sold: Any = (None, 0)

    def __post_init__(self):
        """
        Initialize the ArbitrageStrategy instance by setting up the quoting, hedging,
        and referencing legs. Validates the configuration to ensure the pricer has
        exactly one leg.
        """
        super().__post_init__()

        # Assign quoting and hedging legs from the provided legs configuration
        self.quoting_leg = self.legs["quoting"]

        assert len(self.executor.accounts) == 1, "Wash trading strategy requires exactly one account."
        self.quoting_account = self.executor.accounts[0]

        LOGGER.info(f"order size: {self.order_size}")

    async def trade(self):
        # assume it is good order size
        symbol_info = self.quoting_leg.symbol_info
        assert self.order_size > symbol_info.value_min

        bid_price = self.quoting_leg.depth[2]
        assert self.order_size > bid_price * float(symbol_info.base_min)

        self.print_quote_pulse()

        while True:
            await self._one_round()

            # Yield control to ws communication task
            await asyncio.sleep(0.001)

    async def _one_round(self):
        # Perform a BBO check to check all orderbooks are not delayed
        try:
            self.check_bbo()
        except TimeoutError as e:
            LOGGER.error(f"bbo is not up-to-date: {e}")
            await asyncio.sleep(0.009)
            return

        # Check for arbitrage opportunities and take action
        if self.hit_for_arb():
            # Yield control to ws communication task ASAP
            return

        self.post_trade()

    def hit_for_arb(self) -> bool:
        """return True if need to yield control to ws communication task"""

        # # rare case: cancel redundant orders
        # if self.cancel_redundant_quote_orders():
        #     return True

        symbol_info = self.quoting_leg.symbol_info
        bid_price = self.quoting_leg.depth[1]
        ask_price = self.quoting_leg.depth[2]

        base_total = self._get_base_total()
        base_available = self._get_base_available()

        quote_total = self._get_quote_total()
        quote_available = self._get_quote_available()

        # too much, urgent case
        if base_total * bid_price >= self.order_size * 4:
            # place sell order
            if self.hit_ask_side(self.order_size / ask_price, reason=f"excessive {symbol_info.base_asset}"):
                return True

        # too little, urgent case
        if base_total * bid_price <= self.order_size:
            # place buy order
            if self.hit_bid_side(self.order_size / bid_price, reason=f"insufficient {symbol_info.base_asset}"):
                return True

        # check space to hit, cancel all order and stop quoting
        if ask_price - bid_price < symbol_info.quote_step_f * 2:
            for order in self.quoting_account.get_orders(symbol=self.quoting_leg.symbol, active=True).values():
                return self._cancel_order(order, reason="spread too small")
            return False

        if base_available * bid_price >= symbol_info.value_min:
            # may sell

            bid_qty = self.quoting_leg.depth[5]
            target_qty = DualHitStrategy.rand_size_around(self.order_size, bid_price) / bid_price
            target_qty = symbol_info.round_size(target_qty)

            if abs(bid_qty - target_qty) <= symbol_info.base_step_f * 2:
                bid_qty = min(bid_qty, target_qty)

                # recognized quote

                if (bid_price, bid_qty) == self.sold[0]:
                    if time.time() - self.sold[1] < SAME_TRADE_MINIMUM_PERIOD:
                        # just sold it
                        return False
                    # clear sold flag
                    self.sold = (None, time.time())

                if (bid_price, bid_qty) != self.to_sell[0]:
                    # new quote
                    self.to_sell = ((bid_price, bid_qty), time.time())
                    if MINIMUM_QUOTE_AGE is not None:
                        # return to check if need to wait
                        return False

                if MINIMUM_QUOTE_AGE is not None:
                    if time.time() - self.to_sell[1] < MINIMUM_QUOTE_AGE:
                        return False

                # take a random order
                if self.hit_ask_side(bid_qty, reason=f"ready to sell {symbol_info.base_asset}", time_in_force="fok"):
                    self.to_sell = (None, 0)
                    self.sold = ((bid_price, bid_qty), time.time())
                    LOGGER.info(f"bid qty: {bid_qty}, bid price: {bid_price}, target qty: {target_qty}")
                    return True

        if quote_available >= symbol_info.value_min:
            # may buy

            ask_qty = self.quoting_leg.depth[6]
            target_qty = DualHitStrategy.rand_size_around(self.order_size, ask_price) / ask_price
            target_qty = symbol_info.round_size(target_qty)

            if abs(ask_qty - target_qty) <= symbol_info.base_step_f * 2:
                ask_qty = min(ask_qty, target_qty)

                # recognized quote

                if (ask_price, ask_qty) == self.bought[0]:
                    if time.time() - self.bought[1] < SAME_TRADE_MINIMUM_PERIOD:
                        # just bought it
                        return False
                    # clear bought flag
                    self.bought = (None, time.time())

                if (ask_price, ask_qty) != self.to_buy[0]:
                    # new quote
                    self.to_buy = ((ask_price, ask_qty), time.time())
                    if MINIMUM_QUOTE_AGE is not None:
                        # return to check if need to wait
                        return False

                if MINIMUM_QUOTE_AGE is not None:
                    if time.time() - self.to_buy[1] < MINIMUM_QUOTE_AGE:
                        return False

                # take a random order
                if self.hit_bid_side(ask_qty, reason=f"ready to buy {symbol_info.base_asset}", time_in_force="fok"):
                    self.to_buy = (None, 0)
                    self.bought = ((ask_price, ask_qty), time.time())
                    LOGGER.info(f"ask qty: {ask_qty}, ask price: {ask_price}, target qty: {target_qty}")
                    return True

        return False

    def __repr__(self):
        return self.__class__.__name__

    @staticmethod
    def rand_size_around(size: float, seed: float):
        import random

        random.seed(seed)

        return size * random.randrange(70, 90) / 100
