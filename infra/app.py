import aws_cdk as cdk
from infra.stack import OpsPilotStack

app = cdk.App()
OpsPilotStack(app, "OpsPilotLite")
app.synth()
