#!/bin/bash

# QUICKEST AWS deployment - launches single EC2 instance with Docker
set -e

echo "🚀 Quick AWS vLLM PoC Test Deployment"
echo "====================================="

# Configuration
INSTANCE_TYPE="g4dn.xlarge"  # GPU instance, change to t3.medium for CPU testing
KEY_NAME="vllm-test-key"
SECURITY_GROUP="vllm-quick-sg"

# Get latest Ubuntu AMI with Docker
AMI_ID=$(aws ec2 describe-images \
  --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-22.04-amd64-server-*" \
  --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
  --output text)

echo "📝 Using AMI: $AMI_ID"

# Create key pair if it doesn't exist
if ! aws ec2 describe-key-pairs --key-names $KEY_NAME &>/dev/null; then
    echo "🔑 Creating key pair..."
    aws ec2 create-key-pair --key-name $KEY_NAME --query 'KeyMaterial' --output text > ${KEY_NAME}.pem
    chmod 400 ${KEY_NAME}.pem
    echo "✅ Key pair created: ${KEY_NAME}.pem"
else
    echo "✅ Key pair already exists"
fi

# Create security group
SG_ID=$(aws ec2 create-security-group \
    --group-name $SECURITY_GROUP \
    --description "Quick vLLM test" \
    --query 'GroupId' --output text 2>/dev/null || \
    aws ec2 describe-security-groups \
    --group-names $SECURITY_GROUP \
    --query 'SecurityGroups[0].GroupId' --output text)

# Add rules to security group
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp --port 22 --cidr 0.0.0.0/0 2>/dev/null || true

aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp --port 8000 --cidr 0.0.0.0/0 2>/dev/null || true

echo "✅ Security group ready: $SG_ID"

# Create user data script
cat > user-data.sh << 'EOF'
#!/bin/bash
apt-get update
apt-get install -y docker.io git curl

# Start Docker
systemctl start docker
systemctl enable docker
usermod -aG docker ubuntu

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Clone the repo and run
cd /home/ubuntu
git clone https://github.com/YOUR_USERNAME/vLLM-PoC.git vllm-poc
cd vllm-poc

# Setup Python environment and run
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-simple.txt

# Run the server in background
nohup python app_simple.py > server.log 2>&1 &

# Wait for service to start
sleep 30

# Test the service
curl -f http://localhost:8000/health || echo "Service not ready yet"
EOF

# Launch instance
echo "🚀 Launching EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --count 1 \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_NAME \
    --security-group-ids $SG_ID \
    --user-data file://user-data.sh \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=vllm-poc-test}]' \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "✅ Instance launched: $INSTANCE_ID"
echo "⏳ Waiting for instance to be running..."

# Wait for instance to be running
aws ec2 wait instance-running --instance-ids $INSTANCE_ID

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo ""
echo "🎉 DEPLOYMENT COMPLETE!"
echo "======================"
echo "Instance ID: $INSTANCE_ID"
echo "Public IP: $PUBLIC_IP"
echo "SSH: ssh -i ${KEY_NAME}.pem ubuntu@$PUBLIC_IP"
echo ""
echo "⏳ Wait 2-3 minutes for setup to complete, then test:"
echo "🔗 Health: http://$PUBLIC_IP:8000/health"
echo "🔗 API: http://$PUBLIC_IP:8000/docs"
echo ""
echo "Test API:"
echo "curl -X POST http://$PUBLIC_IP:8000/v1/chat/completions \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"messages\":[{\"role\":\"user\",\"content\":\"Hello!\"}]}'"
echo ""
echo "🗑️  To cleanup: aws ec2 terminate-instances --instance-ids $INSTANCE_ID"

# Cleanup temp files
rm -f user-data.sh