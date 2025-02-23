DevOps CLI Tool for AWS

This CLI tool allows developers to create, update, and delete AWS resources (EC2, S3, Route 53) securely and efficiently, while ensuring compliance with DevOps best practices.

- Features

EC2 Management: Create, start, stop, and delete EC2 instances.

S3 Buckets: Create, upload files, list, and delete S3 buckets (only those created via CLI).

Route 53 DNS: Create Hosted Zones and manage DNS records securely.

User Confirmation for Public Buckets: Ensures public resources are approved explicitly.

Security Best Practices: Prevents credential leaks and manages AWS resources safely.

- Installation

Prerequisites

#Python3 3.8+

AWS CLI installed and configured (aws configure)

Required #Python3 packages (install using pip)

#pip install -r requirements.txt

- Usage

Running the CLI

To start the CLI, run the following command:

General Syntax

#python3 aws_manager.py

This will launch the interactive menu, allowing you to manage EC2 instances, S3 buckets, and Route 53 DNS records.

- Example Commands

EC2 Management

Create an EC2 instance:

#python3 cli.py ec2 create --instance-type t3.nano --ami ubuntu --key-name my-key

Start an EC2 instance:

#python3 cli.py ec2 start --instance-id i-0123456789abcdef

Stop an EC2 instance:

#python3 cli.py ec2 stop --instance-id i-0123456789abcdef

Delete an EC2 instance:

#python3 cli.py ec2 delete --instance-id i-0123456789abcdef

- S3 Bucket Management

Create a new S3 bucket (private/public with confirmation):

#python3 cli.py s3 create --name my-new-bucket --access public

Upload a file to an S3 bucket:

#python3 cli.py s3 upload --bucket-name my-new-bucket --file /path/to/file.txt --key my-folder/file.txt

List all S3 buckets created via CLI:

#python3 cli.py s3 list

Delete an S3 bucket:

#python3 cli.py s3 delete --bucket-name my-old-bucket

- Route 53 DNS Management

Create a new Route 53 Hosted Zone:

#python3 cli.py route53 create --domain-name example.com

Add or update a DNS record:

#python3 cli.py route53 update --zone-id Z123456ABC --record-name sub.example.com --record-type A --record-value 192.168.1.1 --ttl 300

Delete a DNS record:

#python3 cli.py route53 delete --zone-id Z123456ABC --record-name sub.example.com --record-type A

List Hosted Zones created via CLI:

#python3 cli.py route53 list

- Security Best Practices

Do NOT hardcode AWS credentials. Use environment variables or AWS profiles.

Use IAM roles for better security instead of direct access keys.

Public buckets require explicit confirmation before creation.

Sensitive operations require user confirmation to prevent accidental deletions.

- Contribution

If you find a bug or want to improve the CLI, feel free to contribute by forking the repo and submitting a pull request.

- Troubleshooting

If boto3 is not installed, run:

#pip install boto3

If AWS CLI is not configured, run:

#aws configure

If permission errors occur, ensure you have the correct IAM permissions.

- License 

This project is licensed under the MIT License.# Platform-Engineering-Python
# Platform-Engineering-Python
