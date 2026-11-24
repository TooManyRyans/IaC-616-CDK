from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_rds as rds,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancingv2_targets as targets,
)
from constructs import Construct


class ServerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. IAM Role so EC2 instances can run 'aws s3 cp'
        web_role = iam.Role(
            self,
            "WebServerRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess")
            ],
        )

        # 2. Security Groups
        web_sg = ec2.SecurityGroup(
            self,
            "WebServerSG",
            vpc=vpc,
            description="Allow HTTP (port 80) from anywhere",
            allow_all_outbound=True,
        )
        web_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP from anywhere",
        )

        rds_sg = ec2.SecurityGroup(
            self,
            "RDSSG",
            vpc=vpc,
            description="Allow MySQL (port 3306) only from WebServerSG",
            allow_all_outbound=True,
        )
        rds_sg.add_ingress_rule(
            peer=web_sg,
            connection=ec2.Port.tcp(3306),
            description="Allow MySQL from WebServerSG",
        )

        # 3. User Data Script (Amazon Linux 2023 supports dnf)
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "dnf update -y",
            "dnf install -y git httpd php",
            "service httpd start",
            "chkconfig httpd on",
            "aws s3 cp s3://seis665-public/index.php /var/www/html/",
        )

        ami = ec2.MachineImage.latest_amazon_linux2023()

        # 4. Launch one EC2 web server in each public subnet
        web_server_1 = ec2.Instance(
            self,
            "WebServer1",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=[vpc.public_subnets[0]]),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO
            ),
            machine_image=ami,
            security_group=web_sg,
            role=web_role,
            user_data=user_data,
        )

        web_server_2 = ec2.Instance(
            self,
            "WebServer2",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=[vpc.public_subnets[1]]),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO
            ),
            machine_image=ami,
            security_group=web_sg,
            role=web_role,
            user_data=user_data,
        )

        # 5. MySQL RDS Instance in all private subnets
        db_instance = rds.DatabaseInstance(
            self,
            "MySQLDatabase",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[rds_sg],
            publicly_accessible=False,
            allocated_storage=20,
            removal_policy=RemovalPolicy.DESTROY,  # Ensures 'cdk destroy' deletes the DB cleanly
            deletion_protection=False,
        )

        # 6. Application Load Balancer distributing traffic to both web servers
        alb = elbv2.ApplicationLoadBalancer(
            self,
            "WebLoadBalancer",
            vpc=vpc,
            internet_facing=True,
            security_group=web_sg,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        listener = alb.add_listener("WebListener", port=80, open=True)
        listener.add_targets(
            "WebTargets",
            port=80,
            targets=[
                targets.InstanceTarget(web_server_1),
                targets.InstanceTarget(web_server_2),
            ],
            health_check=elbv2.HealthCheck(path="/index.php"),
        )

        # 7. Outputs for Browser Verification
        CfnOutput(
            self,
            "WebsiteURL",
            value=f"http://{alb.load_balancer_dns_name}",
            description="Application Load Balancer URL",
        )
        CfnOutput(
            self,
            "RDSEndpoint",
            value=db_instance.db_instance_endpoint_address,
            description="MySQL Database Endpoint",
        )