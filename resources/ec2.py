import boto3
from resources.config import *

def get_valid_action():
    """
    Prompts the user to enter a valid action (start or stop) for managing EC2 instances.
    If the input is invalid, the function continues prompting until a valid input is received or the user exits.
    """
    action = input("Do you want to start or stop an instance? (start/stop): ").strip().lower()
    
    while action not in ["start", "stop"]:
        print("Invalid action. Please enter 'start' or 'stop': ")
        action = input().strip().lower()  

    return action 

#CHECK IF THERE IS SAME NAME TO DIFFRENTE INSTANCES

def get_instance_by_name(ec2, instance_name, filter_state=None):
    """
    Searches for EC2 instances by name (tag:Name) and allows the user to select one if multiple instances are found.
    
    :param ec2: boto3 resource object
    :param instance_name: The name of the instance to search for
    :param filter_state: (Optional) The state of the instance (running/stopped)
    :return: The selected EC2 instance object
    """
    filters = [{'Name': 'tag:Name', 'Values': [instance_name]}]
    if filter_state:
        filters.append({'Name': 'instance-state-name', 'Values': [filter_state]})

    instances = list(ec2.instances.filter(Filters=filters))

    instances = [instance for instance in instances if instance.state['Name'] not in ["terminated", "shutting-down"]]

    if not instances:
        print(f" No instances found with name '{instance_name}'.")
        return None

    if len(instances) > 1:
        print(f"\n🔹 Multiple instances found with name '{instance_name}'. Please choose one:")
        print(f"{'Instance ID':<20} {'State':<10} {'Public IP':<15} {'Private IP'}")
        print("=" * 60)

        for instance in instances:
            name_tag = next((tag['Value'] for tag in instance.tags if tag['Key'] == 'Name'), "N/A") if instance.tags else "N/A"
            print(f"{instance.id:<20} {instance.state['Name']:<10} {str(instance.public_ip_address) if instance.public_ip_address else 'N/A':<15} {instance.private_ip_address}")

        instance_id = input("\nEnter the Instance ID you want to manage: ").strip()
        instance = next((i for i in instances if i.id == instance_id), None)

        if not instance:
            print(f" No instance found with ID '{instance_id}'. Operation cancelled.")
            return None
    else:
        instance = instances[0]

    return instance

#CHECK FOR RUNNING INSTANCES

def check_running_instances():
    """
    Checks the number of running EC2 instances created via the CLI. 
    If the limit of running instances (e.g., 2) is reached, it prevents the creation or starting of new instances.
    
    :return: True if a new instance can be created or started, False otherwise.
    """

    ec2 = boto3.resource('ec2', region_name=REGION_NAME)

    # Searching for all the runnung instances
    running_instances = list(ec2.instances.filter(
        Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
    ))

    if len(running_instances) >= 2:
        print("You already have 2 running instances. Cannot create or start more.")
        print("""Here is the list of all running instances:
                |
                v
              """)

        # Call the function that displays instances created via the CLI
        list_cli_instances()

        return False  # Returns False if the action cannot proceed.

    return True  # Returns True if the action can proceed.

#MANAGE EC2

