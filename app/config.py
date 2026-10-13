import os


def setting(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def dry_run() -> bool:
    return setting("DRY_RUN", "true").lower() == "true"


def approvers() -> set[str]:
    return {item.strip() for item in setting("APPROVER_USER_IDS").split(",") if item.strip()}
