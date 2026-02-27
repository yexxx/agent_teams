#!/usr/bin/env python3
"""
Simple echo program that outputs a simple message.
This is a standalone script that demonstrates basic echo functionality.
"""

def echo(message: str = "Hello, World!") -> None:
    """
    Echo function that prints a message to stdout.
    
    Args:
        message (str): The message to echo. Defaults to "Hello, World!".
    """
    print(message)


if __name__ == "__main__":
    # Allow command line arguments to override the default message
    import sys
    
    if len(sys.argv) > 1:
        # Join all arguments as the message
        message = " ".join(sys.argv[1:])
    else:
        message = "Hello, World!"
    
    echo(message)