import threading
import time
from Client import Client
from Command import COMMAND as cmd

class AutoClient:
    def __init__(self, ip):
        self.client = Client()
        self.ip = ip
        self.receive_thread = None
        self.running = False
        self.step_size = 25
        self.current_speed = 2
        self.angle_size = 10

    def connect(self):
        if not self.running:
            self.client.turn_on_client(self.ip)
            self.receive_thread = threading.Thread(target=self.listen_for_commands, daemon=True)
            self.receive_thread.start()
            print(f"Connected to {self.ip}")
            self.running = True
        else:
            print("Already connected")

    def listen_for_commands(self):
        try:
            self.client.client_socket1.connect((self.ip, 5002))
            self.client.tcp_flag = True
            print("Connection Successful!")
        except Exception as e:
            print("Failed to connect to the server! Is the IP correct? Is the server running?")
            self.client.tcp_flag = False
        while self.running:  # Loop that listens for new commands
            try:
                alldata = self.client.receive_data()
                if alldata == '':  # Handle empty data or disconnection
                    break
                else:
                    self.process_command(alldata)  # Process incoming commands
            except Exception as e:
                print(f"Error receiving data: {e}")
                break
            time.sleep(0.1)  # Prevent high CPU usage

    def process_command(self, alldata):
        cmdArray = alldata.split('\n')
        for oneCmd in cmdArray:
            data = oneCmd.split("#")
            if data == "":
                self.client.tcp_flag = False
                break
            elif data[0] == cmd.CMD_SONIC:
                print(f"Obstacle: {data[1]} cm")
            elif data[0] == cmd.CMD_POWER:
                try:
                    if len(data) == 3:
                        self.power_value = [data[1], data[2]]
                except Exception as e:
                    print(e)

    def disconnect(self):
        print("Waiting for thread to finish...")
        self.running = False  # Stop listening for commands
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join()  # Ensure the thread stops before disconnecting
        self.client.turn_off_client()  # Turn off the connection
        print("Disconnected")

    def send_move_command(self, x, y, speed=2, angle=0):
        self.current_speed = speed  # Update the speed tracker
        command = f"{cmd.CMD_MOVE}#1#{x}#{y}#{speed}#{angle}\n"
        try:
            self.client.send_data(command)
            print(f"Command sent: {command} (Speed: {speed})")
        except Exception as e:
            print(f"Failed to send command: {e}")

    def stop(self):
        # Send a stop command to halt the movement
        self.send_move_command(x=0, y=0, speed=0, angle=0)

    def move_forward(self, speed=2):
        self.send_move_command(x=0, y=self.step_size, speed=self.current_speed)  # Forward with speed

    def move_backward(self, speed=2):
        self.send_move_command(x=0, y=-self.step_size, speed=self.current_speed)  # Backward with speed

    def turn_left(self, speed=2):
        self.send_move_command(x=-self.step_size, y=0, angle=-self.angle_size, speed=self.current_speed)  # Smooth left turn

    def turn_right(self, speed=2):
        self.send_move_command(x=self.step_size, y=0, angle=self.angle_size, speed=self.current_speed)  # Smooth right turn

    def move_left(self, speed=2):
        self.send_move_command(x=-self.step_size, y=0, speed=self.current_speed)  # Move left with speed

    def move_right(self, speed=2):
        self.send_move_command(x=self.step_size, y=0, speed=self.current_speed)  # Move right with speed

if __name__ == "__main__":
    with open('IP.txt', 'r') as file:
        ip_address = file.readline().strip()
    
    print(f"IP: {ip_address}")
    
    client = AutoClient(ip_address)
    
    client.connect()
    # Wait for commands or disconnect
    try:
        while True:
            user_input = input("Enter command or 'exit' to disconnect: ")
            if user_input.lower() == 'exit':
                client.disconnect()
                break
            # You can map user_input to different movements, e.g., 'forward', 'left', 'right', etc.
            if user_input == 'forward':
                client.move_forward()
            elif user_input == 'left':
                client.move_left()
            elif user_input == 'right':
                client.move_right()
            elif user_input == 'stop':
                client.stop()
            elif user_input == 'backward':
                client.move_backward()
            elif user_input == 'turn_left':
                client.turn_left()
            elif user_input == 'turn_right':
                client.turn_right()
            elif "speed_" in user_input:
                user_input = user_input.replace("speed_", "")
                client.current_speed = int(user_input)
            elif "angle_" in user_input:
                user_input = user_input.replace("angle_", "")
                client.angle_size = int(user_input)
            elif "step_" in user_input:
                user_input = user_input.replace("step_", "")
                client.step_size = int(user_input)
            else:
                print("Unknown command.")
    except KeyboardInterrupt:
        print("Keyboard interrupt detected")
        exit(0)

    
    
