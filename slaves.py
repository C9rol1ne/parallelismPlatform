import socket # For TCP communication
import tqdm # Progress bars
import os   
import cv2 # Lib for image processing

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
SERVER_HOST = "192.168.1.29" # socket.gethostbyname(socket.gethostname())
SERVER_PORT = 5051

# Connect to the server
client_socket.connect((SERVER_HOST, SERVER_PORT))

# Send "READY" command
client_socket.send("READY".encode())

socket_index = 1
socket_address = client_socket.getsockname()[socket_index]

print(f"Socket address: {socket_address}")

# Receive file name and size
size_bytes = client_socket.recv(4)
file_size = int.from_bytes(size_bytes, byteorder='big')
print("file size is:", file_size)

input_file_name = f"recv{socket_address}.jpg"

# Receive file data
with open(input_file_name, "wb") as file:
    received_bytes = 0
    while received_bytes < file_size:
        data = client_socket.recv(1024)
        file.write(data)
        received_bytes += len(data)

print("[+] Image received successfully.")

# Check received image
if not os.path.exists(file_name) or os.path.getsize(file_name)==0:

    print(f"Error: The file {file_name} does not exist or is empty.")

else:
    # Send "DONE" command
    client_socket.send("DONE".encode())
    print("[*] Sent DONE command to server.")

    # Process image
    image = cv2.imread(file_name,cv2.IMREAD_COLOR)
    print(f"Image shape: {image.shape}")
    image = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(image,100,200)
    processed_file_path = "processedImage.jpg"
    cv2.imwrite(processed_file_path, edges)

    # Send image to server
    file_name = processed_file_path
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

# Close the connection given server response.
server_response = client_socket.recv(1024).decode()
print(f'SERVER RESPONSE: {server_response}')
if server_response == "STAY":
    print("[+] Server asks client to stay")
    # Add code for further communication with the server (optional)
else:
    print("[+] Client killed by server")
    client_socket.close()
