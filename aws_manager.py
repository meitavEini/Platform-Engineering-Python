import sys
from resources.ec2 import main as ec2_main
from resources.s3 import main as s3_main
from resources.route53 import main as route53_main

def main():
    """The main() function serves as the entry point for the AWS Resource Management CLI.
    It presents users with a menu of options to manage AWS resources, including EC2 instances, S3 buckets,
    and Route 53 DNS records. Based on the user's input, the function calls the appropriate submodule (ec2_main(),
    s3_main(), or route53_main()). If the user selects "Exit," the program terminates. In case of an invalid input,
    an error message is displayed, prompting the user to enter a valid option.
    """
    print("\nAWS Resource Management CLI")
    print("1. Manage EC2 Instances")
    print("2. Manage S3 Buckets")
    print("3. Manage Route 53 DNS Records")
    print("4. Exit")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice == "1":
        ec2_main()
    elif choice == "2":
        s3_main()
    elif choice == "3":
        route53_main()
    elif choice == "4":
        sys.exit()
    else:
        print("Invalid choice. Please enter a number between 1 and 4.")

if __name__ == "__main__":
    main()
    print("Exiting CLI. Goodbye!")