import logging
import time

import humanize
from bot.executor.account import Account
from bot.strategy.mixin import StatusMixinBase
from bot.trader.leg.base import Leg
from tabulate import tabulate

from .order import OrderMixin

LOGGER = logging.getLogger(__name__)


class ArbitrageStatusMixin(StatusMixinBase, OrderMixin):
    """
    A mixin to manage the status and health of trading legs (quoting, hedging, and referencing).
    Includes functionality for checking best bid/offer (BBO) validity, data delays, and backlogs.
    """

    quoting_leg: Leg = None

    quoting_account: Account = None

    latest_order_prices = None

    def _synthesize_quoting_abstract(self) -> str:
        # if not self.quoting_account.stable:
        #     return None

        bid0, ask0 = self.quoting_leg.depth[1:3]
        bid0_qty, ask0_qty = self.quoting_leg.depth[5:7]

        active_orders = list(self.quoting_account.get_orders(symbol=self.quoting_leg.symbol, active=True).values())
        # active_orders = sorted(active_orders, key=lambda order: order.price, reverse=True)
        order_prices = sorted([(order.price, order.unfilled) for order in active_orders])

        # all_prices = sorted([bid0, ask0, *order_prices])
        if self.latest_order_prices == order_prices:
            return None
        self.latest_order_prices = order_prices

        def __bid_price_depth(price: float):
            return -OrderMixin._bid_price_depth(price, bid0)

        def __ask_price_depth(price: float):
            return OrderMixin._ask_price_depth(price, ask0)

        headers = [
            "",
            "Id",
            "Price",
            "Distance to bbo",
            "Quantity",
            "Value",
            "Status",
            "Time since last update",
        ]
        rows = []
        for order in active_orders:
            if order.side == "sell":
                rows.append(
                    [
                        order.client_order_id,
                        order.order_id,
                        order.price,
                        __ask_price_depth(order.price),
                        order.unfilled,
                        order.unfilled * order.price,
                        order.status,
                        humanize.precisedelta(time.time() - order.timestamp, minimum_unit="microseconds") + " ago",
                    ]
                )

        rows.append([None, "ask (best)", ask0, __ask_price_depth(ask0), ask0_qty, None, None, None])
        rows.append([None, "bid (best)", bid0, __bid_price_depth(bid0), bid0_qty, None, None, None])

        for order in active_orders:
            if order.side == "buy":
                rows.append(
                    [
                        order.client_order_id,
                        order.order_id,
                        order.price,
                        __bid_price_depth(order.price),
                        order.unfilled,
                        order.unfilled * order.price,
                        order.status,
                        humanize.precisedelta(time.time() - order.timestamp, minimum_unit="microseconds") + " ago",
                    ]
                )

        rows = sorted(rows, key=lambda row: row[2], reverse=True)
        return tabulate(rows, headers=headers, tablefmt="simple_outline")

    def print_quote_pulse(self):
        quoting_abstract = self._synthesize_quoting_abstract()
        if quoting_abstract:
            LOGGER.info("[quote.pulse] %s\n%s", self.quoting_leg.symbol, quoting_abstract)

    def post_trade(self):
        self.quoting_account.remove_expired_orders()

        self.print_quote_pulse()
