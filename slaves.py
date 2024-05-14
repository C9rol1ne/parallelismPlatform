import socket
import tqdm
import os

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
SERVER_HOST = socket.gethostbyname(socket.gethostname())
SERVER_PORT = 5050

# Connect to the server
client_socket.connect((SERVER_HOST, SERVER_PORT))

# Send "READY" command
client_socket.send("READY".encode())

# Receive file name and size
file_info = client_socket.recv(1024).decode().split('\n')
file_name, file_size = file_info[0], int(file_info[1])

# Receive file data
with open("receivedImageFromServer.jpg", "wb") as file:
    progress = tqdm.tqdm(range(file_size), f"Receiving {file_name}", unit="B", unit_scale=True)
    received_bytes = 0
    while received_bytes < file_size:
        data = client_socket.recv(1024)
        file.write(data)
        received_bytes += len(data)
        progress.update(len(data))
    progress.close()

print("[+] Image received successfully.")

# Send "DONE" command
client_socket.send("DONE".encode())

print("[*] Sent DONE command to server.")

# Send image to server
file_name = "lievitoMadre.jpg"
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

print("[+] Image sent to server successfully.")

# Close the connection
client_socket.close()
