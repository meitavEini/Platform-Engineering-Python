import boto3
from resources.config import *
import botocore

def is_cli_created_zone(zone_id, route53):
    """
    Checks if a Hosted Zone was created via the CLI.

    This function:
    - Retrieves tags associated with the given Hosted Zone.
    - Verifies whether the 'CreatedBy' tag is set to 'cli-meitaveini'.
    - Returns True if the Hosted Zone was created via the CLI, otherwise returns False.

    This ensures that only Hosted Zones managed through the CLI can be modified 
    or deleted, preventing unintended changes to externally managed zones.
    """
    try:
        response = route53.list_tags_for_resource(ResourceType='hostedzone', ResourceId=zone_id)
        for tag in response['ResourceTagSet']['Tags']:
            if tag['Key'] == "CreatedBy" and tag['Value'] == OWNER_NAME:
                return True
    except route53.exceptions.ClientError:
        pass
    return False

def get_domain_name():
    """
    Checks if a given Route 53 DNS zone was created via the CLI.

    This function retrieves the tags associated with the specified Hosted Zone and verifies
    whether it includes the 'CreatedBy' tag with the value 'cli-meitaveini'. This ensures that
    only zones explicitly created through the CLI tool are recognized for further management.

    Args:
        zone_id (str): The ID of the DNS Hosted Zone to check.
        route53 (boto3.client): The Route 53 client instance.

    Returns:
        bool: True if the Hosted Zone was created via the CLI, False otherwise.
    """
    tlds = [".com", ".net", ".org", ".info", ".io", ".co", ".tech", ".ai"]

    while True:
        domain_name = input("Enter the domain name (without TLD) or 'q' to quit: ").strip()

        if domain_name.lower() == "q":
            print("Exiting domain selection.")
            return None  # Canceling the action if the user want to exit

        if not domain_name:
            print("Domain name cannot be empty. Please try again.")
            continue

        print("\nSelect a TLD from the following options:")
        for idx, tld in enumerate(tlds, 1):
            print(f"{idx}. {tld}")

        while True:
            tld_choice = input("\nEnter the number of your chosen TLD or 'q' to cancel: ").strip()

            if tld_choice.lower() == "q":
                print("Exiting domain selection.")
                return None

            if tld_choice.isdigit() and 1 <= int(tld_choice) <= len(tlds):
                full_domain_name = domain_name + tlds[int(tld_choice) - 1]
                print(f"Selected domain: {full_domain_name}")
                return full_domain_name
            else:
                print("Invalid choice. Please enter a valid number from the list.")


def create_dns_zone():
    """
    Creates a new DNS Hosted Zone in AWS Route 53.

    This function prompts the user for a domain name and checks if the domain already exists
    in Route 53. If the domain name is available, a new Hosted Zone is created with a tag
    identifying it as created via the CLI. The user can cancel the operation at any time.

    Steps:
    1. Lists existing Hosted Zones to ensure uniqueness.
    2. Asks the user to input a domain name.
    3. Creates the Hosted Zone if it doesn't already exist.
    4. Adds a 'CreatedBy' tag to identify CLI-managed zones.

    Returns:
        None
    """

    route53 = boto3.client('route53')
    
    while True:
        domain_name = get_domain_name()  # Asks the user for a domain name with an extension

        if not domain_name:
            return  # If the user want to exit no need to continue

        try:
            # Checking if the domain exist
            existing_zones = route53.list_hosted_zones()['HostedZones']
            if any(zone['Name'].rstrip('.') == domain_name for zone in existing_zones):
                print(f"The domain '{domain_name}' already exists. Please choose a different name or enter 'q' to exit.")
                continue  # Loop back to enter a new name


            #  Creating the - Hosted Zone
            response = route53.create_hosted_zone(
                Name=domain_name,
                CallerReference=str(hash(domain_name)),
                HostedZoneConfig={'Comment': 'Created via CLI', 'PrivateZone': False}
            )

            hosted_zone_id = response['HostedZone']['Id'].split('/')[-1]

            # Adding a tag to indicate that the Hosted Zone was created via the CLI
            route53.change_tags_for_resource(
                ResourceType='hostedzone',
                ResourceId=hosted_zone_id,
                AddTags=[{'Key': 'CreatedBy', 'Value': OWNER_NAME}]
            )

            print(f"DNS zone '{domain_name}' created successfully with ID {hosted_zone_id}.")
            return  # Exit the function if successful

        except botocore.exceptions.ClientError as e:
            print(f"Failed to create DNS zone: {e}")

