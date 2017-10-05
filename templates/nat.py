from troposphere import Base64, FindInMap, GetAtt
from troposphere import Parameter, Output, Ref, Template
from troposphere import Join, Split, cloudformation, Select
from troposphere import If, Equals, Or, And, Not, Condition, Tags
from troposphere import Output, Sub
from troposphere.policies import (CreationPolicy,
                                  ResourceSignal)
from troposphere.certificatemanager import Certificate, DomainValidationOption
from troposphere.s3 import Bucket
from troposphere.iam import Role, Policy, InstanceProfile
import troposphere.ec2 as ec2

import sys

import troposphere.elasticloadbalancing as elb
from troposphere.elasticloadbalancing import Policy as ELBPolicy
from troposphere.elasticloadbalancing import LoadBalancer

from troposphere.autoscaling import AutoScalingGroup, Tag
from troposphere.autoscaling import LaunchConfiguration

from troposphere.autoscaling import (
    ScalingPolicy
)

from troposphere.policies import (
    AutoScalingReplacingUpdate, AutoScalingRollingUpdate, UpdatePolicy
)

from troposphere.cloudwatch import Alarm, MetricDimension

t = Template()

# Take an existing VPC and a subnet having access to an S3 endpoint

# Existing VPC input
VPCIDParam = t.add_parameter(Parameter(
    "VPCID",
    Description="The VPC ID you wish to deploy in",
    Type="AWS::EC2::VPC::Id",
))

# Subnet with S3 endpoint
SubnetsWithS3EndpointParam = t.add_parameter(Parameter(
    "SubnetsWithS3Endpoint",
    Description="The private subnets with a configured S3 endpoint. Recommended to be spread across multiple AZ's.",
    Type="List<AWS::EC2::Subnet::Id>",
))

# Key pair for autoscaling NAT instances
KeyPairNameParam = t.add_parameter(Parameter(
    "KeyPairName",
    Description="Name of an existing EC2 KeyPair to enable SSH access to the instances",
    Type="AWS::EC2::KeyPair::KeyName",
    ConstraintDescription="must be the name of an existing EC2 KeyPair."
))

# DeployUserAccessKey = t.add_parameter(Parameter(
#     "DeployUserAccessKey",
#     Type="String",
#     Description="The access key of the deploy user",
# ))

# DeployUserSecretKey = t.add_parameter(Parameter(
#     "DeployUserSecretKey",
#     Type="String",
#     NoEcho=True,
#     Description="The secret key of the deploy user",
# ))

# Accept security group accepting port 80, 443 for autoscaling instances
AutoscalingSecurityGroupParam = t.add_parameter(Parameter(
    "AutoscalingSecurityGroup",
    Type="AWS::EC2::SecurityGroup::Id",
    Description="Security group for NAT instances & LB. Recommended inbound open for TCP 80, 443",
))

DeployBucket = t.add_parameter(Parameter(
    "DeployBucket",
    Type="String",
    Default="gong-cf-templates",
    Description="The S3 bucket with the cloudformation scripts.",
))

NATInstanceTypeParam = t.add_parameter(Parameter(
    "NATInstanceType",
    Description="EC2 instance type for NAT autoscaling group",
    Type="String",
    Default="t2.micro", #change to "m4.large",
    ConstraintDescription="must be a valid EC2 instance type."
))

DesiredCapacityParam = t.add_parameter(Parameter(
    "DesiredCapacity",
    Description="Number of desired NAT instances",
    Type="Number",
    Default=1
))

MinSizeParam = t.add_parameter(Parameter(
    "MinSize",
    Description="Min number of NAT instances",
    Type="Number",
    Default=1
))

MaxSizeParam = t.add_parameter(Parameter(
    "MaxSize",
    Description="Max number of NAT instances",
    Type="Number",
    Default=10
))

# Mapping of AMIs - TODO
t.add_mapping('AWSAMIRegion', {
    # "ap-northeast-1": {},
    # "ap-northeast-2": {},
    # "ap-south-1": {},
    # "ap-southeast-1": {},
    # "ap-southeast-2": {},
    # "ca-central-1": {},
    # "eu-central-1": {},
    # "eu-west-1": {},
    # "eu-west-2": {},
    # "sa-east-1": {},
    # "us-east-1": {},
    # "us-east-2": {},
    # "us-west-1": {},
    "us-west-2": { "NATAMI": "ami-aa5ebdd2" }
})

EC2Role = t.add_resource(
    Role(
        "EC2Role",
        AssumeRolePolicyDocument={
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": [
                  "ec2.amazonaws.com"
                ]
              },
              "Action": [
                "sts:AssumeRole"
              ]
            }
          ]
        },
        Path="/",
        Policies=[
            Policy(
            PolicyName="s3-policy",
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": [
                            "s3:GetObject"
                        ],
                        "Resource": Sub("arn:aws:s3:::${DeployBucket}/*"),
                        "Effect": "Allow"
                    }
                ]
            }),
            Policy(
                PolicyName="root",
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                        "Effect": "Allow",
                        "Action": [
                            "cloudwatch:PutMetricData"
                        ],
                        "Resource": "*"
                        }
                    ]
                
            })
        ]
    )
)

