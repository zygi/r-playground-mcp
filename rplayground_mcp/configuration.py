from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Configuration(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="_", env_nested_max_split=1, env_prefix="RPLAYGROUND_MCP_"
    )

    support_image_output: bool = Field(default=True, alias="SUPPORT_IMAGE_OUTPUT")
