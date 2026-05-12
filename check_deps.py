import pkg_resources
import sys

def check_requirements(req_file):
    with open(req_file, 'r') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    missing = []
    for req in requirements:
        try:
            pkg_resources.require(req)
        except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict):
            missing.append(req)
    
    return missing

if __name__ == "__main__":
    missing_packages = check_requirements('requirements.txt')
    if missing_packages:
        print("Missing requirements:")
        for pkg in missing_packages:
            print(f"- {pkg}")
    else:
        print("All requirements are met.")
