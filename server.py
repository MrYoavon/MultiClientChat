import socket
import threading
import queue
import datetime

# Server configuration
SERVER_HOST = '127.0.0.1'  # Host address
SERVER_PORT = 54321        # Port number
BUFFER_SIZE = 1024         # Buffer size for receiving messages

# Data structures
managers = ['admin1', 'admin2', 'admin3']  # List of manager usernames
muted_users = set()                        # Store muted usernames
socket_to_username = {}                    # Map client sockets to usernames
socket_to_address = {}                     # Map client sockets to addresses
client_queues = {}                         # Map client sockets to their respective message queues


def get_current_time():
    """Get the current time formatted as HH:MM."""
    return datetime.datetime.now().strftime("%H:%M")

def does_user_exist(username):
    """Check if the username exists in the connected clients."""
    return username in socket_to_username.values()

def send_message(client_socket, message):
    """Sends a message to the specified client socket."""
    try:
        message_len = str(len(message)).zfill(3)  # Prepend the length of the message
        message = message_len + message           # Add length prefix
        client_socket.send(message.encode())
    except Exception:
        remove_client(client_socket)              # Remove client on failure


def remove_client(client_socket):
    """Removes a client from the server."""
    if client_socket in socket_to_address:
        username = socket_to_username.pop(client_socket, None)
        if username and username in muted_users:
            muted_users.remove(username)

        client_address = socket_to_address.pop(client_socket, "Unknown")
        client_queues.pop(client_socket, None)
        print(f"Client disconnected: {client_address}")
        try:
            client_socket.close()
        except Exception:
            print("Client couldn't be closed")


def broadcast_message(message, sender_socket=None, is_system_message=False):
    """Broadcast message to all clients except the sender.

    If `is_system_message` is True, broadcast to everyone (even muted users).
    """
    for client_socket in socket_to_address:
        # Only exclude the sender if this is not a system message.
        if client_socket != sender_socket or is_system_message:
            client_queues[client_socket].put(message)


def send_private_message(private_message, recipient, sender_socket):
    """Send a private message to a specific recipient."""
    if not does_user_exist(recipient):
        message = f"User {recipient} does not exist."
        send_message(sender_socket, message)
        return

    recipient_socket = None
    for client_socket, username in socket_to_username.items():
        if username == recipient:
            recipient_socket = client_socket
            break

    if recipient_socket:
        message_to_send = f"{get_current_time()} !{socket_to_username[sender_socket]}: {private_message}"
        client_queues[recipient_socket].put(message_to_send)
    else:
        send_message(sender_socket, f"{get_current_time()} User {recipient} not found.")


def promote_user(promoting_username, user_to_promote):
    """Promote a user to manager."""
    if not does_user_exist(user_to_promote):
        message = f"User {user_to_promote} doesn't exist."
        send_message(client_socket_by_username(promoting_username), message)
        return

    if promoting_username not in managers:
        message = f"{get_current_time()} Only managers can promote other users!"
        send_message(client_socket_by_username(promoting_username), message)
        return

    if user_to_promote not in managers:
        managers.append(user_to_promote)
        message = f"{get_current_time()} {user_to_promote} has been promoted to manager."
        broadcast_message(message)
    else:
        message = f"{get_current_time()} @{user_to_promote} is already a manager."
        send_message(client_socket_by_username(promoting_username), message)


def kick_user(kicking_username, user_to_kick):
    """Kick a user from the chat."""
    if not does_user_exist(user_to_kick):
        message = f"User {user_to_kick} doesn't exist."
        send_message(client_socket_by_username(kicking_username), message)
        return

    if kicking_username not in managers:
        message = f"{get_current_time()} Only managers can kick other users!"
        send_message(client_socket_by_username(kicking_username), message)
        return

    socket_to_kick = client_socket_by_username(user_to_kick)
    if socket_to_kick:
        send_message(socket_to_kick, "KICKED")  # Notify kicked user
        remove_client(socket_to_kick)  # Remove the kicked user

        message = f"{get_current_time()} {user_to_kick} has been kicked from the chat!"
        broadcast_message(message)
    else:
        message = f"{get_current_time()} {user_to_kick} is not connected to the chat."
        send_message(client_socket_by_username(kicking_username), message)


