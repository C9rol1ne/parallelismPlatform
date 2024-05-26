import socket
import tqdm
import os
from threading import Thread
from threading import Lock
#from threading import Timer
import time
import uuid
from PIL import Image


# List of statuses
BUSY = "busy"
IDLE = "idle"
AWAITING_FOR_TASK = "awaiting_for_task"
DEAD = "dead"



class Channel:
    def __init__(self):
        self.buffer = []
        self.mutex = Lock()

    def enqueue(self, element):
        if element is None:
            raise ValueError('cannot enqueue None values')

        self.mutex.acquire()
        self.buffer.append(element)
        self.mutex.release()

    def dequeue(self):
        self.mutex.acquire()
        out = None

        try:
            if len(self.buffer) == 0:
                raise Exception('cannot dequeue from empty buffer')

            out = self.buffer.pop(0)
        except Exception as e:
            pass
        finally:
            self.mutex.release()
            return out

    def length(self):
        self.mutex.acquire()
        length = len(self.buffer)
        self.mutex.release()

        return length

class Master:

    def __init__(self, done_task_channel) -> None:
        self.slaves = []
        self.slaves_mutex = Lock()

        self.files = []
        self.files_mutex = Lock()

        self.tasks = []
        self.tasks_mutex = Lock()

        self.pending_tasks = []

        self.tasks_by_filename = {}
        self.tasks_by_filename_mutex  = Lock()

        self.done_task_channel = done_task_channel

        Thread(target=self.receive_user_input, args=()).start()
        Thread(target=self.create_tasks_from_file, args=()).start()
        Thread(target=self.dequeue_tasks, args=()).start()
        # Thread: Re-enqueue failed tasks by giving the slaves a steam so the submit the failed tasks
        Thread(target=self.receive_done_tasks, args=()).start()

    def receive_user_input(self):
        while True:
            filename = input('Please enter the file name: \n').strip()

            if not is_valid_filename(filename):
                print('Invalid file name. Please avoid using path traversal characters or empty names.')
                continue

            # TODO: check if the file exists!
            print(f'The provided file name is: {filename}')

            self.enqueue_file(filename)

            # TODO: CAROLINA prevent reseting the progress
            self.tasks_by_filename[filename] = []

    def do_task(self, slave, data, filename, index):
        task = Task(slave.id, data, filename, index)
        slave.set_task(task)

    def split_image(self, image_path, output_folder, num_cols, num_rows):
        try:
            with Image.open(image_path) as img:
                
                width, height = img.size

                col_width = width // num_cols
                row_height = height // num_rows

                # Folder to store images
                if not os.path.exists(output_folder):
                    os.makedirs(output_folder)

                # Splitting of the images
                for row in range(num_rows):
                    for col in range(num_cols):

                        #Compute coordinates of images  
                        left = col * col_width
                        upper = row * row_height
                        right = left + col_width
                        lower = upper + row_height

                        # Crop the sub-image
                        sub_img = img.crop((left, upper, right, lower))

                        # Save the sub-image
                        sub_img_path = os.path.join(output_folder, f"sub_image_{row}_{col}.png")
                        sub_img.save(sub_img_path)

                        print(f"Sub-image saved: {sub_img_path}")

            print("Image splitting completed successfully.")
        except Exception as e:
            print(f"Error splitting image: {e}")

    def create_tasks_from_file(self):
        while True:
            filename = self.dequeue_file()
            if filename is None:
                time.sleep(0.25)

                continue

            try:

                sub_images_folder = "sub_images" # generalize
                self.split_image(filename, sub_images_folder, num_cols=3, num_rows=3)

                index = 0
                tasks = []


                for root, dirs, files in os.walk(sub_images_folder):
                    for file in files:
                        sub_image_path = os.path.join(root, file) # file path
                        with open(sub_image_path, "rb") as sub_img_file:
                            sub_image_data = sub_img_file.read()
                            tasks.append(Task("", sub_image_data, filename, index)) 
                        index += 1

                self.enqueue_tasks(tasks)

            except:
                print(f"could not enqueue {filename} tasks, please input the file again!")
            finally:
                pass

    def dequeue_tasks(self):
        try:
            while True:
                idle_slave = self.get_idle_slave()
                if idle_slave is None:
                    time.sleep(0.25)

                    continue

                while True:
                    task = self.dequeue_task()
                    if task is None:
                        time.sleep(0.25)

                        continue

                    idle_slave.assign_task(task)

                    break
                
        except:
            print("could not dequeue task")
        finally:
            if self.tasks_mutex.locked:
                self.tasks_mutex.release()

    def add_slave(self, slave):
        if slave is None:
            return

        self.slaves_mutex.acquire()

        try:
            self.slaves.append(slave)
        except:
            print("master add slave failed")
        finally:
            if self.slaves_mutex.locked:
                self.slaves_mutex.release()

    def remove_slave(self, slave):
        if self.slaves_len():
            print("master slaves list is empty:")

            return

        self.slaves_mutex.acquire()

        try:
            self.slaves.remove(slave)
        except:
            print("master remove slave failed")
        finally:
            if self.slaves_mutex.locked():
                self.slaves_mutex.release()

    def tasks_len(self):
        self.tasks_mutex.acquire()
        length = len(self.tasks)
        self.tasks_mutex.release()
        return length

    def dequeue_task(self):
        self.tasks_mutex.acquire()

        task = None
        if len(self.tasks) > 0:
            task = self.tasks.pop(0)
            
        self.tasks_mutex.release()

        return task

    def enqueue_tasks(self, tasks):
        self.tasks_mutex.acquire()
        for task in tasks:
            self.tasks.append(task)
            print(f"New task enqueued: {task.filename}, index: {task.order}")
        self.tasks_mutex.release()

    def dequeue_file(self):
        self.files_mutex.acquire()

        file = None
        if len(self.files) > 0:
            file = self.files.pop(-1)
            
        self.files_mutex.release()

        return file
    
    def enqueue_file(self, file):
        self.files_mutex.acquire()

        self.files.append(file)
            
        self.files_mutex.release()

    def slaves_len(self):
        self.slaves_mutex.acquire()
        length = len(self.slaves)
        self.slaves_mutex.release()
        return length

    def get_idle_slave(self):
        idle_slave = None

        found = False
        try:
            while not found:
                self.slaves_mutex.acquire()

                for s in self.slaves:
                    if s.get_status() == IDLE:
                        idle_slave = s
                        idle_slave.set_status(AWAITING_FOR_TASK)
                        found = True
                        break # return

                self.slaves_mutex.release()
                if idle_slave is None:
                    time.sleep(0.25)
                    continue

        except:
            print("get idle slave failed")
        finally:
            if self.slaves_mutex.locked():
                self.slaves_mutex.release()

            return idle_slave

    def receive_done_tasks(self):
        while True:
            done_task = self.done_task_channel.dequeue()
            if done_task is None:
                time.sleep(0.25)
                continue

        
            self.tasks_by_filename_mutex.acquire()
            try:
                self.tasks_by_filename[done_task.filename].append(done_task)
                print(f'Tasks for filename{done_task.filename} added to thedictionary: {done_task}')
                
            finally:
                self.tasks_by_filename_mutex.release()

            print(f"task dequeued {done_task.filename}")
            

