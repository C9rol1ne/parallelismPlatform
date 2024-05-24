import socket
import tqdm
import os
from threading import Thread
from threading import Lock
#from threading import Timer
import time
import uuid

# List of statuses
BUSY = "busy"
IDLE = "idle"
AWAITING_FOR_TASK = "awaiting_for_task"
DEAD = "dead"



class Master:

    def __init__(self) -> None:
        self.slaves = []
        self.slaves_mutex = Lock()

        self.files = []
        self.files_mutex = Lock()

        self.tasks = []
        self.tasks_mutex = Lock()

        self.pending_tasks = []

        Thread(target=self.receive_user_input, args=()).start()
        Thread(target=self.create_tasks_from_file, args=()).start()
        Thread(target=self.dequeue_tasks, args=()).start()
        # Thread: Renqueue failed tasks by giving the slaves a steam so the submit the failed tasks
        # Thread: Create stream so slaves submit succesful tasks

    def receive_user_input(self):
        while True:
            filename = input('Please enter the file name: \n').strip()

            if not is_valid_filename(filename):
                print('Invalid file name. Please avoid using path traversal characters or empty names.')
                continue

            # TODO: check if the file exists!
            print(f'The provided file name is: {filename}')

            self.enqueue_file(filename)

    def do_task(self, slave, data, filename, index):
        task = Task(slave.id, data, filename, index)
        slave.set_task(task)

    def create_tasks_from_file(self):
        while True:
            filename = self.dequeue_file()
            if filename is None:
                time.sleep(0.25)

                continue

            try:
                index = 0
                tasks = []

                with open(filename, "rb") as file:
                    while True:
                        data = file.read() # Read 1024 bytes
                        if not data:
                            break

                        #print("chunk here", data)
                        print("len of chunk", len(data))

                        index += 1
                        tasks.append(Task("", data, filename, index))

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

                    idle_slave.set_task(task)

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
            task = self.tasks.pop(-1)
            
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

class Slave:
    def __init__(self, client_socket, client_address) -> None:
        self.status = IDLE
        self.status_mutex = Lock()

        self.task_mutex = Lock()
        self.task = None
        
        self.id = uuid.uuid4()
        self.client_socket = client_socket
        self.client_address = client_address

    def handle_client(self):
        print(f"[+] {self.client_address} connected.")

        try:
            while True:
                # TODO: if the receive fails it will get stuck forever
                response = self.client_socket.recv(1024).decode()
                if response == "READY":
                    while True:
                        if self.get_task() is None:
                            time.sleep(0.25)
                            continue

                        break

                    self.send_file(self.get_task())
                
                done_command = self.client_socket.recv(1024).decode()
                if done_command == "DONE":
                    print("[*] Client has sent DONE command.")

                    self.receive_file()

                server_response = "STAY"

                self.client_socket.sendall(server_response.encode())
                if server_response != "STAY":
                    break
        except:
            print(f"client {self.client_address}:{self.client_socket} timeout")
        finally:
            self.set_status(DEAD)
            self.client_socket.close()

    def send_file(self, task):
        try:
            file_size = len(task.payload)
            print(file_size)
            #print(task.payload)
            self.client_socket.send(f"{file_size}".encode())

            self.client_socket.send(task.payload)
            
            print("[+] Image sent successfully.")
        except socket.error:
            print(f"slave send file, error: {socket.error}")
        except:
            print(f"slave send file: {task.filename} failed")

    def set_task(self, task):
        self.set_status(BUSY)

        self.task_mutex.acquire()
        self.task = task
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
        file_info = self.client_socket.recv(1024).decode()
        filename, file_size = file_info.split('\n')
        file_size = int(file_size)

        with open('receivedImageFromClient.jpg', "wb") as file:
            progress = tqdm.tqdm(range(file_size), f"Receiving {filename}", unit="B", unit_scale=True, unit_divisor=1024)
            received_bytes = 0
            while received_bytes < file_size:
                data = self.client_socket.recv(1024)
                if not data:
                    break
                file.write(data)
                received_bytes += len(data)
                progress.update(len(data))
            progress.close()
        
        print("[+] Image received and saved successfully.")


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
    master = Master()

    while True:
        try:
            # Accept connections from clients
            client_socket, client_address = server.accept()
            slave = Slave(client_socket, client_address)
            master.add_slave(slave)
            
            # Create a new thread for each client
            client_thread = Thread(target=slave.handle_client)
            client_thread.start()
        except Exception as e:
            print(f"[-] Error: {e}")


if __name__ == '__main__':
    # Device's IP address and port
    SERVER_HOST = socket.gethostbyname(socket.gethostname())
    SERVER_PORT = 5051

    # Create the server TCP socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Bind the socket to our local address
    server.bind((SERVER_HOST, SERVER_PORT))

    # Put server in listening mode
    server.listen(5)
    print(f"[*] Listening as {SERVER_HOST}:{SERVER_PORT}")

    main(server)
    server.close()