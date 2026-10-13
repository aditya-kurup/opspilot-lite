import logging
from slack_bolt.adapter.socket_mode import SocketModeHandler
from app.handlers import build_app


def main():
    logging.basicConfig(level=logging.INFO)
    import os

    if os.getenv("STORAGE_BACKEND") != "sqlite":
        raise RuntimeError("Set STORAGE_BACKEND=sqlite for local Socket Mode")
    SocketModeHandler(build_app(), os.environ["SLACK_APP_TOKEN"]).start()


if __name__ == "__main__":
    main()
