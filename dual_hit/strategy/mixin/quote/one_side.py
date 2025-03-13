import logging

from .order_action import QuoteOrderActionMixin

LOGGER = logging.getLogger(__name__)


class OneSideQuoteMixin(QuoteOrderActionMixin):
    # def quote_bid_side(self, bid_qty: float, reason: str = None):  # unsigned
    #     depth = self.quoting_leg.depth
    #     assert depth[1] < depth[2]

    #     symbol_info = self.quoting_leg.symbol_info
    #     assert bid_qty > symbol_info.base_min

    #     # cancel sell orders
    #     for order in self.quoting_account.get_orders(active=True, side="sell").values():
    #         return self._cancel_order(order, reason=reason)

    #     # cancel unpromising buy orders
    #     for order in self.quoting_account.get_orders(active=True, side="buy").values():
    #         if order.price < depth[1] - 1e-6:
    #             return self._cancel_order(order, reason="order is not the best bid")

    #         if depth[5] > order.quantity + 1e-6:
    #             return self._cancel_order(order, reason="order is not the unique bid")

    #         # already the best bid
    #         return False

    #     bid_price = depth[1] + symbol_info.quote_step_f
    #     assert bid_price * bid_qty > symbol_info.value_min

    #     if bid_qty * bid_price > self._get_quote_available():
    #         return False

    #     return self._place_bid_order_maker(bid_price, bid_qty, reason=reason)

    def hit_bid_side(self, bid_qty: float, reason: str = None):  # unsigned
        depth = self.quoting_leg.depth
        assert depth[1] < depth[2]

        symbol_info = self.quoting_leg.symbol_info
        assert bid_qty > symbol_info.base_min

        # cancel sell orders
        for order in self.quoting_account.get_orders(active=True, side="sell").values():
            return self._cancel_order(order, reason=reason)

        # cancel unpromising buy orders
        for order in self.quoting_account.get_orders(active=True, side="buy").values():
            if order.price < depth[1] - 1e-6:
                return self._cancel_order(order, reason="order is not the best bid")

        if self.quoting_account.get_orders(active=True, side="buy").values():
            return False

        bid_price = depth[2]
        assert bid_price * bid_qty > symbol_info.value_min

        if bid_qty * bid_price > self._get_quote_available():
            return False

        return self._place_bid_order_taker(bid_price, bid_qty, reason=reason)

    # def quote_ask_side(self, ask_qty: float, reason: str = None):  # unsigned
    #     depth = self.quoting_leg.depth
    #     assert depth[1] < depth[2]

    #     symbol_info = self.quoting_leg.symbol_info
    #     assert ask_qty > symbol_info.base_min

    #     # cancel buy orders
    #     for order in self.quoting_account.get_orders(active=True, side="buy").values():
    #         return self._cancel_order(order, reason=reason)

    #     # cancel unpromising sell orders
    #     for order in self.quoting_account.get_orders(active=True, side="sell").values():
    #         if order.price > depth[2] + 1e-6:
    #             return self._cancel_order(order, reason="order is not the best ask")

    #         if depth[6] > order.quantity + 1e-6:
    #             return self._cancel_order(order, reason="order is not the unique ask")

    #         # already the best ask
    #         return False

    #     if ask_qty > self._get_base_available():
    #         return False

    #     ask_price = depth[2] - symbol_info.quote_step_f
    #     assert ask_price * ask_qty > symbol_info.value_min

    #     return self._place_ask_order_maker(ask_price, ask_qty, reason=reason)

    def hit_ask_side(self, ask_qty: float, reason: str = None):  # unsigned
        depth = self.quoting_leg.depth
        assert depth[1] < depth[2]

        symbol_info = self.quoting_leg.symbol_info
        assert ask_qty > symbol_info.base_min

        # cancel buy orders
        for order in self.quoting_account.get_orders(active=True, side="buy").values():
            return self._cancel_order(order, reason=reason)

        # cancel unpromising sell orders
        for order in self.quoting_account.get_orders(active=True, side="sell").values():
            if order.price < depth[1] - 1e-6:
                return self._cancel_order(order, reason="order does not target the best bid")

        if self.quoting_account.get_orders(active=True, side="sell").values():
            return False

        if ask_qty > self._get_base_available():
            return False

        ask_price = depth[1]
        assert ask_price * ask_qty > symbol_info.value_min

        return self._place_ask_order_taker(ask_price, ask_qty, reason=reason)