EC2InstanceProfile = t.add_resource(
    InstanceProfile(
        "EC2InstanceProfile",
        Roles=[Ref(EC2Role)],
        Path="/",
    )
)

# Create an autoscaling group

LaunchConfig = t.add_resource(LaunchConfiguration(
    "LaunchConfig",
    Metadata=cloudformation.Metadata(
            cloudformation.Authentication({
                "DeployUserAuth": cloudformation.AuthenticationBlock(
                    type="S3",
                    roleName=Ref(EC2Role),
                    buckets=[Ref(DeployBucket)]
                )
                
            }),
            cloudformation.Init({
            "config": cloudformation.InitConfig(
                files=cloudformation.InitFiles({
                    "/home/ec2-user/init-cron.sh": cloudformation.InitFile(
                        source=Join('', [
                            "http://",
                            Ref(DeployBucket),
                            ".s3.amazonaws.com/scripts/init-cron.sh"
                        ]),
                        mode="000550",
                        owner="root",
                        group="root",
                        authentication="DeployUserAuth"),

                    "/home/ec2-user/configure-s3-nat.sh": cloudformation.InitFile(
                        source=Join('', [
                            "http://",
                            Ref(DeployBucket),
                            ".s3.amazonaws.com/scripts/configure-s3-nat.sh"
                        ]),
                        mode="000550",
                        owner="root",
                        group="root",
                        authentication="DeployUserAuth"),

                    "/home/ec2-user/metrics.sh": cloudformation.InitFile(
                        source=Join('', [
                            "http://",
                            Ref(DeployBucket),
                            ".s3.amazonaws.com/scripts/metrics.sh"
                        ]),
                        mode="000550",
                        owner="root",
                        group="root",
                        authentication="DeployUserAuth"),
                    
                    "/home/ec2-user/nat-globals.sh": cloudformation.InitFile(
                        source=Join('', [
                            "http://",
                            Ref(DeployBucket),
                            ".s3.amazonaws.com/scripts/nat-globals.sh"
                        ]),
                        mode="000550",
                        owner="root",
                        group="root",
                        authentication="DeployUserAuth"),

                    "/home/ec2-user/nat-lib.sh": cloudformation.InitFile(
                        source=Join('', [
                            "http://",
                            Ref(DeployBucket),
                            ".s3.amazonaws.com/scripts/nat-lib.sh"
                        ]),
                        mode="000550",
                        owner="root",
                        group="root",
                        authentication="DeployUserAuth"),

                    "/home/ec2-user/s3-nat-watchdog.sh": cloudformation.InitFile(
                        source=Join('', [
                            "http://",
                            Ref(DeployBucket),
                            ".s3.amazonaws.com/scripts/s3-nat-watchdog.sh"
                        ]),
                        mode="000550",
                        owner="root",
                        group="root",
                        authentication="DeployUserAuth"),

                    "/home/ec2-user/test-s3-nat.sh": cloudformation.InitFile(
                        source=Join('', [
                            "http://",
                            Ref(DeployBucket),
                            ".s3.amazonaws.com/scripts/test-s3-nat.sh"
                        ]),
                        mode="000550",
                        owner="root",
                        group="root",
                        authentication="DeployUserAuth"),
                }),
                commands={
                    "init": {
                        "command": Join("", [
                            "/home/ec2-user/configure-s3-nat.sh && ",
                            "/home/ec2-user/init-cron.sh \"",
                            Ref("AWS::StackName"), "\" && ",
                            "/home/ec2-user/test-s3-nat.sh"
                        ])
                    }
                }
            )
        })
    ),
    KeyName=Ref(KeyPairNameParam),
    SecurityGroups=[Ref(AutoscalingSecurityGroupParam)],
    InstanceType=Ref(NATInstanceTypeParam),
    IamInstanceProfile=Ref(EC2InstanceProfile),
    InstanceMonitoring=False,
    UserData=Base64(Join('', [
        """
        #!/bin/bash -xe
        /opt/aws/bin/cfn-init -v """,
        "    --resource LaunchConfig",
        "    --stack ", Ref("AWS::StackName"),
        "    --region ", Ref("AWS::Region"), "\n",

        "cfn-signal -e $?", #"cfn-signal -e $?",
        "    --resource AutoscalingGroup",
        "    --stack ", Ref("AWS::StackName"),
        "    --region ", Ref("AWS::Region"), "\n"
    ])),
    ImageId=FindInMap("AWSAMIRegion", Ref("AWS::Region"), "NATAMI"),
    ),
)

