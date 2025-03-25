import logging
import math

from bot.drivers.trading_data.order import Order
from bot.executor.order_action.amendment import OrderNoAmendment
from bot.executor.order_action.placement import OrderPlacement

from ..order import OrderMixin
from .base import QuoteMixinBase

LOGGER = logging.getLogger(__name__)


class QuoteOrderActionMixin(QuoteMixinBase, OrderMixin):
    def _cancel_order(self, order: Order, reason: str = None) -> bool:
        if reason:
            LOGGER.debug(
                "[trade.quote] canceling %s %s order %s",
                reason,
                "bid" if order.side == "buy" else "ask",
                order.client_id_or_id,
            )
        else:
            LOGGER.debug(
                "[trade.quote] canceling %s order %s",
                "bid" if order.side == "buy" else "ask",
                order.client_id_or_id,
            )

        if cancel_order_cmd := self.quoting_leg.generate_cancel_order_cmd(order):
            return self.executor.execute(self.quoting_account, cancel_order_cmd, reason=reason)

    def _place_order(
        self,
        place_order_cmd: OrderPlacement,
        reason: str = None,
    ):
        order = place_order_cmd.order

        if reason:
            LOGGER.debug(
                "[trade.quote] placing %s %s order %s",
                reason,
                "bid" if order.side == "buy" else "ask",
                order.client_id_or_id,
            )
        else:
            LOGGER.debug(
                "[trade.quote] placing %s order %s",
                "bid" if order.side == "buy" else "ask",
                order.client_id_or_id,
            )

        return self.executor.execute(self.quoting_account, place_order_cmd, reason=reason)

    def _place_bid_order_maker(self, price: float, quantity: float, *args, reason: str = "new quote"):
        if not (place_order_cmd := self.quoting_leg.generate_maker_order_cmd(quantity, price=price)):
            return False

        return self._place_order(place_order_cmd, reason=reason)

    def _place_ask_order_maker(self, price: float, quantity: float, *args, reason: str = "new quote"):
        if not (place_order_cmd := self.quoting_leg.generate_maker_order_cmd(-quantity, price=price)):
            return False

        return self._place_order(place_order_cmd, reason=reason)

    def _place_bid_order_taker(
        self, price: float, quantity: float, *args, time_in_force: str = "gtc", reason: str = "new quote"
    ):
        if not (
            place_order_cmd := self.quoting_leg.generate_taker_order_cmd(
                quantity, price=price, time_in_force=time_in_force
            )
        ):
            return False

        return self._place_order(place_order_cmd, reason=reason)

    def _place_ask_order_taker(
        self, price: float, quantity: float, *args, time_in_force: str = "gtc", reason: str = "new quote"
    ):
        if not (
            place_order_cmd := self.quoting_leg.generate_taker_order_cmd(
                -quantity, price=price, time_in_force=time_in_force
            )
        ):
            return False

        return self._place_order(place_order_cmd, reason=reason)

    def _adjust_order(self, order: Order, price: float, quantity: float, *args, reason: str = None):
        if math.isclose(price, order.price) and math.isclose(quantity, order.quantity):
            LOGGER.debug("[order.ignore] %s, cannot be amended to %f %f, %s", order, price, quantity, reason)
            return False

        if not (
            amend_order_cmd := self.quoting_leg.generate_amend_order_cmd(
                order, price=price, quantity=quantity, post_only=True
            )
        ):
            return False

        if isinstance(amend_order_cmd, OrderNoAmendment):
            LOGGER.debug("[order.ignore] %s, cannot be amended to %f %f, %s", order, price, quantity, reason)
            return False

        return self.executor.execute(self.quoting_account, amend_order_cmd, reason=reason)
