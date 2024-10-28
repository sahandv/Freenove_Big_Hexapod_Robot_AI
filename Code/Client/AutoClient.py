import threading
import time
import logging
import cv2
from Client import Client
from Command import COMMAND as cmd
from Thread import stop_thread
import os
import matplotlib.pyplot as plt

# Set up logging configuration
logging.basicConfig(level=logging.WARN, format='%(asctime)s - %(levelname)s - %(message)s')

class AutoClient:
    def __init__(self, ip):
        self.client = Client()
        self.ip = ip
        self.receive_thread = None
        self.running = False
        self.step_size = 25
        self.current_speed = 4
        self.angle_size = 15
        self.sonar_distance = None  # Initialize with a default value
        self.image_retrieve_thread = None  # Image retrieval thread
        self.video_running = False
        self.current_frame = None
        self.power_value = ["0", "0"]
        self.head_defailt_angle_x = 70
        self.image = None  # Placeholder for the retrieved image data
        self.video_flag = False  # Flag indicating when a new image is available
        self.frame_count = 0  # Counter for frame file naming
        # Set directory for saving images
        self.save_directory = "frames"
        self.fig, self.ax = plt.subplots()  # Matplotlib figure and axis
        self.image_display = None  # Placeholder for the displayed image in the plot
        self.new_frame_event = threading.Event()
        if not os.path.exists(self.save_directory):
            os.makedirs(self.save_directory)
            
    def connect(self):
        """Establish the client connection and start the receive thread."""
        if not self.running:
            self.client.turn_on_client(self.ip)
            self.running = True
            self.receive_thread = threading.Thread(target=self.receive_instruction)#, daemon=True)
            self.receive_thread.start()
            self.videoThread=threading.Thread(target=self.client.receiving_video,args=(self.ip,self))
            self.videoThread.start()
            logging.info(f"Connected to {self.ip}") 
            # self.start_battery_timer()
            # self.request_sonar_data()
            self.start_sonar_timer()    # Start sonar data requests
            logging.info("Initiating position...")
            self.init_position()  
        else:
            logging.info("Already connected")
            
    def disconnect(self):
        """Safely disconnect the client."""
        logging.debug("Waiting for thread to finish...")
        self.running = False  # Signal thread to stop
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join()  # Wait for the receive thread to stop
        if self.videoThread and self.videoThread.is_alive():
            self.videoThread.join()  # Stop video retrieval thread
        
        try:
            stop_thread(self.videoThread)
        except Exception as e:
            logging.error(e)
        try:
            stop_thread(self.receive_thread)
        except Exception as e:
            logging.error(e)
        
        self.client.turn_off_client()  # Close the client connection
        logging.info("Disconnected")
        
    # Data request and process methods
    def receive_instruction(self):
        """Thread to handle receiving instructions from the server."""
        try:
            # Connect to the server on the specific socket
            self.client.client_socket1.connect((self.ip, 5002))
            self.client.tcp_flag = True
            logging.info("Connection Successful!")
        except Exception as e:
            logging.error("Failed to connect to the server! Is the IP correct? Is the server running?")
            self.client.tcp_flag = False
            return  # Exit if connection fails

        logging.info("Starting data loop...")
        while self.running:
            try:
                logging.debug("Receiving data...")
                alldata = self.client.receive_data()
                logging.debug(f"Raw data received: {alldata}")

                if alldata == '':  # If no data, break the loop
                    logging.info("No data received, ending connection.")
                    break

                # Process each command line received
                cmdArray = alldata.split('\n')
                for oneCmd in cmdArray:
                    if oneCmd:  # Avoid processing empty commands
                        logging.debug(f"Processing command: {oneCmd}")
                        data = oneCmd.split("#")
                        if data[0] == cmd.CMD_SONIC:
                            self.sonar_distance = int(data[1])  # Store the sonar data
                            logging.info(f"Obstacle: {self.sonar_distance} cm")
                        elif data[0] == cmd.CMD_POWER:
                            try:
                                if len(data) == 3:
                                    self.power_value = [data[1], data[2]]
                                    logging.info(f"Power values: {self.power_value}")
                            except Exception as e:
                                logging.error(f"Error processing power data: {e}")

            except Exception as e:
                logging.error(f"Error receiving data: {e}")
                self.client.tcp_flag = False
                break
            time.sleep(0.2)  # Prevent high CPU usage
        logging.info("Receiving data thread stopped")

    def start_battery_timer(self):
        self.battery_timer = threading.Timer(3.0, self.request_battery_data)  # Call every 3 seconds
        self.battery_timer.start()
        
    def request_battery_data(self):
        # Command to request battery data
        command = cmd.CMD_POWER + '\n'
        self.client.send_data(command)
        logging.debug("Battery data requested.")
        # Restart the timer to request data again after 3 seconds
        self.start_battery_timer()
        
    def start_sonar_timer(self):
        """Initiate sonar data requests every 100 milliseconds."""
        logging.debug("Requesting sonar data...")
        self.getSonicData()  # Request sonar data
        # Start a new timer that will call this method again after 100ms
        self.sonar_timer = threading.Timer(0.1, self.start_sonar_timer)
        self.sonar_timer.start()
            
    def getSonicData(self):
        """Send a command to request sonar data from the server."""
        command = cmd.CMD_SONIC + '\n'
        self.client.send_data(command)
        logging.debug("Sonar data request sent.")

    # Video stream methods
    def vide_stream(self, show=False, save=False):
        """Display frames with matplotlib and save to disk."""
        while self.running and self.video_running:
            self.new_frame_event.wait()
            try:
                if show:
                    # Display with matplotlib
                    if self.image_display is None:
                        self.image_display = self.ax.imshow(self.client.image)
                    else:
                        self.image_display.set_data(self.client.image)                    
                    plt.pause(0.01)  # Small pause to allow for update

                if save:
                    # Save to disk
                    file_path = os.path.join(self.save_directory, f"frame_{self.frame_count}.png")
                    cv2.imwrite(file_path, self.client.image)
                    logging.info(f"Saved and displayed frame {self.frame_count} to {file_path}")
                self.frame_count += 1
                self.client.video_flag = True
                self.new_frame_event.clear()
            except Exception as e:
                logging.error(f"Failed to save or display frame: {e}")
            
    def start_video_stream(self, show=False, save=True):
        if self.video_running:
            logging.info("Video stream already running.")
            return
        else:
            self.video_running = True
            self.vide_stream(show=show, save=save)
        
    def stop_video_stream(self):
        self.video_running = False
        logging.info("Video stream stopped.")
    
    
    # Physical movement methods
    def send_move_command(self, x, y, angle=0):
        """Send a movement command to the client."""
        command = f"{cmd.CMD_MOVE}#1#{x}#{y}#{self.current_speed}#{angle}\n"
        try:
            self.client.send_data(command)
            logging.info(f"Command sent: {command} (Speed: {self.current_speed})")
        except Exception as e:
            logging.info(f"Failed to send command: {e}")

    def stop(self):
        """Send a stop command to halt all movement."""
        self.send_move_command(x=0, y=0, angle=0)

    # Head movement commands
    def headLeftAndRight(self, angle):
        """Turn the head left or right to the specified angle."""
        try:
            # Convert angle to string and format the command
            angle_str = str(180 - angle)  # Mirror the angle, if needed
            command = f"{cmd.CMD_HEAD}#1#{angle_str}\n"
            
            # Send the command to the client
            self.client.send_data(command)
            logging.info(f"Head angle set to: {angle_str} degrees")
        except Exception as e:
            logging.info(f"Error setting head angle: {e}")
            
    def headLeftAndRightAdjusted(self, angle):
        """Turn the head left or right to the specified angle,
        adjusted for the default head angle, as the front, taking 
        positive values to the right and negative values to the left."""
        self.headLeftAndRight(self.head_defailt_angle_x + angle)
        
        
    # Base Movement commands
    def move_forward(self):
        self.send_move_command(x=0, y=self.step_size)

    def move_backward(self):
        self.send_move_command(x=0, y=-self.step_size)

    def turn_left(self):
        self.send_move_command(x=-self.step_size, y=0, angle=-self.angle_size)

    def turn_right(self):
        self.send_move_command(x=self.step_size, y=0, angle=self.angle_size)

    def move_left(self):
        self.send_move_command(x=-self.step_size, y=0)

    def move_right(self):
        self.send_move_command(x=self.step_size, y=0)
    
    # Servo commands
    def relax(self):
        command = cmd.CMD_SERVOPOWER + "#0\n"
        self.client.send_data(command)
        
    def ready(self):
        command = cmd.CMD_SERVOPOWER + "#1\n"
        self.client.send_data(command)

    # Position init methods
    def init_position(self):
        self.init_head_position()
    
    def init_head_position(self):
        self.headLeftAndRight(self.head_defailt_angle_x)

