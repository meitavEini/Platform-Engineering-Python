import boto3
import os
import json
import re
import botocore
from config import *

# CHECKS IF THE NAME IS VALID
def is_valid_bucket_name(bucket_name):
    """
    Checks if the given S3 bucket name follows AWS naming conventions.
    
    - Length must be between 3 and 63 characters.
    - Can only contain lowercase letters, numbers, dots (.), and hyphens (-).
    - Cannot start or end with a dot (.) or hyphen (-).
    - Cannot contain consecutive dots (..), ".-" or "-.".
    - Cannot start with 'xn--' or 'sthree-' (reserved prefixes).
    - Cannot contain 'aws' or 's3' (reserved keywords).
    
    Returns True if the name is valid, otherwise False.
    """
    if not (3 <= len(bucket_name) <= 63):
        return False  # The name must be between 3 and 63 characters long.
    
    if not re.match(r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$', bucket_name):
        return False  # Validate that the characters are valid.

    if '..' in bucket_name or '.-' in bucket_name or '-.' in bucket_name:
        return False  # Consecutive dots or hyphens are not allowed.
    
    if bucket_name.startswith('xn--') or bucket_name.startswith('sthree-'):
        return False  # Names starting with IDN prefixes or AWS reserved names are not allowed.
    
    if 'aws' in bucket_name or 's3' in bucket_name:
        return False  # The name must not contain 'aws' or 's3'.

    
    return True  # If all conditions pass, the name is valid.

#CHECKS IF THE BUCKET IS EMPTY

def check_and_delete_files_in_bucket(s3, bucket_name):
    """
    Checks if the given S3 bucket contains any files and allows the user to delete them.

    - Retrieves the list of objects stored in the specified bucket.
    - If the bucket is empty, notifies the user and exits.
    - If the bucket contains files, displays them as a numbered list.
    - Prompts the user to select a file for deletion or exit the process.
    - Allows the user to repeatedly delete files until they choose to exit.

    :param s3: Boto3 S3 client object.
    :param bucket_name: Name of the S3 bucket to check and manage files.
    """ 
    try:
        response = s3.list_objects_v2(Bucket=bucket_name)
        files = [obj['Key'] for obj in response.get('Contents', [])]

        if not files:
            print(f"The bucket '{bucket_name}' is empty.")
            return False  # No files in the bucket. Deletion is not required.

        print(f"\nBucket '{bucket_name}' contains the following files:")
        for idx, file in enumerate(files, 1):
            print(f"{idx}. {file}")

        while True:
            file_choice = input("\nEnter the file number to delete (or 'q' to cancel): ").strip()

            if file_choice.lower() == 'q':
                print("Operation cancelled. No files were deleted.")
                return False  # The user choose to exit

            try:
                file_choice = int(file_choice)
                if 1 <= file_choice <= len(files):
                    file_to_delete = files[file_choice - 1]
                    s3.delete_object(Bucket=bucket_name, Key=file_to_delete)
                    print(f"File '{file_to_delete}' deleted successfully.")
                    return True  # The file deletes successfully:)
            except ValueError:
                print("Invalid input. Please enter a valid file number or 'q' to cancel.")

    except Exception as e:
        print(f"Failed to check files in bucket '{bucket_name}': {e}")
        return False

#GETS ONLY AVAILABLE NAMES FOR BUCKET

def get_available_bucket_name(s3):

    """Receives a valid name from the user and ensures it is available."""

    while True:
        bucket_name = input("The name u enter needs to be a unique S3 bucket name,\nPlease enter a new unique name: (or 'q' to exit): ").strip()

        if bucket_name.lower() == 'q':  
            print("Bucket creation cancelled.")
            return None  

        if not is_valid_bucket_name(bucket_name):  # Check if the name is valid
            print("Invalid bucket name. Make sure it meets AWS naming rules.")
            continue  # Return to the loop to get a new name

        # Check if the name already exists in S3
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"The bucket name '{bucket_name}' is already taken. Try another name.")
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":  # The bucket not exist, can be used!!
                return bucket_name  
            print(f"AWS error: {e}")

#CREATE A BUCKET

