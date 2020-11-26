class ScenarioCache(dict):
    def __setitem__(self, key, value):
        super().__setitem__(key, {signal.id: signal for signal in value})