def manage_ec2_instance():
    """
    Manages EC2 instances by allowing the user to start or stop an instance.
    The function first lists all available instances that can be managed,
    ensuring that only instances created via the CLI are included.
    
    The user is prompted to select an instance by name or ID and choose an action.
    If the instance is already in the desired state, no action is taken.
    
    Additional checks ensure that no more than two instances are running at a time.
    If the user attempts to start an instance while the limit is reached, the action is denied.

    Exceptions are handled to ensure a smooth user experience in case of AWS errors.
    """
    ec2 = boto3.resource('ec2', region_name=REGION_NAME)

    action = input("Do you want to start or stop an instance? (start/stop): ").strip().lower()

    action = get_valid_action()

    # Searching for all instances that can have the action performed on them
    filter_state = "stopped" if action == "start" else "running"
    instances = list(ec2.instances.filter(
        Filters=[{'Name': 'instance-state-name', 'Values': [filter_state]}]
    ))

    # If there are no instances in the appropriate state – display a message and stop the operation
    if not instances:
        print(f"No {filter_state} instances available to {action}.")
        return

    # Display a list of instances that can be started/stopped
    print(f"\nAvailable instances to {action}:")
    print(f"{'Instance ID':<20} {'Name':<15} {'Public IP':<15} {'Private IP'}")
    print("=" * 60)

    for instance in instances:
        name_tag = next((tag['Value'] for tag in instance.tags if tag['Key'] == 'Name'), "N/A") if instance.tags else "N/A"
        print(f"{instance.id:<20} {name_tag:<15} {str(instance.public_ip_address) if instance.public_ip_address else 'N/A':<15} {instance.private_ip_address}")

    # Receive `Instance ID` or name from the user
    instance_identifier = input("\nEnter the Instance Name or Instance ID to manage: ").strip()

    # Search by name (Name Tag)
    filtered_instances = list(ec2.instances.filter(
        Filters=[
            {'Name': 'tag:Name', 'Values': [instance_identifier]},
            {'Name': 'instance-state-name', 'Values': [filter_state]}
        ]
    ))

    # If not found by name, try searching by Instance ID
    if not filtered_instances:
        filtered_instances = list(ec2.instances.filter(
            Filters=[{'Name': 'instance-id', 'Values': [instance_identifier]}]
        ))

    if not filtered_instances:
        print(f" No instance found with Name or ID '{instance_identifier}'. Operation cancelled.")
        return

    # If multiple instances have the same name, ask the user to select an Instance ID
    if len(filtered_instances) > 1:
        print(f"\n🔹 Multiple instances found with name '{instance_identifier}'. Please choose one:")
        print(f"{'Instance ID':<20} {'State':<10} {'Public IP':<15} {'Private IP'}")
        print("=" * 60)

        for instance in filtered_instances:
            name_tag = next((tag['Value'] for tag in instance.tags if tag['Key'] == 'Name'), "N/A") if instance.tags else "N/A"
            print(f"{instance.id:<20} {instance.state['Name']:<10} {str(instance.public_ip_address) if instance.public_ip_address else 'N/A':<15} {instance.private_ip_address}")

        instance_id = input("\nEnter the Instance ID you want to manage: ").strip()
        instance = next((i for i in filtered_instances if i.id == instance_id), None)

        if not instance:
            print(f"No instance found with ID '{instance_id}'. Operation cancelled.")
            return
    else:
        instance = filtered_instances[0]

    instance_id = instance.id
    instance_state = instance.state['Name'].strip().lower()

    try:
        # Check if the instance is in the correct state for the requested action
        valid_states = {"start": "stopped", "stop": "running"}

        if instance_state != valid_states[action]:
            print(f"Instance {instance_id} is {instance_state}. Impossible to {action}.")
            return

        # If starting an instance, check the limit of running instances
        if action == "start" and not check_running_instances():
            return

        print(f"{action.capitalize()}ing instance {instance_id}...")

        # Perform the appropriate action
        getattr(instance, action)()

        print(f"Instance {instance_id} has been {action}ed successfully.")

    except Exception as e:
        print(f"Failed to {action} instance {instance_id}: {e}")


#CREATE EC2
def create_ec2_instance():
    """
    Creates a new EC2 instance with user-defined specifications.
    
    - Asks the user to enter a name for the instance.
    - Checks if the user has reached the limit of running instances before proceeding.
    - Allows the user to choose between Ubuntu and Amazon Linux AMIs.
    - Configures instance details such as type, key pair, and networking settings.
    - Assigns tags to indicate ownership and creation source.
    - Displays success or failure messages based on the instance creation result.

    :return: The created instance ID if successful, None otherwise.
    """
    instance_name = input("Enter instance name: ")

    if not check_running_instances():
        return    

    ec2 = boto3.resource('ec2', region_name=REGION_NAME)
    
    while True:
        image_choice = input("Enter instance AMI (press 'u' for Ubuntu, 'a' for Amazon Linux, or 'q' to quit): ").strip().lower()

        if image_choice == 'a':
            image_id = AMAZON_LINUX_AMI
            break
        elif image_choice == 'u':
            image_id = UBUNTU_AMI
            break
        elif image_choice == 'q':
            print("Exiting program...")
            exit()
        else:
            print("Invalid input! Please enter 'u' for Ubuntu, 'a' for Amazon Linux, or 'q' to quit.")

    while True:
        type_choice = input("Enter instance type (press 't3' for Ubuntu, 't4' for Amazon Linux, or 'q' to quit): ").strip().lower()

        if type_choice == 't3':
            instance_type = INSTANCE_TYPE_T3
            break
        elif type_choice == 't4':
            instance_type = INSTANCE_TYPE_T4G
            break
        elif type_choice == 'q':
            print("Exiting program...")
            exit()
        else:
            print("Invalid input! Please enter 't3' for t3.nano, 't4' for t4g.nano, or 'q' to quit.") 

    try:
        instances = ec2.create_instances(
            ImageId=image_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            KeyName=KEY_NAME,
            NetworkInterfaces=[
                {
                    'SubnetId': SUBNET_ID,
                    'DeviceIndex': 0,
                    'AssociatePublicIpAddress': True
                }
            ],
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'Name', 'Value': instance_name},
                        {'Key': 'Owner', 'Value': OWNER_NAME},
                        {'Key': 'CreatedBy', 'Value': OWNER_NAME}
                    ]
                }
            ]
        )

        instance_id = instances[0].id
        print(f" Instance {instance_id} created successfully with name '{instance_name}' using {image_id} AMI")
        return instance_id

    except Exception as e:
        print(f"Failed to create instance: {e}")
        return None
