import logging

from .order_action import QuoteOrderActionMixin

LOGGER = logging.getLogger(__name__)


class QuoteCancelationMixin(QuoteOrderActionMixin):
    def _cancel_redundant_bid_orders(self) -> None:
        # get current orders
        current_bid_orders = self._get_current_bid_orders()

        # filter out orders to cancel
        bid_orders_to_cancel = current_bid_orders[1:]

        for bid_order in bid_orders_to_cancel:
            self._cancel_order(bid_order, reason="redundant")

    def _cancel_redundant_ask_orders(self) -> None:
        # get current orders
        current_ask_orders = self._get_current_ask_orders()

        # filter out orders to cancel
        ask_orders_to_cancel = current_ask_orders[1:]

        for ask_order in ask_orders_to_cancel:
            self._cancel_order(ask_order, reason="redundant")

    def cancel_redundant_quote_orders(self) -> bool:
        self._cancel_redundant_bid_orders()
        self._cancel_redundant_ask_orders()

        return False