def create_s3_bucket():
    """
    Creates an S3 bucket with the option to set it as public or private.

    - Prompts the user to enter a valid bucket name and ensures it adheres to AWS naming rules.
    - Checks if the bucket name is already in use and prompts the user to enter a different name if needed.
    - Allows the user to choose between a public or private bucket.
    - If a public bucket is selected, the user must confirm before proceeding.
    - Creates the bucket and applies the appropriate access permissions.
    - Adds a tag indicating that the bucket was created via the CLI.
    - Displays success or failure messages based on the outcome of the creation process.
    """

    s3 = boto3.client("s3", region_name=REGION_NAME)

    bucket_name = input("Enter bucket name: ").strip()
    bucket_name = get_available_bucket_name(s3)  # Performs a check if the name is already taken, allowing the user to enter a new name.

    if not bucket_name:
        return  # The user cancel the action

    
    try:
        # Setting public or private permissions
        access_type = input("Should the bucket be public or private? (public/private): ").strip().lower()
        response = s3.create_bucket(Bucket=bucket_name)
        print(f"S3 Bucket '{bucket_name}' created successfully.")

        # ADDING TAG TO THE BUCKET
        s3.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={
                'TagSet': [
                    {'Key': 'CreatedBy', 'Value': OWNER_NAME}
                ]
            }
        )

        print(f"Tag 'CreatedBy= '{OWNER_NAME}' added to bucket '{bucket_name}'.")

        if access_type == "public":
            # Unblocking public policy (if allowed by your account)
            s3.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': False,
                    'IgnorePublicAcls': False,
                    'BlockPublicPolicy': False,  
                    'RestrictPublicBuckets': False
                }
            )

            # ADDING POLICY TO THR BUCKET
            policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/*"
                }]
            }
            s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))

        print(f"S3 Bucket '{bucket_name}' configured as {access_type}.")

    except Exception as e:
        print(f"Failed to create bucket: {e}")

#UPLOAD A FILE

def upload_file_to_s3():
    """
    Uploads a file to an S3 bucket, but only if the bucket was created via the CLI.

    This function retrieves and displays a list of S3 buckets that were created using the CLI.
    The user is prompted to select a valid bucket and provide a file path for upload.
    If the file path is invalid, the function continues prompting until a valid file is provided
    or the user chooses to exit.

    Once the file is successfully uploaded, a confirmation message is displayed.

    Returns:
        None
    """

    s3 = boto3.client('s3')

    # Displaying all buckets created via the CLI
    response = s3.list_buckets()
    cli_buckets = [
        bucket['Name'] for bucket in response['Buckets']
        if is_cli_created_bucket(bucket['Name'], s3)
    ]

    if not cli_buckets:
        print("No available CLI-created S3 buckets found.")
        return

    print("\nAvailable S3 Buckets (created via CLI):")
    for bucket in cli_buckets:
        print(f"- {bucket}")

    while True:
        bucket_name = input("\nEnter the name of the S3 bucket to upload to (or 'q' to cancel): ").strip()

        if bucket_name.lower() == "q":
            print("Upload cancelled.")
            return  # Exit the function

        if bucket_name in cli_buckets:
            break  #  Exit the loop if the bucket name is valid

        print(f"Invalid bucket name. You can only upload to S3 buckets created via CLI. Try again or enter 'q' to exit.")

    while True:  # Loop to allow multiple file uploads in succession
        # Request the file path for upload
        while True:
            file_path = input("\nEnter the file path to upload (or 'q' to cancel): ").strip()

            if file_path.lower() == "q":
                print("Upload cancelled.")
                return  # Exit the function

            if os.path.isfile(file_path):  # Check if the file exists
                file_name = os.path.basename(file_path)  # Extract the file name from the path
                break  # Exit the loop if the file exists

            print("Invalid file path. File does not exist. Try again or enter 'q' to exit.")

        try:
            s3.upload_file(file_path, bucket_name, file_name)
            print(f"File '{file_name}' uploaded successfully to bucket '{bucket_name}'.")
        except Exception as e:
            print(f"Failed to upload file: {e}")

        # Asking if the user want to upload another file
        while True:
            another_file = input("Do you want to upload another file? (y/n): ").strip().lower()
            if another_file in ["y", "n"]:
                break  # Exit the loop if the input is valid
            print("Invalid input. Please enter 'y' or 'n'.")

        if another_file == "n":
            print("Upload process completed.")
            return  # Exit the function if the user dosent want to create another file


#CHECKS IF BUCKET CREATED BY CLI

def is_cli_created_bucket(bucket_name, s3):
    """
    Checks if the specified S3 bucket was created via the CLI.

    This function retrieves the tags associated with the given S3 bucket and verifies
    if it contains the 'CreatedBy' tag with the value 'cli-meitaveini'. This ensures
    that only buckets explicitly created through the CLI tool are recognized.

    Args:
        bucket_name (str): The name of the S3 bucket to check.
        s3 (boto3.client): The S3 client instance.

    Returns:
        bool: True if the bucket was created via the CLI, False otherwise.
    """

    try:
        response = s3.get_bucket_tagging(Bucket=bucket_name)
        for tag in response['TagSet']:
            if tag['Key'] == "CreatedBy" and tag['Value'] == OWNER_NAME:
                return True
    except s3.exceptions.ClientError:
        pass  # If there are no tags or no permission, the bucket is not considered ours

    return False



def delete_s3_bucket():
    """
    Deletes an S3 bucket created via the CLI.

    This function lists all S3 buckets that were created using the CLI and allows the user to select one for deletion. 
    Before deletion, it checks if the bucket is empty. If the bucket contains files, the user is given the option to 
    delete the files before proceeding with the bucket deletion.

    The function also requires explicit user confirmation before permanently deleting a bucket to prevent accidental 
    deletions.

    If the user chooses to cancel at any stage, the function safely exits.
    """

    s3 = boto3.client('s3')

    #Retrieving all buckets created via the CLI

    response = s3.list_buckets()
    cli_buckets = [
        bucket['Name'] for bucket in response['Buckets']
        if is_cli_created_bucket(bucket['Name'], s3)
    ]

    #  IF THERES NOT AVAILABLE BUCKETS CANCELING THE ACTION
    if not cli_buckets:
        print("No S3 buckets created via CLI are available for deletion.")
        return

    #  LIST ALL THE AVAILABLE BUCKETS TO DELETE
    print("\nAvailable S3 Buckets for Deletion:")
    print("=" * 40)
    for bucket in cli_buckets:
        print(f"- {bucket}")
    print("=" * 40)

    #  GETS NAME TO DELETE
    while True:
        bucket_name = input("Enter the S3 bucket name to delete (or 'q' to exit): ").strip()

        if bucket_name.lower() == 'q':  
            print("Bucket deletion cancelled.")
            return  

        matching_buckets = [b for b in s3.list_buckets()["Buckets"] if b["Name"] == bucket_name]

        if not matching_buckets:
            print(f"No S3 buckets found with name '{bucket_name}'. Please try again.")
        else:
            break  # Getting out of the function if the bucket name is valid


    check_and_delete_files_in_bucket(s3, bucket_name)
    """
    This function checks if an S3 bucket contains any files.
    If the bucket is not empty, it prompts the user to confirm deletion of specific files before proceeding.
    The user can choose to delete files individually or exit the process.
    """

    # Confirm the Deletion
    confirm = input(f"Are you sure you want to delete the bucket '{bucket_name}'? (y/N): ").strip().lower()
    if confirm != "y":
        print("Deletion cancelled.")
        return

    #  Deleting bucket
    try:
        print(f"Deleting bucket '{bucket_name}'...")
        s3.delete_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' has been deleted successfully.")
    except Exception as e:
        print(f"Failed to delete bucket: {e}")

#LIST OF ALL THE BUCKETS

def list_s3_buckets():
    """
    This function retrieves and displays all S3 buckets that were created via the CLI.
    It ensures that only relevant buckets are listed, filtering out those created by other methods.
    """
    s3 = boto3.client("s3")

    try:
        response = s3.list_buckets()
        buckets = response.get('Buckets', [])

        if not buckets:
            print("No S3 buckets found.")
            return

        print("\nAvailable S3 Buckets for deletion:")
        print(f"{'Bucket Name':<30} {'Creation Date'}")
        print("=" * 50)

        for bucket in buckets:
            print(f"{bucket['Name']:<30} {bucket['CreationDate']}")

        return buckets

    except Exception as e:
        print(f"Failed to list buckets: {e}")
        return []

def main():
    """
    The main function serves as the entry point for the CLI tool.
    It provides an interactive menu where users can choose to manage EC2 instances,
    S3 buckets, or Route 53 DNS records. Based on user input, it directs execution to the appropriate functions.
    """

    ACTION_MAP = {
        "1": create_s3_bucket,
        "2": upload_file_to_s3,
        "3": delete_s3_bucket,
        "4": list_s3_buckets
    }

    while True:  # Loop until getting valid value
        user_action_choice = input(
"""\nBefore we start, tell me what you want to do with S3:
1. Create s3 bucket
2. Upload file to s3
3. Delete a bucket
4. List cli buckets
\nEnter your choice (1-4): """)

        if user_action_choice in ACTION_MAP:
            ACTION_MAP[user_action_choice]()  # Call the appropriate function.
            break  # Exit from the loop after the action
        else:
            print("Invalid choice. Please enter a number between 1 and 4.")


if __name__ == "__main__":
    main()