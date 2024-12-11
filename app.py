from flask import Flask, jsonify, render_template
import base64
import ctypes
import io
import time
from PIL import Image
import os
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Path to the SecuGen SDK DLL - ensure sgfplib.dll is in this path or update accordingly
DLL_PATH = r'C:\Users\ADMIN\Desktop\FDx SDK Pro for Windows v4.3.1_J1.12\FDx SDK Pro for Windows v4.3.1\bin\x64\sgfplib.dll'

# Verify that the DLL exists
if not os.path.exists(DLL_PATH):
    logger.error(f"sgfplib.dll not found at path: {DLL_PATH}")
    raise FileNotFoundError(f"sgfplib.dll not found at path: {DLL_PATH}")

# Load the SecuGen SDK DLL
try:
    sgfplib = ctypes.CDLL(DLL_PATH)
    logger.debug("sgfplib.dll loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load sgfplib.dll: {e}")
    raise

# Constants from SecuGen SDK
SGFDX_ERROR_NONE = 0
SG_DEV_AUTO = 0xFF

# Define the SGDeviceInfo structure
class SGDeviceInfo(ctypes.Structure):
    _fields_ = [
        ("DeviceID", ctypes.c_uint32),
        ("DeviceSN", ctypes.c_char * 16),
        ("ComPort", ctypes.c_uint32),
        ("ComSpeed", ctypes.c_uint32),
        ("ImageWidth", ctypes.c_uint32),
        ("ImageHeight", ctypes.c_uint32),
        ("Contrast", ctypes.c_uint32),
        ("Brightness", ctypes.c_uint32),
        ("Gain", ctypes.c_uint32),
        ("ImageDPI", ctypes.c_uint32),
        ("FWVersion", ctypes.c_char * 16)
    ]

# Define function prototypes
sgfplib.SGFPM_Create.restype = ctypes.c_int
sgfplib.SGFPM_Create.argtypes = [ctypes.POINTER(ctypes.c_void_p)]

sgfplib.SGFPM_Init.restype = ctypes.c_int
sgfplib.SGFPM_Init.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

sgfplib.SGFPM_OpenDevice.restype = ctypes.c_int
sgfplib.SGFPM_OpenDevice.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

sgfplib.SGFPM_GetDeviceInfo.restype = ctypes.c_int
sgfplib.SGFPM_GetDeviceInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(SGDeviceInfo)]

sgfplib.SGFPM_SetLedOn.restype = ctypes.c_int
sgfplib.SGFPM_SetLedOn.argtypes = [ctypes.c_void_p, ctypes.c_bool]

sgfplib.SGFPM_GetImage.restype = ctypes.c_int
sgfplib.SGFPM_GetImage.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char)]

sgfplib.SGFPM_CloseDevice.restype = ctypes.c_int
sgfplib.SGFPM_CloseDevice.argtypes = [ctypes.c_void_p]

sgfplib.SGFPM_Terminate.restype = ctypes.c_int
sgfplib.SGFPM_Terminate.argtypes = [ctypes.c_void_p]

