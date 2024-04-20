def get_file_contents(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    return content