import socket
import threading
import msvcrt  # For non-blocking input handling
import sys

# Client configuration
SERVER_HOST = '127.0.0.1'  # Server address
SERVER_PORT = 54321        # Port number
BUFFER_SIZE = 1024         # Buffer size for receiving messages
COMMANDS = {
    "chat": "1",
    "promote": "2",
    "kick": "3",
    "mute": "4",
    "msg": "5",
    "quit": "6",
}
exit_event = threading.Event()  # Event to signal threads to exit

# Username prompt
username = input("Enter your username (99 characters maximum, no spaces or '@'): ")

# Ensure username does not start with '@' or contain spaces
while username.startswith('@') or ' ' in username:
    print("Username must not start with '@' and must not contain spaces.")
    username = input("Enter your username (99 characters maximum, no spaces or '@'): ")


def show_help():
    """Prints the available commands for the user."""
    help_text = """
Available commands:
/promote username     Promote a user to manager
/kick username        Remove a user from the chat
/mute username        Prevent a user from sending messages
/msg username message Send a private message to a user
/quit                 Exit the chat application
"""
    print(help_text)


def send_message(server_socket):
    """Send messages based on command input."""
    user_input = ""

    print("\nType /help for available commands.")

    while not exit_event.is_set():
        if msvcrt.kbhit():
            char = msvcrt.getch().decode('utf-8')  # Non-blocking input
            if char == '\r':  # Enter key pressed
                if user_input.lower() == "/quit":  # User wants to quit
                    print("\nExiting chat...")
                    message = pack_message(username, COMMANDS["quit"], user_input)
                    server_socket.send(message)
                    server_socket.close()
                    sys.exit()

                if user_input.lower() == "/help":  # User requests help
                    show_help()
                    user_input = ""  # Reset input buffer after displaying help
                    print("\n> ", end='', flush=True)
                    continue

                # Process commands
                if user_input.startswith('/'):
                    parts = user_input.split(' ', 2)  # Split into command and arguments
                    command = parts[0].lower()  # The command part (e.g., /promote)
                    if len(parts) > 1:
                        target_user = parts[1]  # First argument (e.g., username)
                    else:
                        target_user = None

                    if command == "/promote" and target_user:
                        message = pack_message(username, COMMANDS["promote"], target_user)
                        server_socket.send(message)
                    elif command == "/kick" and target_user:
                        message = pack_message(username, COMMANDS["kick"], target_user)
                        server_socket.send(message)
                    elif command == "/mute" and target_user:
                        message = pack_message(username, COMMANDS["mute"], target_user)
                        server_socket.send(message)
                    elif command == "/msg" and len(parts) > 2:
                        private_message = parts[2]  # Second argument (the actual message)
                        message = pack_message(username, COMMANDS["msg"], f"{target_user} {private_message}")
                        server_socket.send(message)
                    else:
                        print(f"Invalid command or missing username: {user_input}")
                else:
                    # Assume it's a regular message if no command
                    message = pack_message(username, COMMANDS["chat"], user_input)
                    server_socket.send(message)

                user_input = ""  # Clear the input after processing
                print("\n> ", end='', flush=True)  # Reset the prompt

            elif char == '\b':  # Handle backspace
                if user_input:
                    user_input = user_input[:-1]  # Remove last character from input buffer
                    print(f"\r> {user_input} ", end='', flush=True)
            else:
                user_input += char  # Append the typed character
                print(f"\r> {user_input}", end='', flush=True)

    server_socket.close()
    sys.exit()


def pack_message(username, command, content):
    """Pack the message to send to the server."""
    username = username.encode()
    content = content.encode()
    username_length = f"{len(username):02}".encode()  # Username length (2 characters)
    message_length = f"{len(content):03}".encode()  # Message length (3 characters)
    return username_length + username + command.encode() + message_length + content


def receive_messages(sock):
    """Receive messages from the server and display them."""
    while not exit_event.is_set():
        try:
            message = sock.recv(BUFFER_SIZE).decode()
            if message:
                if message[3:] == "KICKED":
                    print("You have been kicked from the chat.")
                    exit_event.set()  # Signal to exit

                else:
                    print(f"\r{message[3:]}\n> ", end='', flush=True)
            else:
                sock.close()
                break  # Server closed the connection
        except OSError:
            break

    sock.close()
    sys.exit()


def start_client():
    """Start the client, handle sending and receiving messages."""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((SERVER_HOST, SERVER_PORT))

        # Create threads for sending and receiving messages
        receive_thread = threading.Thread(target=receive_messages, args=(client_socket,))
        send_thread = threading.Thread(target=send_message, args=(client_socket,))

        receive_thread.start()
        send_thread.start()

        # Join the threads to wait for their completion
        receive_thread.join()
        send_thread.join()

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    start_client()
