class OrderMixin:
    @staticmethod
    def _bid_price_depth(price: float, bid0: float):
        return bid0 - price

    @staticmethod
    def _ask_price_depth(price: float, ask0: float):
        return price - ask0

    @staticmethod
    def _bid_value_portion(value: float, quote_asset_for_bidding: float):
        assert value >= 0, f"value {value} should be not negative"
        return value / quote_asset_for_bidding

    @staticmethod
    def _ask_quantity_portion(quantity: float, base_asset_for_asking: float):
        assert quantity >= 0, f"quantity {quantity} should be not negative"
        return quantity / base_asset_for_asking