#DELETE EC2

def delete_instance():
    """
    Deletes an EC2 instance based on user input.
    
    - Displays a list of available instances that can be deleted.
    - Asks the user to enter the instance name to delete.
    - If multiple instances exist with the same name, allows the user to select the correct one by Instance ID.
    - Confirms the deletion with the user before proceeding.
    - Sends a termination request to AWS for the selected instance.
    - Displays success or failure messages based on the termination result.

    :return: None
    """
    ec2 = boto3.resource('ec2', region_name=REGION_NAME)

    instances = list(ec2.instances.filter(
        Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped']}]
    ))

    # If theres no instances to delete - canceling the action
    if not instances:
        print(" No instances available for deletion.")
        return

    # Show all the available instances to delete
    print("\nAvailable instances to delete:")
    print(f"{'Instance ID':<20} {'Name':<20} {'State':<10} {'Public IP':<15} {'Private IP'}")
    print("=" * 80)

    for instance in instances:
        name_tag = next((tag['Value'] for tag in instance.tags if tag['Key'] == 'Name'), "N/A") if instance.tags else "N/A"
        print(f"{instance.id:<20} {name_tag:<20} {instance.state['Name']:<10} {str(instance.public_ip_address) if instance.public_ip_address else 'N/A':<15} {instance.private_ip_address}")


    instance_name = input("Enter the instance name to delete: ").strip()

    # Using the new function to find the appropriate instance.
    instance = get_instance_by_name(ec2, instance_name)

    if not instance:
        return  # If no suitable instance is found, the operation is canceled.

    instance_id = instance.id

    # User deletion confirmation.
    confirm = input(f"Are you sure you want to terminate instance {instance_id}? (y/N): ").strip().lower()
    if confirm != "y":
        print("Termination cancelled.")
        return

    try:
        print(f"Terminating instance {instance_id}...")
        instance.terminate()
        print(f"Instance {instance_id} has been terminated successfully.")
    except Exception as e:
        print(f"Failed to terminate instance {instance_id}: {e}")

#LIST OF ALL THE INSTANCES
def list_cli_instances():

    ec2 = boto3.resource('ec2', region_name=REGION_NAME)

    # Search for all instances containing the 'Owner=' tag.
    instances = list(ec2.instances.filter(
        Filters=[{'Name': 'tag:CreatedBy', 'Values': [OWNER_NAME]}]
    ))

    instances = [instance for instance in instances if instance.state['Name'] not in ["terminated", "shutting-down"]]

    if not instances:
        print("No instances found that were created using the CLI.")
        return

    print(f"Found {len(instances)} instances created via CLI:\n")
    print(f"{'Instance ID':<20} {'State':<12} {'Public IP':<15} {'Private IP':<15} {'Name':<20}")

    print("-" * 80)

    for instance in instances:
        instance_id = instance.id
        state = instance.state['Name']
        public_ip = instance.public_ip_address if instance.public_ip_address else "N/A"
        private_ip = instance.private_ip_address if instance.private_ip_address else "N/A"

        # Retrieving the instance name from tags (if available).
        name_tag = next((tag['Value'] for tag in instance.tags if tag['Key'] == 'Name'), "Unnamed")

        print(f"{instance_id:<20} {state:<12} {public_ip:<15} {private_ip:<15} {name_tag:<20}")



def main():
    ACTION_MAP = {
        "1": manage_ec2_instance,
        "2": delete_instance,
        "3": create_ec2_instance,
        "4": list_cli_instances
    }

    while True:  # Loop until valid value
        user_action_choice = input(
    """\nBefore we start, tell me what you want to do with EC2:
    1. Manage an instance (start/stop)
    2. Delete an instance
    3. Create a new instance
    4. List all instances
    \nEnter your choice (1-4): """)

        if user_action_choice in ACTION_MAP:
            ACTION_MAP[user_action_choice]()  # Calling the appropriate function.
            break  # Exit the function after the action
        else:
            print("Invalid choice. Please enter a number between 1 and 4.")

if __name__ == "__main__":
    main()

