from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    tinyfish_api_key: str = ''
    tinyfish_api_url: str = 'https://agent.tinyfish.ai/v1/automation/run-sse'
    database_url: str = 'postgresql+psycopg://careersidekick:careersidekick@localhost:5432/careersidekick'
    auto_create_schema: bool = True
    backend_port: int = 8000
    allowed_origin: str = 'http://localhost:5173'


settings = Settings()
