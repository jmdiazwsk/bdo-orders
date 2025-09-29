
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    app_name: str = Field(default="BDO Orders Platform")
    app_env: str = Field(default="dev")

    database_url: str = Field(alias="DATABASE_URL")
    db_host: str = Field(alias="DB_HOST")
    db_port: int = Field(alias="DB_PORT")
    db_user: str = Field(alias="DB_USER")
    db_password: str = Field(alias="DB_PASSWORD")
    db_name: str = Field(alias="DB_NAME")
    sync_database_url: str | None = Field(alias="SYNC_DATABASE_URL", default=None)
    # Kafka
    kafka_brokers: str = Field(alias="KAFKA_BROKERS", default="localhost:9092")
    kafka_orders_topic: str = Field(alias="KAFKA_ORDERS_TOPIC", default="orders")

    # AWS / LocalStack
    aws_endpoint_url: str | None = Field(alias="AWS_ENDPOINT_URL", default=None)
    aws_region: str = Field(alias="AWS_REGION", default="eu-west-1")
    aws_sns_topic_arn: str | None = Field(alias="AWS_SNS_TOPIC_ARN", default=None)
    aws_s3_bucket: str | None = Field(alias="AWS_S3_BUCKET", default=None)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
