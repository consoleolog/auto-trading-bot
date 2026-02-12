import logging


class StandardFormatter(logging.Formatter):
    """Standard text formatter"""

    def __init__(self):
        super().__init__("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
