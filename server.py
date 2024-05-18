import socket
import tqdm
import os

# Device's IP address and port
SERVER_HOST = socket.gethostbyname(socket.gethostname())
SERVER_PORT = 5050

# Create the server TCP socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind the socket to our local address
server.bind((SERVER_HOST, SERVER_PORT))

# Put server in listening mode
server.listen()

print(f"[*] Listening as {SERVER_HOST}:{SERVER_PORT}")

while True:
    # Accept connections from clients
    client_socket, client_address = server.accept()

    # Define protocol
    response = client_socket.recv(1024).decode()

    if response == "READY":
        # Send image to client

        file_name = "spongebob.jpg"
        file_size = os.path.getsize(file_name)

        # Send file name and size
        client_socket.send(f"{file_name}\n{file_size}".encode())

        # Send file data in chunks
        with open(file_name, "rb") as file:
            while True:
                data = file.read(1024)
                if not data:
                    break
                client_socket.sendall(data)

        print("[+] Image sent successfully.")

    # Receive "DONE" command
    done_command = client_socket.recv(1024).decode()
    if done_command == "DONE":
        print("[*] Client has sent DONE command.")

        # Receive image from client
        file_name, file_size = client_socket.recv(1024).decode().split('\n')
        file_size = int(file_size)

        with open('receivedImageFromClient.jpg', "wb") as file:
            progress = tqdm.tqdm(range(file_size), f"Receiving {file_name}", unit="B", unit_scale=True)
            received_bytes = 0
            while received_bytes < file_size:
                data = client_socket.recv(1024)
                file.write(data)
                received_bytes += len(data)
                progress.update(len(data))
            progress.close()

        print("[+] Image received and saved successfully.")

    # Close the connection

    server_response = "STAY" # Change depending on the logic   
    client_socket.sendall(server_response.encode())

    if server_response == "STAY":
        pass
        # Add code for further communication if needed
    else:
        client_socket.close()

server.close()