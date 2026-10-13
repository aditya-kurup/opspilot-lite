from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from app.handlers import build_app


def handler(event, context):
    return SlackRequestHandler(build_app()).handle(event, context)