def delete_dns_zone():
    """
    Deletes a DNS Hosted Zone from AWS Route 53.
    
    This function lists all Hosted Zones created via the CLI and allows the user to select one for deletion.
    It ensures that only CLI-created zones are deletable and confirms with the user before proceeding.
    If the Hosted Zone contains DNS records, the user is prompted to remove them before deletion.
    
    The function follows best practices by validating user input and preventing accidental deletions.
    """
    route53 = boto3.client('route53')

    # Fetching all zones created via the CLI
    response = route53.list_hosted_zones()
    cli_zones = [
        (zone['Id'].split('/')[-1], zone['Name'])
        for zone in response['HostedZones']
        if is_cli_created_zone(zone['Id'].split('/')[-1], route53)
    ]

    if not cli_zones:
        print("No CLI-created DNS zones found.")
        return

    # Displaying a list of Zones for selection
    print("\nAvailable DNS Zones for Deletion:")
    for idx, (zone_id, zone_name) in enumerate(cli_zones, 1):
        print(f"{idx}. {zone_name} (ID: {zone_id})")

    while True:
        choice = input("\nSelect the DNS Zone number to delete (or 'q' to cancel): ").strip().lower()
        if choice == "q":
            print("Operation cancelled.")
            return
        try:
            choice = int(choice)
            if 1 <= choice <= len(cli_zones):
                selected_zone_id, selected_zone_name = cli_zones[choice - 1]
                break
            else:
                print("Invalid selection. Please choose a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Checking if the Zone contains records other than NS and SOA.
    record_sets = route53.list_resource_record_sets(HostedZoneId=selected_zone_id)['ResourceRecordSets']
    deletable_records = [record for record in record_sets if record['Type'] not in ["NS", "SOA"]]

    if deletable_records:
        print(f"\nThe DNS Zone '{selected_zone_name}' contains additional records that must be deleted before removing the zone.")
        print("You must delete these records first:")
        for record in deletable_records:
            print(f"- {record['Name']} ({record['Type']}) - {record['ResourceRecords'][0]['Value']}")

        confirm_delete_records = input("Do you want to delete all records in this zone? (y/N): ").strip().lower()
        if confirm_delete_records != "y":
            print("Zone deletion cancelled. Please delete the records manually before retrying.")
            return
        
        # Deleting all non-default records.
        for record in deletable_records:
            try:
                route53.change_resource_record_sets(
                    HostedZoneId=selected_zone_id,
                    ChangeBatch={
                        'Changes': [{
                            'Action': 'DELETE',
                            'ResourceRecordSet': record
                        }]
                    }
                )
                print(f"Deleted record: {record['Name']} ({record['Type']})")
            except Exception as e:
                print(f"Failed to delete record {record['Name']}: {e}")
                return

    # Confirmation for deleting the Zone.
    confirm = input(f"Are you sure you want to delete the DNS Zone '{selected_zone_name}'? (y/N): ").strip().lower()
    if confirm != "y":
        print("Zone deletion cancelled.")
        return

    # Deleting the Zone.
    try:
        route53.delete_hosted_zone(Id=selected_zone_id)
        print(f"DNS Zone '{selected_zone_name}' has been deleted successfully.")
    except Exception as e:
        print(f"Failed to delete DNS zone: {e}")

def is_cli_created_zone(zone_id, route53):
    """
    Checks if a DNS Zone (Hosted Zone) was created via the CLI by verifying the presence of a specific tag.

    :param zone_id: The ID of the Hosted Zone to check.
    :param route53: The boto3 client for AWS Route 53.
    :return: True if the zone was created via the CLI (based on the 'CreatedBy' tag), otherwise False.
    """
    try:
        response = route53.list_tags_for_resource(ResourceType='hostedzone', ResourceId=zone_id)
        for tag in response['ResourceTagSet']['Tags']:
            if tag['Key'] == "CreatedBy" and tag['Value'] == OWNER_NAME:
                return True
    except route53.exceptions.ClientError:
        pass
    return False


def manage_dns_record():
    """
    Manages DNS records within a Hosted Zone created via the CLI.
    
    This function allows the user to:
    - View all DNS Zones created through the CLI.
    - Select a specific DNS Zone for management.
    - Choose an action (Create, Update, or Delete a DNS record).
    - Perform the selected action on a specified DNS record.

    The function ensures that only records within CLI-created zones can be modified. 
    The user interacts via a menu system and selects from available options.
    """

    actions = {
        "1": "Create DNS Record",
        "2": "Update DNS Record",
        "3": "Delete DNS Record",
        "4": "Quit"
    }

    while True:
        print("\nChoose a DNS Record Action:")
        for key, value in actions.items():
            print(f"{key}. {value}")

        choice = input("\nEnter your choice (1-4): ").strip()

        if choice == "1":
            create_dns_record()
        elif choice == "2":
            update_dns_record()
        elif choice == "3":
            delete_dns_record()
        elif choice == "4":
            print("Operation cancelled.")
            return
        else:
            print("Invalid choice. Please enter a number between 1 and 4.")

def create_dns_record():
    """
    Creates a new DNS record in a Hosted Zone that was created via the CLI.

    This function:
    - Lists all available DNS zones created through the CLI.
    - Allows the user to select a zone for record creation.
    - Requests input for the record name, type (A, CNAME, MX, TXT, etc.), value, and TTL.
    - Ensures valid input and handles any errors during record creation.
    
    The function only permits record creation within Hosted Zones that have the 
    'CreatedBy' tag set to 'cli-meitaveini', ensuring control over managed records.
    """
    route53 = boto3.client('route53')

    # Retrieving DNS zones created via the CLI
    response = route53.list_hosted_zones()
    cli_zones = [
        (zone['Id'].split('/')[-1], zone['Name'].rstrip('.'))
        for zone in response['HostedZones']
        if is_cli_created_zone(zone['Id'].split('/')[-1], route53)
    ]

    if not cli_zones:
        print("No CLI-created DNS zones found.")
        return

    print("\nAvailable DNS Zones (created via CLI):")
    for idx, (zone_id, zone_name) in enumerate(cli_zones, 1):
        print(f"{idx}. {zone_name} (ID: {zone_id})")

    # Choosing DNS zone
    while True:
        choice = input("\nSelect the DNS Zone number (or 'q' to cancel): ").strip().lower()
        if choice == "q":
            print("Operation cancelled.")
            return
        try:
            choice = int(choice)
            if 1 <= choice <= len(cli_zones):
                selected_zone_id, selected_zone_name = cli_zones[choice - 1]
                break
            else:
                print("Invalid selection. Please choose a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Receiving the record name and validating its correctness.
    while True:
        record_name = input(f"Enter the record name (subdomain for {selected_zone_name}, or leave empty for root): ").strip().lower()
        
        if not record_name:
            record_name = selected_zone_name  # If empty, use the main domain name.
            break
        elif record_name.endswith(selected_zone_name):
            break  # The name is valid
        elif "." not in record_name:
            record_name = f"{record_name}.{selected_zone_name}"  # Adding the main domain if the user entered only a subdomain.
            break
        else:
            print(f"Invalid record name. It must be within '{selected_zone_name}'.")

    valid_record_types = {"A", "AAAA", "CNAME", "MX", "TXT", "SRV", "NS", "PTR", "SOA"} # The records type

    while True:
        record_type = input("Enter the record type (A, CNAME, MX, TXT, etc.) or 'q' to cancel: ").strip().upper()
        if record_type == "Q":
            print("Operation cancelled.")
            return
        if record_type in valid_record_types:
            break
        print(f"Invalid record type. Supported types: {', '.join(valid_record_types)}")


    while True:
        record_value = input("Enter the record value: ").strip()
        if record_value:
            if record_type == "TXT" and not (record_value.startswith('"') and record_value.endswith('"')):
                record_value = f'"{record_value}"'  # Adding quotation marks in case of a TXT record.
            break
        else:
            print("Record value cannot be empty. Please enter a value.")

    ttl = input("Enter the TTL (Time To Live) in seconds (default 300): ").strip()
    ttl = int(ttl) if ttl.isdigit() else 300  # Default to 300 if the user does not provide a TTL.

    change_batch = {
        'Changes': [{
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'Name': record_name,
                'Type': record_type,
                'TTL': ttl,
                'ResourceRecords': [{'Value': record_value}]
            }
        }]
    }

    try:
        route53.change_resource_record_sets(HostedZoneId=selected_zone_id, ChangeBatch=change_batch)
        print(f"DNS record '{record_name}' ({record_type}) has been created successfully in zone {selected_zone_name}.")
    except Exception as e:
        print(f"Failed to create DNS record: {e}")


def update_dns_record():
    """
    Updates an existing DNS record in a Hosted Zone that was created via the CLI.

    This function:
    - Retrieves all Hosted Zones created through the CLI.
    - Allows the user to select a zone from a numbered list.
    - Lists all existing DNS records within the selected zone.
    - Prompts the user to select a record to update.
    - Requests new values for the record (name, type, value, and TTL).
    - Maintains existing values if no new input is provided.
    - Ensures the update process follows AWS Route 53 constraints.

    The function ensures that only records within CLI-created zones 
    (identified by the 'CreatedBy' tag) can be modified.
    """
    route53 = boto3.client('route53')

    # Retrieving all Hosted Zones that were created via the CLI.
    response = route53.list_hosted_zones()
    cli_zones = [
        (zone['Id'].split('/')[-1], zone['Name'])
        for zone in response['HostedZones']
        if is_cli_created_zone(zone['Id'].split('/')[-1], route53)
    ]

    if not cli_zones:
        print("No DNS zones created via CLI were found.")
        return

    print("\nAvailable DNS Zones (created via CLI):")
    for idx, (zone_id, zone_name) in enumerate(cli_zones, 1):
        print(f"{idx}. {zone_name} (ID: {zone_id})")

    # Retrieving the user's selection.
    while True:
        choice = input("\nSelect the DNS Zone number (or 'q' to cancel): ").strip()
        if choice.lower() == "q":
            print("Operation cancelled.")
            return
        if choice.isdigit() and 1 <= int(choice) <= len(cli_zones):
            zone_id, zone_name = cli_zones[int(choice) - 1]
            break
        print("Invalid choice. Please enter a valid number.")

    # Retrieving existing DNS records.
    try:
        record_sets = route53.list_resource_record_sets(HostedZoneId=zone_id)['ResourceRecordSets']
    except Exception as e:
        print(f"Failed to retrieve DNS records: {e}")
        return

    if not record_sets:
        print("No DNS records found in the selected zone.")
        return

    print("\nAvailable DNS Records:")
    for idx, record in enumerate(record_sets, 1):
        print(f"{idx}. {record['Name']} ({record['Type']}) - Value: {record['ResourceRecords'][0]['Value']} - TTL: {record['TTL']}")

    # Selecting a record for update.
    while True:
        record_choice = input("\nSelect the record number to update (or 'q' to cancel): ").strip()
        if record_choice.lower() == "q":
            print("Operation cancelled.")
            return
        if record_choice.isdigit() and 1 <= int(record_choice) <= len(record_sets):
            selected_record = record_sets[int(record_choice) - 1]
            break
        print("Invalid choice. Please enter a valid number.")

    record_name = selected_record['Name']
    record_type = selected_record['Type']
    old_value = selected_record['ResourceRecords'][0]['Value']
    old_ttl = selected_record['TTL']

    print(f"\nUpdating Record: {record_name} ({record_type})")
    print(f"Current Value: {old_value}")
    print(f"Current TTL: {old_ttl}")

    # Receiving a new value.
    new_value = input("\nEnter the new record value (or press Enter to keep the current value): ").strip()
    if not new_value:
        new_value = old_value  # Preserving the existing value if the user does not enter a new one.

    # Receiving a new TTL.
    new_ttl = input(f"Enter the new TTL in seconds (default {old_ttl}): ").strip()
    new_ttl = int(new_ttl) if new_ttl.isdigit() else old_ttl  # Preserving the existing TTL if the user does not enter a new value.

    # Updating the DNS record.
    change_batch = {
        'Changes': [{
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'Name': record_name,
                'Type': record_type,
                'TTL': new_ttl,
                'ResourceRecords': [{'Value': new_value}]
            }
        }]
    }

    try:
        route53.change_resource_record_sets(HostedZoneId=zone_id, ChangeBatch=change_batch)
        print(f"DNS record '{record_name}' ({record_type}) updated successfully in zone {zone_name}.")
    except Exception as e:
        print(f"Failed to update DNS record: {e}")


