import aws_cdk as cdk
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_iam as iam
from cdk_nag import AwsSolutionsChecks, NagSuppressions, NagPackSuppression

class DyndnsStack(cdk.Stack):

    def __init__(self, scope: cdk.App, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        #Create Lambda role
        fn_role = iam.Role(self, "dyndns_fn_role",
            assumed_by = iam.ServicePrincipal("lambda.amazonaws.com"),
            description = "DynamicDNS Lambda role",
            inline_policies = {
                'r53': iam.PolicyDocument(
                    statements = [
                        iam.PolicyStatement(
                            effect = iam.Effect.ALLOW,
                            resources = [
                                "*"
                            ],
                          actions = [
                                "route53:ChangeResourceRecordSets","route53:ListResourceRecordSets"
                            ]
                        )
                    ],
                ),
                'cw': iam.PolicyDocument(
                    statements = [
                        iam.PolicyStatement(
                            effect = iam.Effect.ALLOW,
                            resources = [
                                "*"
                            ],
                          actions = [
                                "logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"
                            ]
                        )
                    ],
                )
            }
        ) 


        fn = lambda_.Function(self, "dyndns_fn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("lambda"),
            role=fn_role,
            timeout=cdk.Duration.seconds(8),
            #Provide configuration as environment variables
            environment={
                "VALIDATION_MODE": "wildcard",  # Options: "hardcoded" or "wildcard"
                "ALLOWED_PATTERN": r"^[a-z0-9\-]+\.dyn\.orbit\.me\.uk$",  # For wildcard mode
                "ALLOWED_DOMAINS": "",  # For hardcoded mode: comma-separated list
                "ROUTE53_ZONE_ID": "",  # Must be set via CDK context or updated here
                "ROUTE53_RECORD_TTL": "60",  # DNS record TTL in seconds
                "SHARED_SECRET": ""  # Must be set via CDK context or updated here
            }
        )            

        #Create FunctionURL for invocation - principal will be set to * as it required for invocation from any HTTP client
        fn.add_function_url(
            #Allow unauthenticated access
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            #Set CORS for any source
            cors=lambda_.FunctionUrlCorsOptions(
                allowed_origins=["*"]
            )
        )

        #Suppress AwsSolutions-IAM5 triggered by Resources::*
        NagSuppressions.add_resource_suppressions(
            construct= fn_role,
            suppressions=[
                NagPackSuppression(
                    id = 'AwsSolutions-IAM5',
                    reason="""
                    Lambda role created at line 29 has 2 inline policies allowing access to Route53 and CloudWatch. 
                    Route53 resources are set to "*" as the function will need to access any hosted zone.
                    CloudWatch resources are set to "*" to avoid having to specify a Logging group and consume the default one deployed by CDK.
                    """
                )
            ]
        )
