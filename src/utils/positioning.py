def calculate_position(current_equity: float, risk_per_trade: float, stop_price: float, stop_loss: float) -> int:
    risk_amount = current_equity * risk_per_trade
    risk_distance = abs(stop_price - stop_loss)
    return int(risk_amount / risk_distance) if risk_distance > 0 else 100000