if __name__ == "__main__":
    with open('IP.txt', 'r') as file:
        ip_address = file.readline().strip()
    
    logging.info(f"IP: {ip_address}")
    
    client = AutoClient(ip_address)
    
    client.connect()
    try:
        while True:
            user_input = input("Enter command or 'exit' to disconnect: ")
            if user_input.lower() == 'exit':
                client.disconnect()
            # if user_input == 'connect':
            #     client.connect()
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
            elif user_input == 'relax':
                client.relax()
            elif user_input == 'ready':
                client.ready()
            elif "speed_" in user_input:
                client.current_speed = int(user_input.replace("speed_", ""))
            elif "angle_" in user_input:
                client.angle_size = int(user_input.replace("angle_", ""))
            elif "step_" in user_input:
                client.step_size = int(user_input.replace("step_", ""))
            elif "headx_" in user_input:
                angle = int(user_input.replace("headx_", ""))
                client.headLeftAndRightAdjusted(angle)
            elif user_input == 'start_video':
                client.start_video_stream()
                time.sleep(10)
                client.stop_video_stream()
            elif user_input == 'stop_video':
                client.stop_video_stream()
            elif user_input == 'get_frame':
                frame = client.refresh_image()
                if frame is not None:
                    # Process the frame for object detection or display
                    logging.info("Frame received for processing")
                    # Add object detection processing here if needed
                else:
                    logging.info("No frame available")
            else:
                logging.warning("Unknown command.")
                
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt detected")
        client.disconnect()