def mute_user(muting_username, user_to_mute):
    """Mute a user so they cannot send messages."""
    if not does_user_exist(user_to_mute):
        message = f"User {user_to_mute} doesn't exist."
        send_message(client_socket_by_username(muting_username), message)
        return

    if muting_username not in managers:
        message = f"{get_current_time()} Only managers can mute other users!"
        send_message(client_socket_by_username(muting_username), message)
        return

    if user_to_mute not in muted_users:
        muted_users.add(user_to_mute)
        muting_message = f"{get_current_time()} {user_to_mute} has been muted."
        muted_message = f"{get_current_time()} You have been muted by {muting_username}."
        send_message(client_socket_by_username(muting_username), muting_message)
        send_message(client_socket_by_username(user_to_mute), muted_message)

    else:
        message = f"{get_current_time()} {user_to_mute} is already muted."
        send_message(client_socket_by_username(muting_username), message)


def client_socket_by_username(username):
    """Retrieve the client socket by username."""
    for socket, user in socket_to_username.items():
        if user == username:
            return socket
    return None


def unpack_message(message):
    """Unpack the received message from the client."""
    try:
        username_length = int(message[:2].decode())
        username = message[2:2 + username_length].decode()
        command = message[2 + username_length:2 + username_length + 1].decode()
        message_length = int(message[2 + username_length + 1:2 + username_length + 4].decode())
        content = message[2 + username_length + 4:2 + username_length + 4 + message_length].decode()
        return username, command, content
    except (ValueError, IndexError):
        return None, None, None


def handle_commands(username, command, content, client_socket, exit_event):
    """Handle various commands from clients."""
    if command == "2":  # Promote user
        promote_user(username, content.strip())

    elif command == "3":  # Kick user
        kick_user(username, content.strip())

    elif command == "4":  # Mute user
        mute_user(username, content.strip())

    elif command == "5":  # Private message
        recipient, private_message = content.split(maxsplit=1)
        send_private_message(private_message, recipient, client_socket)

    elif command == "6":  # Handle quit command
        username = socket_to_username.get(client_socket, None)
        if username:
            message = f"{get_current_time()} {username} has left the chat!"
            broadcast_message(message)
        exit_event.set()
        remove_client(client_socket)

    else:  # Regular message
        if username in muted_users:
            send_message(client_socket, f"{get_current_time()} You are muted and cannot send messages.")
        else:
            if content.strip() == "view-managers":
                message = f"Managers List\n-------------\n"
                for manager in managers:
                    message += (manager + "\n")
                send_message(client_socket, message)
            else:
                is_manager = username in managers
                if is_manager:
                    username = '@' + username

                message_to_send = f"{get_current_time()} {username}: {content}"
                broadcast_message(message_to_send, client_socket)


def handle_client(client_socket, exit_event):
    """Handle communication with a single client."""
    while not exit_event.is_set():
        try:
            message = client_socket.recv(BUFFER_SIZE)
            if not message:
                remove_client(client_socket)
                break

            username, command, content = unpack_message(message)
            if username:
                socket_to_username[client_socket] = username
                handle_commands(username, command, content, client_socket, exit_event)

        except Exception as e:
            exit_event.set()
            remove_client(client_socket)
            break

    remove_client(client_socket)  # Clean up on exit


def client_sender(client_socket, exit_event):
    """Send messages from the client's queue."""
    while not exit_event.is_set():
        try:
            message = client_queues.get(client_socket).get(timeout=1)
            send_message(client_socket, message)
        except queue.Empty:
            continue  # Continue looping until exit_event is set


def start_server():
    """Start the server and handle incoming clients."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((SERVER_HOST, SERVER_PORT))
    server_socket.listen()

    print(f"Server started on {SERVER_HOST}:{SERVER_PORT}")

    while True:
        client_socket, client_address = server_socket.accept()
        print(f"New connection: {client_address}")

        client_queues[client_socket] = queue.Queue()  # Initialize queue for the new client
        socket_to_address[client_socket] = client_address

        exit_event = threading.Event()  # Create an exit event for each client
        threading.Thread(target=handle_client, args=(client_socket, exit_event)).start()
        threading.Thread(target=client_sender, args=(client_socket, exit_event)).start()


if __name__ == "__main__":
    start_server()
