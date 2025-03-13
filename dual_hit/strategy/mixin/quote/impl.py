from .cancel import QuoteCancelationMixin
from .one_side import OneSideQuoteMixin
from .order_action import QuoteOrderActionMixin


class QuoteMixin(QuoteCancelationMixin, OneSideQuoteMixin, QuoteOrderActionMixin):
    pass
