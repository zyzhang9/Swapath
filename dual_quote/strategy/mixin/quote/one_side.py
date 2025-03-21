import logging
import time

from .order_action import QuoteOrderActionMixin

LOGGER = logging.getLogger(__name__)

MINIMUM_QUOTE_LIFETIME = None  # 0.2

class OneSideQuoteMixin(QuoteOrderActionMixin):
    def quote_bid_side(self, bid_price: float, bid_qty: float, reason: str = None):  # unsigned
        depth = self.quoting_leg.depth
        assert depth[1] < depth[2]

        symbol_info = self.quoting_leg.symbol_info
        assert bid_qty > symbol_info.base_min

        # cancel sell orders
        for order in self.quoting_account.get_orders(symbol=self.quoting_leg.symbol, active=True, side="sell").values():
            return self._cancel_order(order, reason=reason)

        # cancel unpromising buy orders
        for order in self.quoting_account.get_orders(symbol=self.quoting_leg.symbol, active=True, side="buy").values():
            if order.price < depth[1] - 1e-6:
                return self._cancel_order(order, reason=f"order is not the best bid, i.e., {order.price} vs {depth[1]}")

            if order.filled > 1e-6:
                return self._cancel_order(order, reason=f"order filled, i.e., {order.filled} vs 0")

            if order.price == depth[1]:
                order_size = self.rand_size_around(self.order_size, order.price)
                if abs(depth[5] - order_size) > self.quoting_leg.symbol_info.base_step_f * 2 * order.price:
                    if MINIMUM_QUOTE_LIFETIME is None or time.time() - order.timestamp > MINIMUM_QUOTE_LIFETIME:
                        return self._cancel_order(
                            order, reason=f"order size will not be taken, i.e., {depth[5]} vs {order_size}"
                        )
            # if depth[5] > (order.quantity - order.filled) + 1e-6:
            #     if MINIMUM_QUOTE_LIFETIME is None or time.time() - order.timestamp > MINIMUM_QUOTE_LIFETIME:
            #         return self._cancel_order(
            #             order, reason=f"order is not the unique bid, i.e., {order.quantity} vs {depth[5]}"
            #         )

            # already the best bid
            return False

        # bid_price = depth[1] + symbol_info.quote_step_f * 0.5
        # bid_price = symbol_info.round_price(bid_price, round_up=True)
        assert bid_price * bid_qty > symbol_info.value_min

        if bid_qty * bid_price > self._get_quote_available():
            return False

        return self._place_bid_order_maker(bid_price, bid_qty, reason=reason)

    def quote_ask_side(self, ask_price: float, ask_qty: float, reason: str = None):  # unsigned
        depth = self.quoting_leg.depth
        assert depth[1] < depth[2]

        symbol_info = self.quoting_leg.symbol_info
        assert ask_qty > symbol_info.base_min

        # cancel buy orders
        for order in self.quoting_account.get_orders(symbol=self.quoting_leg.symbol, active=True, side="buy").values():
            return self._cancel_order(order, reason=reason)

        # cancel unpromising sell orders
        for order in self.quoting_account.get_orders(symbol=self.quoting_leg.symbol, active=True, side="sell").values():
            if order.price > depth[2] + 1e-6:
                return self._cancel_order(order, reason=f"order is not the best ask, i.e., {order.price} vs {depth[2]}")

            if order.filled > 1e-6:
                return self._cancel_order(order, reason=f"order filled, i.e., {order.filled} vs 0")

            if order.price == depth[2]:
                order_size = self.rand_size_around(self.order_size, order.price)
                if abs(depth[6] - order_size) > self.quoting_leg.symbol_info.base_step_f * 2 * order.price:
                    if MINIMUM_QUOTE_LIFETIME is None or time.time() - order.timestamp > MINIMUM_QUOTE_LIFETIME:
                        return self._cancel_order(
                            order, reason=f"order size will not be taken, i.e., {depth[6]} vs {order_size}"
                        )

            # if depth[6] > (order.quantity - order.filled) + 1e-6:
            #     if MINIMUM_QUOTE_LIFETIME is None or time.time() - order.timestamp > MINIMUM_QUOTE_LIFETIME:
            #         return self._cancel_order(
            #             order,
            #             reason=f"order is not the unique ask, i.e., {order.quantity - order.filled} vs {depth[6]}",
            #         )

            # already the best ask
            return False

        if ask_qty > self._get_base_available():
            return False

        # check space to quote, allow active order
        if depth[2] - depth[1] < symbol_info.quote_step_f * 5:
            return False

        # ask_price = depth[2] - symbol_info.quote_step_f * 0.5
        # ask_price = symbol_info.round_price(ask_price, round_up=False)
        assert ask_price * ask_qty > symbol_info.value_min

        return self._place_ask_order_maker(ask_price, ask_qty, reason=reason)

    def hit_ask_side(self, ask_qty: float, reason: str = None):  # unsigned
        depth = self.quoting_leg.depth
        assert depth[1] < depth[2]

        symbol_info = self.quoting_leg.symbol_info
        assert ask_qty > symbol_info.base_min

        # cancel buy orders
        for order in self.quoting_account.get_orders(symbol=self.quoting_leg.symbol, active=True, side="buy").values():
            return self._cancel_order(order, reason=reason)

        # cancel unpromising sell orders
        for order in self.quoting_account.get_orders(symbol=self.quoting_leg.symbol, active=True, side="sell").values():
            if order.price < depth[1] - 1e-6:
                return self._cancel_order(order, reason="order does not target the best bid")

        if ask_qty > self._get_base_available():
            return False

        # check space to quote, allow active order
        if depth[2] - depth[1] < symbol_info.quote_step_f * 5:
            return False

        ask_price = depth[1]
        assert ask_price * ask_qty > symbol_info.value_min

        return self._place_ask_order_taker(ask_price, ask_qty, reason=reason)