# Define the fingerprint storage folder
FINGERPRINTS_FOLDER = os.path.join('static', 'fingerprints')
os.makedirs(FINGERPRINTS_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/capture', methods=['GET'])
def capture_fingerprint():
    hFPM = ctypes.c_void_p()

    try:
        # Create the SGFPM object
        result = sgfplib.SGFPM_Create(ctypes.byref(hFPM))
        if result != SGFDX_ERROR_NONE:
            logger.error(f"SGFPM_Create failed with error code: {result}")
            return jsonify({"status": "error", "message": f"SGFPM_Create failed with error code: {result}"}), 500
        logger.debug("SGFPM_Create succeeded.")

        # Initialize the device
        result = sgfplib.SGFPM_Init(hFPM, SG_DEV_AUTO)
        if result != SGFDX_ERROR_NONE:
            logger.error(f"SGFPM_Init failed with error code: {result}")
            return jsonify({"status": "error", "message": f"SGFPM_Init failed with error code: {result}"}), 500
        logger.debug("SGFPM_Init succeeded.")

        # Open the device
        result = sgfplib.SGFPM_OpenDevice(hFPM, SG_DEV_AUTO)
        if result != SGFDX_ERROR_NONE:
            logger.error(f"SGFPM_OpenDevice failed with error code: {result}")
            return jsonify({"status": "error", "message": f"SGFPM_OpenDevice failed with error code: {result}"}), 500
        logger.debug("SGFPM_OpenDevice succeeded.")

        # Get device information
        dev_info = SGDeviceInfo()
        result = sgfplib.SGFPM_GetDeviceInfo(hFPM, ctypes.byref(dev_info))
        if result != SGFDX_ERROR_NONE:
            logger.error(f"SGFPM_GetDeviceInfo failed with error code: {result}")
            return jsonify({"status": "error", "message": f"SGFPM_GetDeviceInfo failed with error code: {result}"}), 500
        logger.debug(f"SGFPM_GetDeviceInfo succeeded. Device Info: {dev_info}")

        # Calculate image buffer size
        img_size = dev_info.ImageWidth * dev_info.ImageHeight
        img_buffer = (ctypes.c_char * img_size)()

        # Turn on LED and capture image
        result = sgfplib.SGFPM_SetLedOn(hFPM, True)
        if result != SGFDX_ERROR_NONE:
            logger.error(f"SGFPM_SetLedOn (True) failed with error code: {result}")
            return jsonify({"status": "error", "message": f"SGFPM_SetLedOn failed with error code: {result}"}), 500
        logger.debug("LED turned on.")

        time.sleep(2)  # Wait for finger placement

        result = sgfplib.SGFPM_GetImage(hFPM, img_buffer)
        if result != SGFDX_ERROR_NONE:
            logger.error(f"SGFPM_GetImage failed with error code: {result}")
            sgfplib.SGFPM_SetLedOn(hFPM, False)
            return jsonify({"status": "error", "message": f"SGFPM_GetImage failed with error code: {result}"}), 500
        logger.debug("SGFPM_GetImage succeeded.")

        # Turn off LED
        result = sgfplib.SGFPM_SetLedOn(hFPM, False)
        if result != SGFDX_ERROR_NONE:
            logger.warning(f"SGFPM_SetLedOn (False) failed with error code: {result}")
        else:
            logger.debug("LED turned off.")

        # Convert image buffer to PIL Image
        img = Image.frombytes('L', (dev_info.ImageWidth, dev_info.ImageHeight), img_buffer)

        # Optionally, enhance the image here (e.g., resize, apply filters)

        # Convert image to PNG and then to base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # Save the image to the server with a unique filename
        timestamp = int(time.time())
        filename = f"fingerprint_{timestamp}.png"
        filepath = os.path.join(FINGERPRINTS_FOLDER, filename)
        img.save(filepath)
        logger.debug(f"Fingerprint image saved at {filepath}")

        relative_path = os.path.join('fingerprints', filename)

        return jsonify({"status": "success", "image": base64_image, "image_path": relative_path}), 200

    except Exception as e:
        logger.exception(f"Exception during fingerprint capture: {e}")
        return jsonify({"status": "error", "message": "An unexpected error occurred during fingerprint capture."}), 500

    finally:
        # Close the device and terminate
        if hFPM:
            result = sgfplib.SGFPM_CloseDevice(hFPM)
            if result != SGFDX_ERROR_NONE:
                logger.warning(f"SGFPM_CloseDevice failed with error code: {result}")
            else:
                logger.debug("SGFPM_CloseDevice succeeded.")
            
            result = sgfplib.SGFPM_Terminate(hFPM)
            if result != SGFDX_ERROR_NONE:
                logger.warning(f"SGFPM_Terminate failed with error code: {result}")
            else:
                logger.debug("SGFPM_Terminate succeeded.")

if __name__ == '__main__':
    app.run(debug=True)
