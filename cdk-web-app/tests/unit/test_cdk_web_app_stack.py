import aws_cdk as core
import aws_cdk.assertions as assertions

from cdk_web_app.cdk_web_app_stack import CdkWebAppStack

# example tests. To run these tests, uncomment this file along with the example
# resource in cdk_web_app/cdk_web_app_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = CdkWebAppStack(app, "cdk-web-app")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
