from pathlib import Path
from typing import Optional, TypeVar

import confuse

APPLICATION_NAME = "IzumiBot"
CONFIG_DIR = Path(".") / "config"
DEFAULT_DIR = CONFIG_DIR / "default"
CONFIG_NAME = "bot.yml"

_T = TypeVar("_T")


class ApplicationConfiguration(confuse.Configuration):
    def __init__(self, configPath: Optional[str] = None):
        self._config_path = configPath or str(CONFIG_DIR)
        self._config = str(CONFIG_DIR / CONFIG_NAME)
        self._default = str(DEFAULT_DIR / CONFIG_NAME)
        super().__init__(APPLICATION_NAME)

    def config_dir(self) -> str:
        Path(self._config_path).mkdir(exist_ok=True)
        return str(self._config_path)

    def user_config_path(self) -> str:
        return str(Path(self._config_path) / CONFIG_NAME)

    def _add_default_source(self):
        assert Path(self._default).is_file()
        data = confuse.load_yaml(self._default, loader=self.loader)
        self.add(confuse.ConfigSource(data, filename=self._default, default=True))

    def _add_user_source(self):
        if not Path(self._config).is_file():
            Path(self._config).write_bytes(Path(self._default).read_bytes())
        data = confuse.load_yaml(self._config, loader=self.loader)
        self.add(confuse.ConfigSource(data, filename=self._config, default=True))


Config = ApplicationConfiguration()
VERSION: str = Config["general"]["version"].as_str()  # type:ignore
