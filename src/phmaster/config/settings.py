from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from platformdirs import user_log_path
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
PresetChoice = Literal["light", "medium", "night"]
LayoutChoice = Literal["stereo", "keep", "both"]
CodecSetting = Literal["auto", "aac", "eac3", "ac3", "opus", "flac"]


class ConsoleSettings(BaseModel):
    """Rich console output."""

    width: int | None = Field(
        default=None, ge=1, description="Fixed width; terminal width if unset"
    )
    height: int | None = Field(
        default=None, ge=1, description="Fixed height; terminal height if unset"
    )
    color_system: Literal["auto", "standard", "256", "truecolor", "windows"] = Field(
        default="auto", description="Color system; `auto` detects terminal support"
    )
    no_color: bool = Field(default=False, description="Disable all color output")
    force_terminal: bool | None = Field(
        default=None, description="Force terminal control codes; detected automatically if unset"
    )
    quiet: bool = Field(default=False, description="Suppress all console output")
    soft_wrap: bool = Field(default=False, description="Disable word wrapping")
    markup: bool = Field(default=True, description="Render Rich console markup")
    emoji: bool = Field(default=True, description="Render `:emoji:` codes")
    highlight: bool = Field(default=True, description="Highlight numbers, strings, and paths")
    tab_size: int = Field(default=8, ge=1, description="Spaces per tab character")


class LogSettings(BaseModel):
    """Console and rotating file logging."""

    level: LogLevel = Field(default="INFO", description="Root log level")
    console_level: LogLevel = Field(default="DEBUG", description="Minimum level printed to stderr")
    file_level: LogLevel = Field(default="INFO", description="Minimum level written to the file")
    format: Literal["console", "json"] = Field(
        default="console", description="Console log renderer; file logs are always JSON"
    )
    dir: Path | None = Field(
        default=None,
        description=(
            "Log directory; the platform user log directory if unset. "
            "If it cannot be used, logs go only to the console"
        ),
    )
    file_name: str = Field(default="phmaster.log", description="Log file name")
    file_max_bytes: int = Field(
        default=4 * 1024 * 1024, ge=0, description="File size that triggers rotation"
    )
    file_backup_count: int = Field(default=5, ge=0, description="Rotated files to keep")

    @property
    def resolved_dir(self) -> Path:
        """Select the explicit log directory or the platform default."""
        return self.dir if self.dir is not None else user_log_path("phmaster")


class ProcessingSettings(BaseModel):
    """Defaults of the process and probe commands."""

    presets: list[PresetChoice] = Field(
        default_factory=lambda: list[PresetChoice](["night"]),
        min_length=1,
        description="Presets to generate, as a JSON list; one track per preset",
    )
    layout: LayoutChoice = Field(
        default="stereo",
        description="`stereo` downmix, `keep` the source layout (up to 5.1), or `both`",
    )
    codec: CodecSetting = Field(
        default="auto", description="Codec of new tracks; `auto` is AAC for stereo, E-AC-3 for 5.1"
    )
    stereo_bitrate: str = Field(
        default="256k",
        pattern=r"^[1-9][0-9]*[kKmM]?$",
        description=(
            "Bitrate of mono and stereo tracks; positive number with optional k or M suffix"
        ),
    )
    surround_bitrate: str = Field(
        default="640k",
        pattern=r"^[1-9][0-9]*[kKmM]?$",
        description="Bitrate of surround tracks; positive number with optional k or M suffix",
    )
    center_mix_db: float = Field(
        default=0.0,
        ge=-12.0,
        le=12.0,
        allow_inf_nan=False,
        description="Center (dialogue) level in stereo downmixes; the ITU default is -3",
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Process only tracks in these languages, as a JSON list; empty means all",
    )
    suffix: str = Field(
        default=".phm",
        min_length=1,
        pattern=r"^[^/\\\x00<>:\"|?*]+$",
        description="Inserted before the output extension; must be a filename fragment",
    )
    set_default: bool = Field(
        default=True, description="Mark the first new track as the default audio track"
    )
    ffmpeg: str = Field(default="ffmpeg", description="ffmpeg executable name or path")
    ffprobe: str = Field(default="ffprobe", description="ffprobe executable name or path")


class Settings(BaseSettings):
    """Load application settings from PHMASTER_* variables and .env."""

    model_config = SettingsConfigDict(
        env_prefix="PHMASTER_",
        env_file=".env",
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="ignore",
    )

    console: ConsoleSettings = Field(default_factory=ConsoleSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)


def nested_model(field: FieldInfo) -> type[BaseModel] | None:
    """Return the settings model of a nested section, if the field is one."""
    for candidate in getattr(field.annotation, "__args__", (field.annotation,)):
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            return candidate
    return None


def env_fields(
    model: type[BaseModel] = Settings, prefix: str = "PHMASTER_"
) -> Iterator[tuple[str, FieldInfo]]:
    """Yield every leaf setting with its environment variable name."""
    for name, field in model.model_fields.items():
        variable = f"{prefix}{name.upper()}"
        section = nested_model(field)
        if section is None:
            yield variable, field
        else:
            yield from env_fields(section, f"{variable}__")


def load_settings() -> Settings:
    """Load settings from the environment and .env."""
    return Settings()
