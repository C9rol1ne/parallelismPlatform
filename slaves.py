import socket
import tqdm
import os

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
SERVER_HOST = socket.gethostbyname(socket.gethostname())
client.connect((SERVER_HOST, 5050))

file = open("spongebob.jpg","rb")
file_size = os.path.getsize("spongebob.jpg")

client.send("received_image.jpg".encode())
client.send(str(file_size).encode())

data = file.read()
client.sendall(data)
client.send(b"<END>")

file.close()
client.close()