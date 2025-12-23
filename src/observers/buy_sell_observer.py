import backtrader as bt

class BuySellObserver(bt.observers.BuySell):
        plotlines = dict(
            buy=dict(marker='^', markersize=10.0, color='#00FF00',
                     fillstyle='full', ls='', ),
            sell=dict(marker='v', markersize=10.0, color='#FF0040',
                      fillstyle='full', ls='')
        )