"""Configuration loader for the Marvis module using Pydantic BaseSettings."""

from typing import Literal, Optional, Dict, Any, List

from pydantic import Field, FilePath, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """Settings for LLM interaction."""

    model_config = SettingsConfigDict(env_prefix='MARVIS_LLM_')

    provider: Literal["openai", "google", "anthropic", "other"] = Field(
        default="openai", description="The LLM provider to use."
    )
    api_key: SecretStr = Field(..., description="API key for the LLM provider.")
    model_name: str = Field(
        default="gpt-4o", description="The specific LLM model to use."
    )
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="LLM temperature setting."
    )
    max_tokens: Optional[int] = Field(
        default=None, description="LLM maximum tokens to generate."
    )
    # Pydantic AI specific settings if any, e.g. client options
    # For Pydantic AI, the model_name might be sufficient if it uses a string like 'openai:gpt-4o'
    # We might need to store the Pydantic AI compatible LLM client/model instance details here or pass them directly.
    # For now, keeping it simple with provider and model_name.


class PyATSConnectionSettings(BaseSettings):
    """Direct connection settings for a pyATS device."""

    model_config = SettingsConfigDict(env_prefix='MARVIS_PYATS_DEVICE_')

    hostname: str = Field(..., description="Hostname or IP address of the device.")
    username: Optional[str] = Field(default=None, description="Username for device login.")
    password: Optional[SecretStr] = Field(default=None, description="Password for device login.")
    protocol: Literal["ssh", "telnet"] = Field(
        default="ssh", description="Connection protocol (ssh or telnet)."
    )
    port: Optional[int] = Field(default=None, description="Connection port.")


class PyATSSettings(BaseSettings):
    """Settings for pyATS, either via testbed file or direct connection parameters."""

    model_config = SettingsConfigDict(env_prefix='MARVIS_PYATS_')

    testbed_file: Optional[FilePath] = Field(
        default=None, description="Path to the pyATS testbed YAML file."
    )
    # If testbed_file is not provided, direct connection settings can be used
    # This would typically be for a single device or a list of devices.
    # For simplicity, let's assume if testbed_file is None, client provides connection details per device.
    # Or, we can have a default device connection here if testbed is not used.
    # For now, focusing on testbed_file as primary, direct connection details might be passed at runtime.


class FeatureSettings(BaseSettings):
    """Settings for optional module features."""

    model_config = SettingsConfigDict(env_prefix='MARVIS_FEATURE_')

    enable_basic_connectivity_tests_on_failure: bool = Field(
        default=True,
        description="Enable basic connectivity tests (ping, DNS) if pyATS connection fails.",
    )


class MarvisSettings(BaseSettings):
    """Main configuration settings for the Marvis module."""

    model_config = SettingsConfigDict(
        env_nested_delimiter='__',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    llm: LLMSettings = Field(default_factory=LLMSettings)
    pyats: PyATSSettings = Field(default_factory=PyATSSettings)
    features: FeatureSettings = Field(default_factory=FeatureSettings)

    # List of allowed show commands for pyATS interface
    allowed_pyats_commands: List[str] = Field(
        default_factory=lambda: [
            "show version",
            "show ip interface brief",
            "show interfaces",
            "show run",
            "show logging",
            "show ip route",
            "show cdp neighbors detail",
            "show lldp neighbors detail",
        ],
        description="Configurable list of allowed pyATS show commands.",
    )


# Helper function to load settings
def load_marvis_settings() -> MarvisSettings:
    """Loads and returns the MarvisSettings."""
    return MarvisSettings()


if __name__ == "__main__":
    # Example of loading settings
    settings = load_marvis_settings()
    print("Marvis Settings Loaded:")
    print(f"  LLM Provider: {settings.llm.provider}")
    print(f"  LLM Model: {settings.llm.model_name}")
    if settings.llm.api_key: # Check if api_key is set
        print(f"  LLM API Key: {settings.llm.api_key.get_secret_value()[:5]}...")
    else:
        print("  LLM API Key: Not set")
    print(f"  PyATS Testbed File: {settings.pyats.testbed_file}")
    print(
        f"  Enable Connectivity Tests: {settings.features.enable_basic_connectivity_tests_on_failure}"
    )
    print(f"  Allowed pyATS Commands: {settings.allowed_pyats_commands}")

    # Example for .env file:
    # MARVIS_LLM__PROVIDER="openai"
    # MARVIS_LLM__API_KEY="your_llm_api_key"
    # MARVIS_LLM__MODEL_NAME="gpt-4o"
    # MARVIS_PYATS__TESTBED_FILE="/path/to/your/testbed.yaml"
    # MARVIS_FEATURE__ENABLE_BASIC_CONNECTIVITY_TESTS_ON_FAILURE=false
    # MARVIS_ALLOWED_PYATS_COMMANDS='["show version", "show ip arp"]' # JSON encoded list
