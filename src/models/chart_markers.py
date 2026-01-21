from enum import Enum

class ChartMarkerType(Enum):
    RETEST_ORDER_PLACED = 'retest_order_placed'

MARKER_TYPE_TO_MARKER_SYMBOL = {
    ChartMarkerType.RETEST_ORDER_PLACED: 'diamond',
}