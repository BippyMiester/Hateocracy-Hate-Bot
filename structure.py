import os

def print_directory_structure(startpath):
    """Prints the directory structure starting from the given path."""
    for root, dirs, files in os.walk(startpath):
        # Filter out unwanted directories
        dirs[:] = [d for d in dirs if d not in {'.venv', '__pycache__'}]

        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * level
        print(f'{indent}{os.path.basename(root)}/')

        subindent = ' ' * 4 * (level + 1)

        # Exclude files in specific directories but include directories themselves
        if 'logs' not in root and not root.endswith(os.path.join('data', 'videos', 'meta')) and not root.endswith(os.path.join('data', 'subscriptions')):
            for f in files:
                print(f'{subindent}{f}')

# Get the current working directory
current_directory = os.getcwd()

# Print the structure of the current directory
print_directory_structure(current_directory)