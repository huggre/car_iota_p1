# Imports some required PyOTA libraries
import iota
from iota import Address

# Imports some libraries required by OpenALPR communication
import requests
import base64
import json

# Imports the CSV library used for DB comm. 
import csv

# Import PiCamera library
from picamera import PiCamera

# Setup the camera
camera = PiCamera()

# Rotate the image so that the lisence plate is placed horizontaly within the picture
# Depends on how you monted the camera
camera.rotation = 270

# Import the GPIO library
import RPi.GPIO as GPIO
import time
GPIO.setmode(GPIO.BCM)

# URL to IOTA fullnode used when interacting with the Tangle
iotaNode = "https://nodes.thetangle.org:443"

# Hotel owner recieving address, replace with your own recieving address
hotel_address = b'NYZBHOVSMDWWABXSACAJTTWJOQRPVVAWLBSFQVSJSWWBJJLLSQKNZFC9XCRPQSVFQZPBJCJRANNPVMMEZQJRQSVVGZ'

# Price of the parking service (10 IOTA)
price = 10

# Specify GPIO pins used by ultrasonic sensor
TRIG = 23 
ECHO = 24

# Variable used for monitoring when car enters/exits the sensor area
car_found = False

print "Distance Measurement In Progress"

# Setup the GPIO pins
GPIO.setup(TRIG,GPIO.OUT)
GPIO.setup(ECHO,GPIO.IN)

# Function for capturing image using the Raspberry PI camera
def capture_image():
    image_file = "/home/pi/Desktop/image.jpg"
    print("Capturing image...")
    camera.start_preview()
    time.sleep(1)
    camera.capture(image_file)
    camera.stop_preview()
    get_plate_id(image_file)

# Function for getting the plate ID from image using the OpenALPR Cloud API service 
def get_plate_id(image_file):

    # Replace with your OpenALPR secret key
    SECRET_KEY = 'PutYourOpenALPRSecretKeyHere'

    with open(image_file, 'rb') as image_file:
        img_base64 = base64.b64encode(image_file.read())

    # Send image to the OpenALPR Cloud service for decoding
    url = 'https://api.openalpr.com/v2/recognize_bytes?recognize_vehicle=1&country=us&secret_key=%s' % (SECRET_KEY)
    r = requests.post(url, data = img_base64)

    # Convert returned json to string 
    r_str = json.loads(json.dumps(r.json(), indent=2))
     
    # Search the Plate/SEED DB for a matching lisence plate
    # If found, get the related SEED
    try:
        if 'plate' in r_str['results'][0]:
            plate_id = r_str['results'][0]['plate']
            print(plate_id)
            get_seed(plate_id)
    except:
        print('OpenALPR did not return a plate ID')       



# Function for getting the seed used for IOTA payment
def get_seed(plate_id):

    plate_found = False

    with open('plates.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for row in csv_reader:
            if row[0] == plate_id:
                seed=row[1]
                plate_found = True
    
    if plate_found == True:
        print("Plate was found in DB, seed: " + seed)
        send_transaction(hotel_address, price, plate_id, seed)
    else:
        print("Plate was not found in DB")
        
# Function for sending the IOTA value transaction
def send_transaction(hotel_address, price, plate_id, seed):
    
    # Define api object
    api = iota.Iota(iotaNode, seed=seed)

    # Create transaction object
    tx1 = iota.ProposedTransaction( address = iota.Address(hotel_address), message = None, tag = iota.Tag(iota.TryteString.from_unicode(plate_id)), value = price)

    # Send transaction to tangle
    print("\nSending transaction... Please wait...")
    SentBundle = api.send_transfer(depth=3,transfers=[tx1], inputs=None, change_address=None, min_weight_magnitude=14)       

    # Display transaction sent confirmation message
    print("\nTransaction sent...")
        

# Check (every 2 sec.) for new cars entering or exiting the parking lot..
try:
    while True:

        GPIO.output(TRIG, False)
        print "Waiting For Sensor To Settle"
        time.sleep(2)

        GPIO.output(TRIG, True)
        time.sleep(0.00001)
        GPIO.output(TRIG, False)

        while GPIO.input(ECHO)==0:
          pulse_start = time.time()

        while GPIO.input(ECHO)==1:
          pulse_end = time.time()

        pulse_duration = pulse_end - pulse_start

        # Convert distance to cm
        distance = pulse_duration * 17150

        distance = round(distance, 2)
        
        # If distance between sensor and car is less than 10 cm
        if distance < 10:
            if car_found == False:
                capture_image()
                car_found = True
        else:
            car_found = False
                

except KeyboardInterrupt: # If there is a KeyboardInterrupt (when you press ctrl+c), exit the program and cleanup
    print("Cleaning up!")
    GPIO.cleanup()
