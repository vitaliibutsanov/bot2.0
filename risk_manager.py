class RiskManager:
    def __init__(self, max_loss=0.05):
        self.max_loss = max_loss

    def check_risk(self, current_loss):
        return current_loss < self.max_loss
