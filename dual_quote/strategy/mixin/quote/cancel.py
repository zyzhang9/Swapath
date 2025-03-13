import logging
import time

from .order_action import QuoteOrderActionMixin

LOGGER = logging.getLogger(__name__)


class QuoteCancelationMixin(QuoteOrderActionMixin):
    def _cancel_redundant_bid_orders(self) -> None:
        # get current orders
        current_bid_orders = self._get_current_bid_orders()

        for bid_order in current_bid_orders:
            if time.time() - bid_order.timestamp > 15:
                return self._cancel_order(bid_order, reason="redundant")

        # filter out orders to cancel
        bid_orders_to_cancel = current_bid_orders[1:]

        for bid_order in bid_orders_to_cancel:
            return self._cancel_order(bid_order, reason="redundant")

    def _cancel_redundant_ask_orders(self) -> None:
        # get current orders
        current_ask_orders = self._get_current_ask_orders()

        for ask_order in current_ask_orders:
            if time.time() - ask_order.timestamp > 15:
                return self._cancel_order(ask_order, reason="redundant")

        # filter out orders to cancel
        ask_orders_to_cancel = current_ask_orders[1:]

        for ask_order in ask_orders_to_cancel:
            return self._cancel_order(ask_order, reason="redundant")

    def cancel_redundant_quote_orders(self) -> bool:
        return self._cancel_redundant_bid_orders() or self._cancel_redundant_ask_orders()
