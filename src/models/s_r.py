from enum import Enum, auto

class SRLevelType(Enum):
    SUPPORT = auto()
    RESISTANCE = auto()


class SR:
    def __init__(self, id: int, type: SRLevelType, price: float, candle_index: int):
        self.id = id
        self.type = type
        self.price = price
        self.candle_index = candle_index

    def __str__(self):
        return f"SR(id={self.id}, type={self.type}, price={self.price}, candle_index={self.candle_index})"

    def __repr__(self):
        return self.__str__()