def delete_dns_record():
    """
    Deletes a DNS record from a Hosted Zone that was created via the CLI.

    This function:
    - Lists all available DNS zones created through the CLI.
    - Allows the user to select a zone for record deletion.
    - Retrieves all DNS records from the selected zone, filtering out non-deletable ones (NS, SOA).
    - Displays the available records and lets the user choose which one to delete.
    - Requests confirmation before deleting the selected record.
    - Executes the deletion and provides feedback on success or failure.
    
    The function ensures that only DNS records within CLI-managed Hosted Zones (tagged with 
    'CreatedBy=cli-meitaveini') can be deleted, preventing unintended modifications.
    """
    route53 = boto3.client('route53')

    # Retrieving all Hosted Zones created via the CLI.
    response = route53.list_hosted_zones()
    cli_zones = [
        (zone['Id'].split('/')[-1], zone['Name'])
        for zone in response['HostedZones']
        if is_cli_created_zone(zone['Id'].split('/')[-1], route53)
    ]

    if not cli_zones:
        print("No DNS zones created via CLI were found.")
        return

    print("\nAvailable DNS Zones (created via CLI):")
    for idx, (zone_id, zone_name) in enumerate(cli_zones, 1):
        print(f"{idx}. {zone_name} (ID: {zone_id})")

    while True:
        choice = input("\nSelect the DNS Zone number to delete a record from (or 'q' to cancel): ").strip().lower()
        if choice == "q":
            print("Operation cancelled.")
            return
        try:
            choice = int(choice)
            if 1 <= choice <= len(cli_zones):
                selected_zone_id, selected_zone_name = cli_zones[choice - 1]
                break
            else:
                print("Invalid selection. Please choose a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Retrieving existing DNS records.
    try:
        record_sets = route53.list_resource_record_sets(HostedZoneId=zone_id)['ResourceRecordSets']
    except Exception as e:
        print(f"Failed to retrieve DNS records: {e}")
        return

    if not record_sets:
        print("No DNS records found in the selected zone.")
        return

    print("\nAvailable DNS Records for Deletion:")
    deletable_records = [
        record for record in record_sets
        if record['Type'] not in ["NS", "SOA"]  # Filtering records that cannot be deleted.
    ]

    if not deletable_records:
        print("No deletable DNS records found in this zone.")
        return

    for idx, record in enumerate(deletable_records, 1):
        print(f"{idx}. {record['Name']} ({record['Type']}) - Value: {record['ResourceRecords'][0]['Value']} - TTL: {record['TTL']}")

    while True:
        record_choice = input("\nSelect the record number to delete (or 'q' to cancel): ").strip().lower()
        if record_choice == "q":
            print("Operation cancelled.")
            return
        try:
            record_choice = int(record_choice)
            if 1 <= record_choice <= len(deletable_records):
                selected_record = deletable_records[record_choice - 1]
                break
            else:
                print("Invalid selection. Please choose a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")


    record_name = selected_record['Name']
    record_type = selected_record['Type']
    record_value = selected_record['ResourceRecords'][0]['Value']
    ttl = selected_record['TTL']

    print(f"\nDeleting Record: {record_name} ({record_type})")
    print(f"Value: {record_value}")
    print(f"TTL: {ttl}")

    # Requesting confirmation for deletion.
    confirm = input(f"\nAre you sure you want to delete this record? (y/N): ").strip().lower()

    if confirm != "y":
        print("Operation cancelled.")
        return

    # Performing deletion.
    change_batch = {
        'Changes': [{
            'Action': 'DELETE',
            'ResourceRecordSet': {
                'Name': record_name,
                'Type': record_type,
                'TTL': ttl,
                'ResourceRecords': [{'Value': record_value}]
            }
        }]
    }

    try:
        route53.change_resource_record_sets(HostedZoneId=zone_id, ChangeBatch=change_batch)
        print(f"DNS record '{record_name}' ({record_type}) deleted successfully from zone {zone_name}.")
    except Exception as e:
        print(f"Failed to delete DNS record: {e}")


def list_all_dns_zones():
    """
    Lists all Hosted Zones created via the CLI in AWS Route 53.

    This function:
    - Retrieves all Hosted Zones from Route 53.
    - Filters the list to only include zones that were created via the CLI 
      (i.e., those tagged with 'CreatedBy=cli-meitaveini').
    - Displays the available Hosted Zones with their names and corresponding IDs.
    
    The function ensures that only CLI-managed zones are shown, maintaining clear visibility 
    of resources under the tool's control.
    """
    route53 = boto3.client('route53')

    try:
        # Retrieving all zones from Route 53.
        response = route53.list_hosted_zones()
        hosted_zones = response.get('HostedZones', [])

        if not hosted_zones:
            print("No DNS zones found in Route 53.")
            return

        print("\nList of all DNS Zones in Route 53:")
        print(f"{'Index':<6} {'Domain Name':<30} {'Zone ID':<25} {'CLI Created':<12}")
        print("=" * 80)

        for idx, zone in enumerate(hosted_zones, 1):
            zone_id = zone['Id'].split('/')[-1]
            zone_name = zone['Name']
            is_cli_created = "V" if is_cli_created_zone(zone_id, route53) else "X"

            print(f"{idx:<6} {zone_name:<30} {zone_id:<25} {is_cli_created:<12}")

    except Exception as e:
        print(f"Failed to retrieve DNS zones: {e}")

def is_cli_created_zone(zone_id, route53):
    """
    Checks if a Hosted Zone was created via the CLI.

    This function:
    - Retrieves tags associated with the given Hosted Zone.
    - Verifies whether the 'CreatedBy' tag is set to 'cli-meitaveini'.
    - Returns True if the Hosted Zone was created via the CLI, otherwise returns False.

    This ensures that only Hosted Zones managed through the CLI can be modified 
    or deleted, preventing unintended changes to externally managed zones.
    """
    try:
        response = route53.list_tags_for_resource(ResourceType='hostedzone', ResourceId=zone_id)
        for tag in response['ResourceTagSet']['Tags']:
            if tag['Key'] == "CreatedBy" and tag['Value'] == OWNER_NAME:
                return True
    except route53.exceptions.ClientError:
        pass
    return False


def list_all_dns_records():
    """
    Lists all DNS records in a Hosted Zone created via the CLI.

    This function:
    - Retrieves all Hosted Zones created through the CLI (tagged with 'CreatedBy=cli-meitaveini').
    - Allows the user to select a specific Hosted Zone to view its DNS records.
    - Fetches and displays all records within the selected Hosted Zone, including 
      their names, types (A, CNAME, MX, TXT, etc.), values, and TTL.

    The function ensures that only DNS records from CLI-managed Hosted Zones are shown, 
    maintaining controlled visibility over managed records.
    """


    route53 = boto3.client('route53')

    # Retrieving all DNS Zones created via the CLI.
    response = route53.list_hosted_zones()
    cli_zones = [
        (zone['Id'].split('/')[-1], zone['Name'])
        for zone in response['HostedZones']
        if is_cli_created_zone(zone['Id'].split('/')[-1], route53)
    ]

    if not cli_zones:
        print("No CLI-created DNS zones found.")
        return

    print("\nAvailable DNS Zones (created via CLI):")
    for idx, (zone_id, zone_name) in enumerate(cli_zones, 1):
        print(f"{idx}. {zone_name} (ID: {zone_id})")

    # Selecting a DNS zone to display its DNS records.
    while True:
        try:
            choice = input("\nEnter the number of the DNS zone to list records (or 'q' to quit): ").strip().lower()
            if choice == "q":
                print("Operation cancelled.")
                return

            choice = int(choice)
            if 1 <= choice <= len(cli_zones):
                selected_zone_id = cli_zones[choice - 1][0]
                break
            else:
                print("Invalid selection. Please choose a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    try:
        # Retrieving all records in the selected DNS zone.
        response = route53.list_resource_record_sets(HostedZoneId=selected_zone_id)
        records = response.get('ResourceRecordSets', [])

        if not records:
            print(f"No DNS records found in the selected zone.")
            return

        print(f"\nDNS Records for Zone ID {selected_zone_id}:")
        print(f"{'Index':<6} {'Record Name':<30} {'Type':<10} {'TTL':<6} {'Value'}")
        print("=" * 80)

        for idx, record in enumerate(records, 1):
            record_name = record['Name']
            record_type = record['Type']
            ttl = record.get('TTL', 'N/A')
            values = ', '.join([r['Value'] for r in record.get('ResourceRecords', [])])

            print(f"{idx:<6} {record_name:<30} {record_type:<10} {ttl:<6} {values}")

    except Exception as e:
        print(f"Failed to retrieve DNS records: {e}")

def is_cli_created_zone(zone_id, route53):
    """
    Checks if a Hosted Zone was created via the CLI.

    This function:
    - Retrieves tags associated with the given Hosted Zone.
    - Verifies whether the 'CreatedBy' tag is set to 'cli-meitaveini'.
    - Returns True if the Hosted Zone was created via the CLI, otherwise returns False.

    This ensures that only Hosted Zones managed through the CLI can be modified 
    or deleted, preventing unintended changes to externally managed zones.
    """

    try:
        response = route53.list_tags_for_resource(ResourceType='hostedzone', ResourceId=zone_id)
        for tag in response['ResourceTagSet']['Tags']:
            if tag['Key'] == "CreatedBy" and tag['Value'] == OWNER_NAME:
                return True
    except route53.exceptions.ClientError:
        pass
    return False


def main():
    """
    AWS Resource Management CLI Entry Point.

    This function:
    - Displays a menu allowing users to choose between managing EC2 instances, 
      S3 buckets, or Route 53 DNS records.
    - Calls the corresponding main function (ec2_main, s3_main, or route53_main) 
      based on the user's choice.
    - Provides an option to exit the program.

    The CLI ensures that each AWS resource is managed through predefined actions, 
    maintaining security and consistency in operations.
    """

    ACTION_MAP = {
        "1": create_dns_zone,
        "2": delete_dns_zone,
        "3": manage_dns_record,
        "4": list_all_dns_zones,
        "5": list_all_dns_records
    }

    while True:  # Loop until the user enters a valid value.
        user_action_choice = input(
"""\nBefore we start, tell me what you want to do with Route53:
1. Create dns zone 
2. Delete dns zone
3. Manage dns record (create, update, or delete)
4. List all dns zones
5. List all dns records
\nEnter your choice (1-5): """)

        if user_action_choice in ACTION_MAP:
            ACTION_MAP[user_action_choice]()  # Call the appropriate function.
            break  # Exit the loop after performing the action.
        else:
            print("Invalid choice. Please enter a number between 1 and 5.")

if __name__ == "__main__":
    main()