class Slave:
    def __init__(self, client_socket, client_address, submit_channel) -> None:
        self.status = IDLE
        self.status_mutex = Lock()

        self.task_mutex = Lock()
        self.task = None
        
        self.id = uuid.uuid4()
        self.client_socket = client_socket
        self.client_address = client_address

        self.submit_channel = submit_channel

        self.file_handshake_established = False

    def is_invalid_response(self, response):
        return response == "READY" and self.file_handshake_established or response == "DONE" and not self.file_handshake_established

    def handle_client(self):
        print(f"[+] {self.client_address} connected.")

        try:
            while True:
                # TODO: if the receive fails it will get stuck forever
                response = self.client_socket.recv(1024).decode()
                if self.is_invalid_response(response):
                    self.flush_connection()
                    continue

                if response == "READY":
                    self.file_handshake_established = True
                    self.handle_send_task()

                    continue

                if response == "DONE":
                    print(f"Client {self.client_address}:{self.client_socket} has sent DONE command.")
                    self.receive_file()
                
                server_response = "STAY"

                self.client_socket.send(server_response.encode())

                self.set_status(IDLE)
                self.set_task(None)

        except:
            print(f"client {self.client_address}:{self.client_socket} timeout")
        finally:
            self.set_status(DEAD)
            self.client_socket.close()

    def handle_send_task(self):
        while True:
            if self.get_task() is None:
                time.sleep(0.25)
                continue

            break

        self.send_file(self.get_task())

    def flush_connection(self):
        self.file_handshake_established = False

    def send_file(self, task):
        try:
            file_size = len(task.payload)

            file_size_bytes = file_size.to_bytes(4, byteorder='big')
            print(file_size)
            print(file_size_bytes)

            self.client_socket.send(file_size_bytes)

            self.client_socket.send(task.payload)
            
            print("[+] Image sent successfully.")
        except socket.error:
            print(f"slave send file, error: {socket.error}")
        except:
            print(f"slave send file: {task.filename} failed")

    def assign_task(self, task):
        self.set_status(BUSY)
        self.set_task(task)

    def set_task(self, task):
        self.set_status(BUSY)

        self.task_mutex.acquire()
        self.task = task
        self.task_mutex.release()

    def set_task_data(self, payload):
        self.task_mutex.acquire()
        self.task.payload = payload
        self.task_mutex.release()

    def get_task(self):
        self.task_mutex.acquire()
        task = self.task
        self.task_mutex.release()

        return task

    def get_status(self):
        self.status_mutex.acquire()
        status = self.status
        self.status_mutex.release()
        return status
    
    def set_status(self, status):
        self.status_mutex.acquire()
        self.status = status
        self.status_mutex.release()

    def receive_file(self):

        size_bytes = self.client_socket.recv(4)
        file_size = int.from_bytes(size_bytes, byteorder='big')

        data = self.client_socket.recv(file_size)
        self.set_task_data(data)
        
        self.submit_task()
    
        print("[+] Image received and saved successfully.")

    def submit_task(self):
        self.submit_channel.enqueue(self.get_task())

class Task:

    def __init__(self, owner, payload, filename, index) -> None:
        self.owner = owner
        self.payload = payload
        self.filename = filename
        self.order = index

def is_valid_filename(filename):
    # Ensure the filename is not empty and does not contain path traversal characters
    if not filename or filename.strip() == "":
        return False

    if os.path.basename(filename) != filename:
        return False

    return True

def main(server):
    done_tasks_channel = Channel()
    master = Master(done_tasks_channel)

    while True:
        try:
            # Accept connections from clients
            client_socket, client_address = server.accept()
            slave = Slave(client_socket, client_address, done_tasks_channel)
            master.add_slave(slave)
            
            # Create a new thread for each client
            client_thread = Thread(target=slave.handle_client)
            client_thread.start()
        except Exception as e:
            print(f"[-] Error: {e}")


if __name__ == '__main__':
    # Device's IP address and port
    SERVER_HOST = socket.gethostbyname(socket.gethostname())
    SERVER_PORT = 5050

    # Create the server TCP socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Bind the socket to our local address
    server.bind((SERVER_HOST, SERVER_PORT))

    # Put server in listening mode
    server.listen(5)
    print(f"[*] Listening as {SERVER_HOST}:{SERVER_PORT}")

    main(server)
    server.close()