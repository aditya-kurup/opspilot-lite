import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWLIST = {"create_s3_bucket"}


class ProvisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: str
    name: str = Field(min_length=3, max_length=30)
    ttl_hours: int = Field(ge=1, le=72)
    env: str

    @field_validator("action")
    @classmethod
    def allowed_action(cls, value: str) -> str:
        if value not in ALLOWLIST:
            raise ValueError("action is not allowlisted")
        return value

    @field_validator("name")
    @classmethod
    def safe_name(cls, value: str) -> str:
        value = value.lower().strip()
        value = re.sub(r"[^a-z0-9-]+", "-", value).strip("-")
        if len(value) < 3 or len(value) > 30:
            raise ValueError("name must have 3-30 safe characters")
        return value

    @field_validator("env")
    @classmethod
    def safe_env(cls, value: str) -> str:
        if value not in {"dev", "test"}:
            raise ValueError("env must be dev or test")
        return value


def parse_request(text: str, llm_fn) -> ProvisionRequest:
    if not text.strip() or len(text) > 500:
        raise ValueError("request must contain 1-500 characters")
    return ProvisionRequest.model_validate(llm_fn(text))
