#!/bin/bash

# Quick AWS Deployment Script for vLLM PoC
# This script sets up the complete AWS infrastructure and deploys the application

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
CLUSTER_NAME="vllm-poc-cluster"
SERVICE_NAME="vllm-poc-service"
ECR_REPO_NAME="vllm-poc"
INSTANCE_TYPE="g4dn.xlarge"  # GPU-enabled instance

echo -e "${BLUE}🚀 vLLM PoC AWS Deployment Script${NC}"
echo "=================================="

# Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"

if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found. Please install AWS CLI first.${NC}"
    exit 1
fi

if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured. Please run 'aws configure' first.${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${BLUE}📝 AWS Account ID: ${ACCOUNT_ID}${NC}"
echo -e "${BLUE}📍 Region: ${AWS_REGION}${NC}"

# Function to create or get VPC
setup_vpc() {
    echo -e "${YELLOW}🌐 Setting up VPC...${NC}"
    
    # Check if VPC exists
    VPC_ID=$(aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=vllm-poc-vpc" \
        --query "Vpcs[0].VpcId" \
        --output text 2>/dev/null || echo "None")
    
    if [ "$VPC_ID" = "None" ] || [ "$VPC_ID" = "null" ]; then
        # Create VPC
        VPC_ID=$(aws ec2 create-vpc \
            --cidr-block 10.0.0.0/16 \
            --query 'Vpc.VpcId' \
            --output text)
        
        aws ec2 create-tags \
            --resources $VPC_ID \
            --tags Key=Name,Value=vllm-poc-vpc
        
        echo -e "${GREEN}✅ Created VPC: ${VPC_ID}${NC}"
    else
        echo -e "${GREEN}✅ Using existing VPC: ${VPC_ID}${NC}"
    fi
    
    # Create Internet Gateway
    IGW_ID=$(aws ec2 describe-internet-gateways \
        --filters "Name=tag:Name,Values=vllm-poc-igw" \
        --query "InternetGateways[0].InternetGatewayId" \
        --output text 2>/dev/null || echo "None")
    
    if [ "$IGW_ID" = "None" ] || [ "$IGW_ID" = "null" ]; then
        IGW_ID=$(aws ec2 create-internet-gateway \
            --query 'InternetGateway.InternetGatewayId' \
            --output text)
        
        aws ec2 create-tags \
            --resources $IGW_ID \
            --tags Key=Name,Value=vllm-poc-igw
        
        aws ec2 attach-internet-gateway \
            --vpc-id $VPC_ID \
            --internet-gateway-id $IGW_ID
        
        echo -e "${GREEN}✅ Created and attached Internet Gateway: ${IGW_ID}${NC}"
    fi
    
    # Create subnet
    SUBNET_ID=$(aws ec2 describe-subnets \
        --filters "Name=tag:Name,Values=vllm-poc-subnet" \
        --query "Subnets[0].SubnetId" \
        --output text 2>/dev/null || echo "None")
    
    if [ "$SUBNET_ID" = "None" ] || [ "$SUBNET_ID" = "null" ]; then
        SUBNET_ID=$(aws ec2 create-subnet \
            --vpc-id $VPC_ID \
            --cidr-block 10.0.1.0/24 \
            --availability-zone ${AWS_REGION}a \
            --query 'Subnet.SubnetId' \
            --output text)
        
        aws ec2 create-tags \
            --resources $SUBNET_ID \
            --tags Key=Name,Value=vllm-poc-subnet
        
        aws ec2 modify-subnet-attribute \
            --subnet-id $SUBNET_ID \
            --map-public-ip-on-launch
        
        echo -e "${GREEN}✅ Created subnet: ${SUBNET_ID}${NC}"
    fi
    
    # Create route table
    ROUTE_TABLE_ID=$(aws ec2 describe-route-tables \
        --filters "Name=tag:Name,Values=vllm-poc-rt" \
        --query "RouteTables[0].RouteTableId" \
        --output text 2>/dev/null || echo "None")
    
    if [ "$ROUTE_TABLE_ID" = "None" ] || [ "$ROUTE_TABLE_ID" = "null" ]; then
        ROUTE_TABLE_ID=$(aws ec2 create-route-table \
            --vpc-id $VPC_ID \
            --query 'RouteTable.RouteTableId' \
            --output text)
        
        aws ec2 create-tags \
            --resources $ROUTE_TABLE_ID \
            --tags Key=Name,Value=vllm-poc-rt
        
        aws ec2 create-route \
            --route-table-id $ROUTE_TABLE_ID \
            --destination-cidr-block 0.0.0.0/0 \
            --gateway-id $IGW_ID
        
        aws ec2 associate-route-table \
            --subnet-id $SUBNET_ID \
            --route-table-id $ROUTE_TABLE_ID
        
        echo -e "${GREEN}✅ Created and configured route table${NC}"
    fi
    
    # Create security group
    SG_ID=$(aws ec2 describe-security-groups \
        --filters "Name=tag:Name,Values=vllm-poc-sg" \
        --query "SecurityGroups[0].GroupId" \
        --output text 2>/dev/null || echo "None")
    
    if [ "$SG_ID" = "None" ] || [ "$SG_ID" = "null" ]; then
        SG_ID=$(aws ec2 create-security-group \
            --group-name vllm-poc-sg \
            --description "Security group for vLLM PoC" \
            --vpc-id $VPC_ID \
            --query 'GroupId' \
            --output text)
        
        aws ec2 create-tags \
            --resources $SG_ID \
            --tags Key=Name,Value=vllm-poc-sg
        
        # Allow HTTP traffic
        aws ec2 authorize-security-group-ingress \
            --group-id $SG_ID \
            --protocol tcp \
            --port 8000 \
            --cidr 0.0.0.0/0
        
        # Allow SSH
        aws ec2 authorize-security-group-ingress \
            --group-id $SG_ID \
            --protocol tcp \
            --port 22 \
            --cidr 0.0.0.0/0
        
        echo -e "${GREEN}✅ Created security group: ${SG_ID}${NC}"
    fi
}

# Function to create ECR repository
setup_ecr() {
    echo -e "${YELLOW}📦 Setting up ECR repository...${NC}"
    
    if aws ecr describe-repositories --repository-names $ECR_REPO_NAME &> /dev/null; then
        echo -e "${GREEN}✅ ECR repository already exists${NC}"
    else
        aws ecr create-repository --repository-name $ECR_REPO_NAME
        echo -e "${GREEN}✅ Created ECR repository: ${ECR_REPO_NAME}${NC}"
    fi
    
    # Get login token and login to ECR
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
    echo -e "${GREEN}✅ Logged into ECR${NC}"
}

# Function to build and push Docker image
build_and_push() {
    echo -e "${YELLOW}🔨 Building and pushing Docker image...${NC}"
    
    IMAGE_URI="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:latest"
    
    # Build image
    docker build -t $ECR_REPO_NAME .
    docker tag $ECR_REPO_NAME:latest $IMAGE_URI
    
    # Push image
    docker push $IMAGE_URI
    
    echo -e "${GREEN}✅ Pushed image: ${IMAGE_URI}${NC}"
}

# Function to create ECS cluster
setup_ecs() {
    echo -e "${YELLOW}🚀 Setting up ECS cluster...${NC}"
    
    # Create ECS cluster
    if aws ecs describe-clusters --clusters $CLUSTER_NAME | grep -q "ACTIVE"; then
        echo -e "${GREEN}✅ ECS cluster already exists${NC}"
    else
        aws ecs create-cluster --cluster-name $CLUSTER_NAME
        echo -e "${GREEN}✅ Created ECS cluster: ${CLUSTER_NAME}${NC}"
    fi
    
    # Create IAM roles if they don't exist
    create_iam_roles
    
    # Update task definition with actual values
    sed -e "s/YOUR_ACCOUNT_ID/$ACCOUNT_ID/g" \
        -e "s/YOUR_REGION/$AWS_REGION/g" \
        aws/ecs-task-definition.json > aws/ecs-task-definition-updated.json
    
    # Register task definition
    aws ecs register-task-definition --cli-input-json file://aws/ecs-task-definition-updated.json
    echo -e "${GREEN}✅ Registered ECS task definition${NC}"
    
    # Update service definition
    sed -e "s/subnet-YOUR_SUBNET_ID/$SUBNET_ID/g" \
        -e "s/sg-YOUR_SECURITY_GROUP_ID/$SG_ID/g" \
        aws/ecs-service.json > aws/ecs-service-updated.json
    
    # Create or update ECS service
    if aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME | grep -q "ACTIVE"; then
        aws ecs update-service \
            --cluster $CLUSTER_NAME \
            --service $SERVICE_NAME \
            --task-definition vllm-poc
        echo -e "${GREEN}✅ Updated ECS service${NC}"
    else
        aws ecs create-service --cli-input-json file://aws/ecs-service-updated.json
        echo -e "${GREEN}✅ Created ECS service: ${SERVICE_NAME}${NC}"
    fi
}

# Function to create IAM roles
create_iam_roles() {
    echo -e "${YELLOW}🔐 Setting up IAM roles...${NC}"
    
    # Create ECS task execution role
    if ! aws iam get-role --role-name ecsTaskExecutionRole &> /dev/null; then
        aws iam create-role \
            --role-name ecsTaskExecutionRole \
            --assume-role-policy-document '{
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "ecs-tasks.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }'
        
        aws iam attach-role-policy \
            --role-name ecsTaskExecutionRole \
            --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
        
        echo -e "${GREEN}✅ Created ECS task execution role${NC}"
    fi
    
    # Create ECS task role
    if ! aws iam get-role --role-name ecsTaskRole &> /dev/null; then
        aws iam create-role \
            --role-name ecsTaskRole \
            --assume-role-policy-document '{
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "ecs-tasks.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }'
        
        echo -e "${GREEN}✅ Created ECS task role${NC}"
    fi
}

# Function to create launch template for GPU instances
create_launch_template() {
    echo -e "${YELLOW}💻 Creating EC2 launch template for GPU instances...${NC}"
    
    # Get latest ECS-optimized AMI for GPU
    AMI_ID=$(aws ec2 describe-images \
        --owners amazon \
        --filters "Name=name,Values=amzn2-ami-ecs-gpu-hvm-*" \
        --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
        --output text)
    
    echo -e "${BLUE}🖼️  Using AMI: ${AMI_ID}${NC}"
    
    # Create launch template
    aws ec2 create-launch-template \
        --launch-template-name vllm-poc-gpu-template \
        --launch-template-data '{
            "ImageId": "'$AMI_ID'",
            "InstanceType": "'$INSTANCE_TYPE'",
            "SecurityGroupIds": ["'$SG_ID'"],
            "IamInstanceProfile": {
                "Name": "ecsInstanceRole"
            },
            "UserData": "'$(echo '#!/bin/bash
echo ECS_CLUSTER='$CLUSTER_NAME' >> /etc/ecs/ecs.config
echo ECS_ENABLE_GPU_SUPPORT=true >> /etc/ecs/ecs.config' | base64 -w 0)'"
        }' || echo "Launch template may already exist"
    
    echo -e "${GREEN}✅ Created launch template for GPU instances${NC}"
}

# Main deployment function
main() {
    echo -e "${BLUE}Starting deployment to AWS...${NC}"
    
    setup_vpc
    setup_ecr
    build_and_push
    create_launch_template
    setup_ecs
    
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    echo -e "${BLUE}📝 Summary:${NC}"
    echo -e "   VPC ID: ${VPC_ID}"
    echo -e "   Subnet ID: ${SUBNET_ID}"
    echo -e "   Security Group ID: ${SG_ID}"
    echo -e "   ECR Repository: ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"
    echo -e "   ECS Cluster: ${CLUSTER_NAME}"
    echo -e "   ECS Service: ${SERVICE_NAME}"
    
    echo -e "${YELLOW}⚠️  Note: You'll need to manually launch EC2 instances in the ECS cluster with GPU support.${NC}"
    echo -e "${BLUE}🚀 To launch an instance:${NC}"
    echo -e "   aws ec2 run-instances \\"
    echo -e "     --launch-template LaunchTemplateName=vllm-poc-gpu-template \\"
    echo -e "     --subnet-id ${SUBNET_ID} \\"
    echo -e "     --instance-type ${INSTANCE_TYPE}"
}

# Run main function
main "$@"