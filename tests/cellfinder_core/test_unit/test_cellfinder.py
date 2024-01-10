import json
import logging
import re
from pathlib import Path

import pooch
import pytest

from brainglobe_workflows.utils import setup_logger


@pytest.fixture(scope="session")
def cellfinder_GIN_data() -> dict:
    """Return the URL and hash to the GIN repository with the input data

    Returns
    -------
    dict
        URL and hash of the GIN repository with the cellfinder test data
    """
    return {
        "url": "https://gin.g-node.org/BrainGlobe/test-data/raw/master/cellfinder/cellfinder-test-data.zip",
        "hash": "b0ef53b1530e4fa3128fcc0a752d0751909eab129d701f384fc0ea5f138c5914",  # noqa
    }


@pytest.fixture()
def config_local(cellfinder_GIN_data, default_input_config_cellfinder):
    """ """

    from brainglobe_workflows.cellfinder_core.cellfinder_core import (
        CellfinderConfig,
    )

    # read default config as dict
    # as dict because some paths are computed derived from input_data_dir
    with open(default_input_config_cellfinder) as cfg:
        config_dict = json.load(cfg)

    # modify config:
    # - remove url
    # - remove data hash
    # - add input_data_dir
    config_dict["data_url"] = None
    config_dict["data_hash"] = None
    config_dict["input_data_dir"] = Path.home() / "local_cellfinder_data"

    # instantiate object
    config = CellfinderConfig(**config_dict)

    # fetch data from GIN and download locally to local location?
    pooch.retrieve(
        url=cellfinder_GIN_data["url"],
        known_hash=cellfinder_GIN_data["hash"],
        path=Path(config.input_data_dir).parent,  # path to download zip to
        progressbar=True,
        processor=pooch.Unzip(
            extract_dir=Path(config.input_data_dir).stem
            # path to unzipped dir, *relative*  to 'path'
        ),
    )
    return config


@pytest.mark.parametrize(
    "input_config, message",
    [
        ("default_input_config_cellfinder", "Using default config file"),
    ],
)
def test_read_cellfinder_config(
    input_config: str,
    message: str,
    caplog: pytest.LogCaptureFixture,
    request: pytest.FixtureRequest,
):
    """Test for reading a cellfinder config file

    Parameters
    ----------
    input_config : str
        Name of input config json file
    input_configs_dir : Path
        Test data directory path
    """
    from brainglobe_workflows.cellfinder_core.cellfinder_core import (
        read_cellfinder_config,
    )

    # instantiate custom logger
    _ = setup_logger()

    input_config_path = request.getfixturevalue(input_config)

    # read json as Cellfinder config
    config = read_cellfinder_config(input_config_path, log_on=True)

    # read json as dict
    with open(input_config_path) as cfg:
        config_dict = json.load(cfg)

    # check keys of dictionary are a subset of Cellfinder config attributes
    assert all(
        [ky in config.__dataclass_fields__.keys() for ky in config_dict.keys()]
    )

    # check logs
    assert message in caplog.text

    # check all signal files exist
    assert config._list_signal_files
    assert all([Path(f).is_file() for f in config._list_signal_files])

    # check all background files exist
    assert config._list_background_files
    assert all([Path(f).is_file() for f in config._list_background_files])

    # check output directory exists
    assert Path(config._output_path).resolve().is_dir()

    # check output directory name has correct format
    out = re.fullmatch(
        str(config.output_dir_basename) + "\\d{8}_\\d{6}$",
        Path(config._output_path).stem,
    )
    assert out is not None
    assert out.group() is not None

    # check output file path is as expected
    assert (
        Path(config._detected_cells_path)
        == Path(config._output_path) / config.detected_cells_filename
    )


@pytest.mark.skip(reason="focus of PR62")
@pytest.mark.parametrize(
    "input_config, message_pattern",
    [
        (
            "config_local",
            "Fetching input data from the local directories",
        ),
    ],
)
def test_add_input_paths(
    caplog: pytest.LogCaptureFixture,
    input_config: str,
    message_pattern: str,
    request: pytest.FixtureRequest,
):
    """Test signal and background files addition to the cellfinder config

    Parameters
    ----------
    caplog : pytest.LogCaptureFixture
        Pytest fixture to capture the logs during testing
    cellfinder_GIN_data : dict
        Dict holding the URL and hash of the cellfinder test data in GIN
    input_configs_dir : Path
        Test data directory path
    input_config : str
        Name of input config json file
    message_pattern : str
        Expected pattern in the log
    """

    # instantiate custom logger
    _ = setup_logger()

    # read json as Cellfinder config
    _ = request.getfixturevalue(input_config)

    # check log messages
    assert len(caplog.messages) > 0
    out = re.fullmatch(message_pattern, caplog.messages[-1])
    assert out is not None
    assert out.group() is not None


@pytest.mark.parametrize(
    "input_config",
    [
        "default_input_config_cellfinder",
    ],
)
def test_setup(
    input_config: str,
    custom_logger_name: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request: pytest.FixtureRequest,
):
    """Test full setup for cellfinder workflow, using the default config
    and passing a specific config file.

    Parameters
    ----------
    input_config : str
        Path to input config file
    custom_logger_name : str
        Name of custom logger
    monkeypatch : MonkeyPatch
        Pytest fixture to use monkeypatching utils
    tmp_path : Path
        Pytest fixture providing a temporary path for each test
    request : pytest.FixtureRequest
        Pytest fixture to enable requesting fixtures by name
    """
    from brainglobe_workflows.cellfinder_core.cellfinder_core import (
        CellfinderConfig,
    )
    from brainglobe_workflows.cellfinder_core.cellfinder_core import (
        setup as setup_full,
    )

    # Monkeypatch to change current directory to
    # pytest temporary directory
    # (cellfinder cache directory is created in cwd)
    monkeypatch.chdir(tmp_path)

    # run setup on default configuration
    cfg = setup_full(request.getfixturevalue(input_config))

    # check logger exists
    logger = logging.getLogger(custom_logger_name)
    assert logger.level == logging.DEBUG
    assert logger.hasHandlers()

    # check config is CellfinderConfig
    assert isinstance(cfg, CellfinderConfig)


@pytest.mark.parametrize(
    "input_config",
    [
        "default_input_config_cellfinder",
    ],
)
def test_run_workflow_from_cellfinder_run(
    input_config: str,
    request: pytest.FixtureRequest,
):
    """Test running cellfinder workflow with default input config
    (fetches data from GIN) and local input config

    Parameters
    ----------
    input_config : str
        Path to input config json file
    monkeypatch : MonkeyPatch
        Pytest fixture to use monkeypatching utils
    tmp_path : Path
        Pytest fixture providing a temporary path for each test
    request : pytest.FixtureRequest
        Pytest fixture to enable requesting fixtures by name
    """
    from brainglobe_workflows.cellfinder_core.cellfinder_core import (
        run_workflow_from_cellfinder_run,
    )
    from brainglobe_workflows.cellfinder_core.cellfinder_core import (
        setup as setup_full,
    )

    # run setup
    cfg = setup_full(str(request.getfixturevalue(input_config)))

    # run workflow
    run_workflow_from_cellfinder_run(cfg)

    # check output files are those expected?
    assert Path(cfg._detected_cells_path).is_file()
