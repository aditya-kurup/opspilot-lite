"""Generate the architecture PNG with Pillow (development tool only)."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent.parent
image = Image.new("RGB", (1600, 930), "#0c1421")
draw = ImageDraw.Draw(image)
font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
font = ImageFont.truetype(font_path, 23)
small = ImageFont.truetype(font_path, 19)
title = ImageFont.truetype(font_path, 40)

draw.text((70, 45), "OpsPilot Lite | AWS deployment", font=title, fill="#ebf1fa")
draw.text(
    (70, 105),
    "Human approval separates an AI-generated plan from an AWS action.",
    font=font,
    fill="#9db0c9",
)

boxes = {
    "slack": (60, 210, 300, 310, "Slack user", "/provision + buttons"),
    "ingress": (360, 210, 610, 310, "Ingress Lambda", "Verify signature + queue"),
    "parseq": (680, 180, 900, 265, "SQS parse queue", "Async requests"),
    "execq": (680, 340, 900, 425, "SQS execute queue", "Approval decisions"),
    "parser": (980, 180, 1240, 265, "Parser Lambda", "Redact + validate JSON"),
    "executor": (980, 340, 1240, 425, "Executor Lambda", "Authorize + fixed boto3"),
    "bedrock": (1310, 180, 1540, 265, "Bedrock", "Text to JSON only"),
    "s3": (1310, 340, 1540, 425, "S3 bucket", "Private + encrypted"),
    "requests": (980, 540, 1240, 625, "DynamoDB", "Requests + state"),
    "audit": (1310, 540, 1540, 625, "DynamoDB", "Audit history"),
    "timer": (360, 710, 610, 795, "EventBridge", "Hourly schedule"),
    "cleanup": (980, 710, 1240, 795, "Cleanup Lambda", "Expired empty buckets"),
}


def arrow(points, color="#88e7bf"):
    draw.line(points, fill=color, width=3)
    x, y = points[-1]
    px, py = points[-2]
    if x > px:
        tip = [(x, y), (x - 12, y - 6), (x - 12, y + 6)]
    elif y > py:
        tip = [(x, y), (x - 6, y - 12), (x + 6, y - 12)]
    else:
        tip = [(x, y), (x - 6, y + 12), (x + 6, y + 12)]
    draw.polygon(tip, fill=color)


arrow([(300, 255), (360, 255)])
arrow([(610, 245), (645, 245), (645, 222), (680, 222)])
arrow([(610, 280), (645, 280), (645, 382), (680, 382)])
arrow([(900, 222), (980, 222)])
arrow([(900, 382), (980, 382)])
arrow([(1240, 222), (1310, 222)])
arrow([(1240, 382), (1310, 382)])
arrow([(1070, 265), (1070, 300), (950, 300), (950, 580), (980, 580)], "#9db0c9")
arrow([(1110, 425), (1110, 540)], "#9db0c9")
arrow([(1200, 425), (1200, 485), (1430, 485), (1430, 540)], "#9db0c9")
arrow([(610, 752), (980, 752)])
arrow([(1240, 752), (1500, 752), (1500, 425)])
arrow([(1100, 710), (1100, 625)], "#9db0c9")
for x1, y1, x2, y2, heading, detail in boxes.values():
    draw.rounded_rectangle((x1, y1, x2, y2), radius=12, fill="#152236", outline="#38516b", width=2)
    draw.text((x1 + 15, y1 + 16), heading, font=font, fill="#ebf1fa")
    draw.text((x1 + 15, y1 + 51), detail, font=small, fill="#9db0c9")
draw.text(
    (70, 850),
    "Parser: no S3 mutation permissions. Executor and cleanup: no Bedrock permissions. Secrets stay in Secrets Manager.",
    font=small,
    fill="#88e7bf",
)
image.save(root / "docs" / "architecture.png")
