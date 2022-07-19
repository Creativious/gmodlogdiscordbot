import os

if not os.path.exists("/sensitive"): # If the path for the sensitive files doesn't exist then create it
    os.mkdir("/sensitive")


if not os.path.exists("/sensitive/token.txt"): # Ensuring the file for tokens exists, setup so github can't see it.
    with open("/sensitive/token.txt", "w+") as f:
        f.write("TOKENGOESHERE")