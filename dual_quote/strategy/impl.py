import asyncio
import logging
import time
from dataclasses import dataclass

from bot.strategy.base import StrategyBase
from bot.trader.leg.base import Leg

from .mixin.quote.impl import QuoteMixin
from .mixin.status import ArbitrageStatusMixin

LOGGER = logging.getLogger(__name__)


INTERVAL_BETWEEN_BUY_SELL = None  # 0.2


@dataclass
class DualQuoteStrategy(StrategyBase, ArbitrageStatusMixin, QuoteMixin):
    """
    Implements an arbitrage trading strategy, inheriting core functionality from Strategy
    and adding additional behavior for status tracking via StatusMixin.

    Attributes:
        quoting_leg (Leg): The leg used for quoting trades.
    """

    quoting_leg: Leg = None
    order_size: float = None

    latest_exposure: float = None
    latest_status: str = None
    idle_until: float = 0

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
        if self.quote_for_arb():
            # Yield control to ws communication task ASAP
            return

        self.post_trade()

    def quote_for_arb(self) -> bool:
        """return True if need to yield control to ws communication task"""

        # rare case: cancel redundant orders
        if self.cancel_redundant_quote_orders():
            return True

        symbol_info = self.quoting_leg.symbol_info
        bid_price = self.quoting_leg.depth[1]
        ask_price = self.quoting_leg.depth[2]

        base_total = self._get_base_total()
        base_available = self._get_base_available()

        quote_total = self._get_quote_total()
        quote_available = self._get_quote_available()

        # too much, urgent case
        if base_total * bid_price >= self.order_size * 2:
            if self.latest_status != "clearance":
                self.latest_status = "clearance"
                LOGGER.info(f"status: {self.latest_status}")

            # place sell order
            if self.hit_ask_side(self.order_size / ask_price, reason=f"excessive {symbol_info.base_asset}"):
                return True

        # check space to quote, cancel all order and stop quoting
        if ask_price - bid_price < symbol_info.quote_step_f * 3:
            for order in self.quoting_account.get_orders(active=True).values():
                if self.latest_status != "stopping":
                    self.latest_status = "stopping"
                    LOGGER.info(f"status: {self.latest_status}")

                return self._cancel_order(order, reason="spread too small")

            if self.latest_status != "stopped":
                self.latest_status = "stopped"
                LOGGER.info(f"status: {self.latest_status}")
            return False

        if self.latest_status == "idling":
            if time.time() < self.idle_until:
                return False
            self.idle_until = 0

        if base_total * bid_price >= self.order_size:
            # need to sell

            if self.latest_status == "buying":
                if INTERVAL_BETWEEN_BUY_SELL is not None:
                    self.latest_status = "idling"
                    LOGGER.info(f"status: {self.latest_status}")
                    self.idle_until = time.time() + INTERVAL_BETWEEN_BUY_SELL
                    return False

            ask_price = ask_price - symbol_info.quote_step_f * 1.5
            ask_price = symbol_info.round_price(ask_price, round_up=False)
            order_size = DualQuoteStrategy.rand_size_around(self.order_size, ask_price)

            ask_qty = order_size / ask_price
            if self.quote_ask_side(ask_qty, reason=f"need to sell {symbol_info.base_asset}"):
                if self.latest_status != "selling":
                    self.latest_status = "selling"
                    LOGGER.info(f"status: {self.latest_status}")

                LOGGER.info(f"ask qty: {ask_qty}, ask price: {ask_price}")
                # LOGGER.info(f"ask price: {ask_price}, order size: {order_size}")
                return True

        else:
            # need to buy

            if self.latest_status == "selling":
                if INTERVAL_BETWEEN_BUY_SELL is not None:
                    self.latest_status = "idling"
                    LOGGER.info(f"status: {self.latest_status}")
                    self.idle_until = time.time() + INTERVAL_BETWEEN_BUY_SELL
                    return False

            bid_price = bid_price + symbol_info.quote_step_f * 1.5
            bid_price = symbol_info.round_price(bid_price, round_up=True)
            order_size = DualQuoteStrategy.rand_size_around(self.order_size, bid_price)

            bid_qty = order_size / bid_price
            if self.quote_bid_side(bid_qty, reason=f"need to buy {symbol_info.base_asset}"):
                if self.latest_status != "buying":
                    self.latest_status = "buying"
                    LOGGER.info(f"status: {self.latest_status}")

                LOGGER.info(f"bid qty: {bid_qty}, bid price: {bid_price}")
                # LOGGER.info(f"bid price: {bid_price}, order size: {order_size}")
                return True

        return False

    def __repr__(self):
        return self.__class__.__name__

    @staticmethod
    def rand_size_around(size: float, seed: float):
        import random

        random.seed(seed)

        return size * random.randrange(70, 90) / 100
