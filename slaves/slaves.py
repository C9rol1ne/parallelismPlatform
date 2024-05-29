import socket # For TCP communication
import tqdm # Progress bars
import os   
import cv2 # Lib for image processing

def send_content_with_length(socket, data):
    if isinstance(data, str):
        data = data.encode()

    data_size = len(data)
    data_size_bytes = data_size.to_bytes(4, byteorder='big')
    socket.sendall(data_size_bytes)
    socket.sendall(data)

def receive_content_by_length(socket):
    # Read exactly 4 bytes to get the length
    content_length_bytes = socket.recv(4)
    if len(content_length_bytes) < 4:
        raise ValueError("Failed to read the complete content length.")
    
    content_length = int.from_bytes(content_length_bytes, byteorder='big')

    # Read the content based on the received length
    received_data = bytearray()
    while len(received_data) < content_length:
        packet = socket.recv(content_length - len(received_data))
        if not packet:
            raise ValueError("Connection closed before receiving all data.")
        received_data.extend(packet)

    return received_data.decode('utf-8')


def run(client_socket):
    while True:
        # Send "READY" command
        send_content_with_length(client_socket, "READY")

        socket_index = 1
        socket_address = client_socket.getsockname()[socket_index]

        input_file_name = receive_content_by_length(client_socket)

        # Receive file name and size
        size_bytes = client_socket.recv(4)
        file_size = int.from_bytes(size_bytes, byteorder='big')
        print("file size is:", file_size)

        # Receive file data
        with open(input_file_name, "wb") as file:
            received_bytes = 0
            while received_bytes < file_size:
                data = client_socket.recv(1024)
                file.write(data)
                received_bytes += len(data)

        print("[+] Image received successfully.")

        # Check received image
        if not os.path.exists(input_file_name) or os.path.getsize(input_file_name)==0:

            print(f"Error: The file {input_file_name} does not exist or is empty.")

        else:
            send_content_with_length(client_socket, "DONE")
            print("[*] Sent DONE command to server.")

            # Process image
            image = cv2.imread(input_file_name,cv2.IMREAD_COLOR)
            print(f"Image shape: {image.shape}")
            image = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(image,100,200)
            processed_file_path = "processedImage.jpg"
            cv2.imwrite(processed_file_path, edges)

            # Send image to server
            input_file_name = processed_file_path
            file_size = os.path.getsize(input_file_name)

            # Send file name and size

            # Send file data in chunks
            content = None
            with open(input_file_name, "rb") as file:
                content = file.read()

            send_content_with_length(client_socket, content)

            print("[+] Image sent to server successfully.")

        # Close the connection given server response.
        
        server_response = receive_content_by_length(client_socket)
        print(f'SERVER RESPONSE: {server_response}')
        if server_response == "STAY":
            print("[+] Server asks client to stay")
            # Add code for further communication with the server (optional)
        else:
            print("[+] Client killed by server")
            client_socket.close()
            break


if __name__ == '__main__':
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    SERVER_HOST = "192.168.1.29" # socket.gethostbyname(socket.gethostname())
    SERVER_PORT = 50564

    # Connect to the server
    client_socket.connect((SERVER_HOST, SERVER_PORT))
    run(client_socket)