import logging

from brainglobe_workflows.utils import setup_logger


def test_setup_logger(custom_logger_name: str):
    """Test custom logger is correctly created

    Parameters
    ----------
    custom_logger_name : str
        Pytest fixture for the custom logger name
    """
    logger = setup_logger()

    assert logger.level == logging.DEBUG
    assert logger.name == custom_logger_name
    assert logger.hasHandlers()
    assert logger.handlers[0].name == "console_handler"