LoadBalancerResource = t.add_resource(LoadBalancer(
    "LoadBalancer",
    ConnectionDrainingPolicy=elb.ConnectionDrainingPolicy(
        Enabled=True,
        Timeout=120,
    ),
    Subnets=Ref(SubnetsWithS3EndpointParam),
    HealthCheck=elb.HealthCheck(
        Target="TCP:80",
        HealthyThreshold=6,
        UnhealthyThreshold=10, #TODO: UPDATE TO REASONABLE, like 2
        Interval=300, #TODO: UPDATE TO 10
        Timeout=5,
    ),
    Listeners=[
        elb.Listener(
            LoadBalancerPort="80",
            InstancePort="80",
            Protocol="TCP",
        ),
        elb.Listener(
            LoadBalancerPort="443",
            InstancePort="443",
            Protocol="TCP",
        ),
    ],
    CrossZone=True,
    SecurityGroups=[Ref(AutoscalingSecurityGroupParam)],
    LoadBalancerName="NAT-LoadBalancer",
    Scheme="internal",
    Policies=[ELBPolicy(
        PolicyName="EnableProxyProtocol",
        PolicyType="ProxyProtocolPolicyType",
        Attributes=[
                  {
                    "Name": "ProxyProtocol",
                    "Value": "true"
                  }
                ],
        InstancePorts=[
            443, 80
        ]
        )]
))

AutoscalingGroup = t.add_resource(AutoScalingGroup(
    "AutoscalingGroup",
    DesiredCapacity=Ref(DesiredCapacityParam),
    LaunchConfigurationName=Ref(LaunchConfig),
    MinSize=Ref(MinSizeParam),
    MaxSize=Ref(MaxSizeParam),
    VPCZoneIdentifier=Ref(SubnetsWithS3EndpointParam),
    LoadBalancerNames=[Ref(LoadBalancerResource)],
    # AvailabilityZones=[Ref(VPCAvailabilityZone1), Ref(VPCAvailabilityZone2)], # Not strictly required?
    HealthCheckType="EC2", #TODO: Change to ELB
    HealthCheckGracePeriod="300",
    UpdatePolicy=UpdatePolicy(
        AutoScalingReplacingUpdate=AutoScalingReplacingUpdate(
            WillReplace=True,
        ),
        AutoScalingRollingUpdate=AutoScalingRollingUpdate(
            PauseTime='PT5M',
            MinInstancesInService="1",
            MaxBatchSize='1',
            WaitOnResourceSignals=True
        )
    )
))



ScaleOutPolicy = t.add_resource(ScalingPolicy(
    'ScaleOutPolicy',
    AdjustmentType="ChangeInCapacity",
    AutoScalingGroupName=Ref(AutoscalingGroup),
    Cooldown=300,
    ScalingAdjustment=1
))

ScaleInPolicy = t.add_resource(ScalingPolicy(
    'ScaleInPolicy',
    AdjustmentType="ChangeInCapacity",
    AutoScalingGroupName=Ref(AutoscalingGroup),
    Cooldown=300,
    ScalingAdjustment=-1
))

AlarmScaleOutPolicy = t.add_resource(Alarm(
    "AlarmScaleOutPolicy",
    AlarmDescription="Scale out if average traffic > 5000 KB/s for 5 minutes",
    MetricName="TotalKbytesPerSecond",
    Namespace="NATGroup",
    Statistic="Average",
    Period=300,
    EvaluationPeriods=1,
    Threshold="5000",
    Dimensions=[
        MetricDimension(
            "StackMetricDimension",
            Name="StackName",
            Value=Ref("AWS::StackName")
        )
        ],
    ComparisonOperator="GreaterThanThreshold",
    AlarmActions=[
        Ref(ScaleOutPolicy)
    ]    
))

AlarmScaleInPolicy = t.add_resource(Alarm(
    "AlarmScaleInPolicy",
    AlarmDescription="Scale in if average traffic < 2000 KB/s for 15 minutes",
    MetricName="TotalKbytesPerSecond",
    Namespace="NATGroup",
    Statistic="Average",
    Period=300,
    EvaluationPeriods=3,
    Threshold="2000",
    Dimensions=[
        MetricDimension(
            "StackMetricDimension",
            Name="StackName",
            Value=Ref("AWS::StackName")
        )
        ],
    ComparisonOperator="LessThanThreshold",
    AlarmActions=[
        Ref(ScaleInPolicy)
    ]    
))



# Deploy an autoscaling group of Amazon NAT AMIs
# With load balancer

# Configure load balancer, auto scaling group with the right health triggers

# Output: load balancer instance, DNS name & IP address

# Manual process
# Configure any subnets requiring NAT to point 0.0.0.0/0 to the instance created by above

print(t.to_json())