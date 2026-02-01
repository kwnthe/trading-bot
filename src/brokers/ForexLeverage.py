import backtrader as bt

class ForexLeverage(bt.CommInfoBase):
    """
    Standard Forex/Metals Commission Scheme.
    - 20x Leverage (5% Margin)
    - 0.005% Commission
    """
    params = (
        ('leverage', 20),
        ('commission', 0.00005), 
        ('stocklike', False),
        ('commtype', bt.CommInfoBase.COMM_PERC),
    )

    def getmargin(self, price):
        # Cleanly defines margin as a function of current price
        return price / self.p.leverage