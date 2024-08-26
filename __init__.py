import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QLineEdit, QGridLayout, QMainWindow, QStatusBar, QToolBar, QMainWindow
from PyQt5.QtGui import QIntValidator, QIcon, QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer, QMetaObject, QThread
import pco.camera
import pyqtgraph as pg
import threading
import serial
import time
import numpy as np
import pco
import MCM300 as mc
from optotune_lens import Lens
from tifffile import imwrite 
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.colors import Normalize
import matplotlib.pyplot as plt
import math
import random
from enum import Enum
import cv2 as cv
import configparser
import os
import json

software_version = "0.0.1"

# todo:
# - fix bug with ui incited movement interfering with movement indigator
# - stop recorder after ending live view mode
# - bug stack acquisition in simulation mode only shows data after live view has been run once

# Traceback (most recent call last):
#   File "d:\Dominik\Github\LSM-microscope\__init__.py", line 507, in save_image
#     self.cam.wait_for_first_image()
#   File "D:\Dominik\Github\LSM-microscope\lsm_env\Lib\site-packages\pco\camera.py", line 1682, in wait_for_first_image
#     if self.rec.get_status()["dwProcImgCount"] >= 1:
#        ^^^^^^^^^^^^^^^^^^^^^
#   File "D:\Dominik\Github\LSM-microscope\lsm_env\Lib\site-packages\pco\recorder.py", line 741, in get_status
#     raise CameraException(sdk=self.sdk, code=error)
# pco.camera_exception.CameraException: CameraException 0x80153004: SDK DLL error 80153004 at device 'recorder dll': Option is not available.

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
elif __file__:
    application_path = os.path.dirname(__file__)

#-- Defaults --
# Camera defaults
default_cam_pix_x = 2048
default_cam_pix_y = 2048
default_exposure_time = int(100)

# Lens defaults
lens_diopter = 0 #setting default lens diopter value to 0, centering it in its range (-5,5)
lens_max_diopter = 5
lens_min_diopter = -5
default_lens_live_update_delay = 0.1

# Stage defaults
default_position_update_delay = 0.1

# Scanner defauls

# UI defaults
default_um_btn_move = 10
#setting default dynamic range of image display canvas
default_vMin = 0
default_vMax = 65535
default_roi_position = (math.floor(default_cam_pix_x/4),math.floor(default_cam_pix_y/4))
default_roi_size = (math.floor(default_cam_pix_x/2),math.floor(default_cam_pix_y/2))
default_config_file_path = application_path+"\config.json" # the config file location is fixed and cannot be modified from the config file itself to avoid file detection issues
default_save_file_path = application_path+"\imageOut"

#-- Defaults --

# manage configuration file and its data
class ConfigFile:
    def __init__(self):
        self.configs = {
            "default_um_btn_move": default_um_btn_move,
            "default_vMin": default_vMin,
            "default_vMax": default_vMax,
            "default_roi_position":default_roi_position,
            "default_roi_size":default_roi_size,
            "default_cam_pix_x": default_cam_pix_x,
            "default_cam_pix_y": default_cam_pix_y,
            "default_exposure_time": default_exposure_time,
            "lens_diopter": lens_diopter,
            "lens_max_diopter": lens_max_diopter,
            "lens_min_diopter": lens_min_diopter,
            "default_lens_live_update_delay": default_lens_live_update_delay,
            "default_position_update_delay": default_position_update_delay,
            "default_save_file_path": default_save_file_path
            }
    
    def loadConfig(self, filePath):
        if os.path.exists(filePath):
            with open(filePath,"r") as jsonFile:
                data = json.load(jsonFile)
                #print(data)
                self.configs = data
            print("configuration loaded")
        else:
            self.saveConfig(filePath) #create a new config file that contains the default values if no file was found
            print("no config file found, creating new file with default configuration")
        return
    
    def saveConfig(self, filePath):
        with open(filePath,"w") as jsonFile:
            jsonFileData = json.dumps(self.configs)
            jsonFile.write(jsonFileData)
        return


class CameraDummy:

    def __init__(self):
        self.sdk = self
        self.expodure_time = 0
        self.delay_time = 0
        
        print("simulating camera")

    def record(self, n_images=1, mode="sequence"):
        #print("starting recording of "+str(n_images)+" images in "+str(mode)+" mode")
        #print("exposure time "+str(self.expodure_time)+"ms, delay "+str(self.delay_time)+" ms")
        time.sleep(1.0*(self.expodure_time+self.delay_time)/1000.0)
        #print("recording done")

    def image(self):
        #print("capturing image")
        imageData = np.random.randint(default_vMax, size=(2048,2048))
        imageData16 = imageData.astype(np.uint16)
        wait_time = 1.0*(self.expodure_time+self.delay_time)/1000.0 
        #print(wait_time)
        #time.sleep(wait_time)
        metaData = "none"
        return imageData16, metaData

    def wait_for_first_image(self):
        #print("waiting for first image")
        time.sleep(1.0*(self.expodure_time+self.delay_time)/1000.0)
        #print("done waiting")

    
    def wait_for_new_image(self, delay=True, timeout=15):
        #print("waiting for new image")
        time.sleep(1.0*(self.expodure_time+self.delay_time)/1000.0)
        #print("done waiting")

    def stop(self):
        print("cam stopped")

    def set_recording_state(self, state):
        print("setting recording state to "+str(state))

    def set_trigger_mode(self, state):
        print("setting trigger mode to "+str(state))

    def set_delay_exposure_time(self, delay_time, dt_unit, exposure_time, ex_unit):
        print("setting delay time to "+str(delay_time)+" "+str(dt_unit))
        self.delay_time = delay_time
        print("setting exposure time to "+str(exposure_time)+" "+str(ex_unit))
        self.expodure_time = exposure_time
        
    def close(self):
        print("cam connection closed")


class StageDummy:
    class ChannelName(Enum):
            X = 0
            Y = 1
            Z = 2

    def __init__(self):
        print("simulating xyz stage")
        self.pos = np.zeros(3)
        
    def _set_encoder_counts_to_zero(self, channel):
        print("defined as zero")

    def close(self):
        print("stage connection closed")

    def get_position_um(self, channel):
        #pos = " 5"
        #pos = (random.uniform(-4000,4000))
        
        pos = self.pos[channel]

        return pos

    def move_um(self, channel, move_um, relative, block=True):
        
        if relative:
            self.pos[channel] = self.pos[channel]+ move_um
            print("moving stage on "+str(self.ChannelName(channel).name)+" axis for "+ str(move_um)+ " um")
            time.sleep(abs(move_um/100.0))
        else:
            moveDelta = move_um-self.pos[channel]
            self.pos[channel] = move_um
            print("moving stage on "+str(self.ChannelName(channel).name)+" axis for "+ str(moveDelta)+ " um")
            time.sleep(abs(moveDelta/100.0))
        
        
        print("done moving")
        

class LensDummy:
    def __init__(self):
        self.lens_diopter = 0
        print("simulating ETL lens")

    def to_focal_power_mode(self):
        print("switched to diopter mode")
        return 0

    def set_diopter(self, lens_diopter):
        self.lens_diopter = lens_diopter
        #print("refractive power set to "+str(lens_diopter)+ "diopter")

    def get_diopter(self):
        
        #print("lens diopter is "+str(self.lens_diopter))
        return self.lens_diopter
    
    def close(self):
        print("lens connection closed")


class ScannerDummy:
    def __init__(self):
        print("simulating scanner")
    
    def write(self,command):
        #print("command sent to arduino")
        return 0

    def close(self):
        print("scanner connection closed")


class ObjectiveInfo:
    def __init__(self, description, NA, FoV_um):
        self.description = description
        self.NA = NA
        self.FoV = FoV_um

    def calculate_pixel_size(self, pixels):
        self.pixelSize = self.FoV/pixels
        return self.pixelSize




class MicroscopeControlGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.configData = ConfigFile()
        self.configData.loadConfig(default_config_file_path)
        # get default configs from file (or generate a new file)
        #self.get_config()

        # Initialize components
        try:
            self.controller_mcm = mc.Controller(which_port='COM4',
                                        stages=('ZFM2020', 'ZFM2020', 'ZFM2020'),
                                        reverse=(False, False, False),
                                        verbose=False,
                                        very_verbose=False)
        except:
            print("xyz stage not found")
            self.controller_mcm = StageDummy()


        for channel in range(3):
            self.controller_mcm._set_encoder_counts_to_zero(channel)

        try:
            self.lens = Lens('COM5', debug=False)
        except:
            self.lens = LensDummy()

        self.lens.to_focal_power_mode() # switch lens to focus power mode instead of current mode
        self.lens.set_diopter(self.configData.configs["lens_diopter"]) # set diopter to default value
        
        self.lensCalib = np.zeros((2,2))
        self.bLensCalibrated = False

        
        try:
            self.cam = pco.Camera(interface="USB 3.0")
        except:
            self.cam = CameraDummy()

        try:
            self.arduino = serial.Serial(port="COM6", baudrate=115200, timeout=1)
        except:
            self.arduino = ScannerDummy()
        
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('LSM Control (version '+ software_version+ ")")

        # Create the canvas for the camera
        self.canvas = pg.ImageView()
        imageData = np.zeros((self.configData.configs["default_cam_pix_x"],self.configData.configs["default_cam_pix_y"]))
        imageData16 = imageData.astype(np.uint16)
        self.canvas.setImage(imageData)
        self.canvas.roi.setSize(self.configData.configs["default_roi_size"])
        self.canvas.roi.setPos(self.configData.configs["default_roi_position"])
        self.canvas.setMinimumWidth(500)
        
        # Create the main layout
        main_layout = QHBoxLayout()
        
        # Create the settings layout
        settings_layout = QVBoxLayout()
        settings_widget = QWidget()
        settings_widget.setLayout(settings_layout)
        settings_widget.setFixedWidth(500)  # Fixed width for settings

        # Add exposure time input
        exposure_layout = QHBoxLayout()
        exposure_label = QLabel("Exposure Time (ms):")
        self.exposure_input = QLineEdit(str(self.configData.configs["default_exposure_time"]))
        self.exposure_input.returnPressed.connect(self.update_exposure_time)
        self.exposure_time = self.configData.configs["default_exposure_time"]
        exposure_layout.addWidget(exposure_label)
        exposure_layout.addWidget(self.exposure_input)

        # Add start/stop live view buttons
        self.start_live_view_btn = QPushButton("Start Live-View")
        self.start_live_view_btn.clicked.connect(self.init_live_acquisition)
        exposure_layout.addWidget(self.start_live_view_btn)

        self.stop_live_view_btn = QPushButton("Stop Live-View")
        self.stop_live_view_btn.clicked.connect(self.stop_live_acquisition)
        self.stop_live_view_btn.setDisabled(True)
        exposure_layout.addWidget(self.stop_live_view_btn)

        # Add the exposure and min/max controls to the settings layout
        settings_layout.addLayout(exposure_layout)
        
        # Label um step fixed size
        self.label_joystick = QLabel('10 um steps for sample stage')
        self.create_control_buttons()

        # Sliders stage
        x_layout, self.x_slider, self.x_text = self.create_slider_with_text('X Position (um)', -10000, 10000, 0, self.move_stage, channel=0)
        y_layout, self.y_slider, self.y_text = self.create_slider_with_text('Y Position (um)', -10000, 10000, 0, self.move_stage, channel=1)
        z_layout, self.z_slider, self.z_text = self.create_slider_with_text('Z Position (um)', -10000, 10000, 0, self.move_stage, channel=2)

        # Sliders optotune lens and arduino stepper motor
        current_layout, self.current_slider, self.current_text = self.create_slider_with_text('milli Diopter', -5000, 5000, 0, self.change_optotune_diopter) #changed slider from current to focal strength in diopter
        acceleration_layout, self.acceleration_slider, self.acceleration_text = self.create_slider_with_text('Acceleration', 1, 25000, 1000, self.send_acc_serial_command)
        amplitude_layout, self.amplitude_slider, self.amplitude_text = self.create_slider_with_text('Amplitude', 1, 50, 30, self.send_width_serial_command)
        
        self.pause_stepper_motor_btn = QPushButton("Pause stepper motor")
        self.pause_stepper_motor_btn.clicked.connect(lambda: self.send_command_arduino("p?"))

        self.start_stepper_motor_btn = QPushButton("Start stepper motor")
        self.start_stepper_motor_btn.clicked.connect(lambda: self.send_command_arduino("s?"))

        self.move_cw_stepper_motor_btn = QPushButton("Move CW stepper motor")
        self.move_cw_stepper_motor_btn.clicked.connect(lambda: self.send_command_arduino("r?"))
        
        self.move_ccw_stepper_motor_btn = QPushButton("Move CCW stepper motor")
        self.move_ccw_stepper_motor_btn.clicked.connect(lambda: self.send_command_arduino("l?"))
        
        self.stop_stepper_motor_btn = QPushButton("STOP stepper motor")
        self.stop_stepper_motor_btn.clicked.connect(lambda: self.send_command_arduino("h?"))

        self.get_Lens_calib_point_btn = QPushButton("Get Lens Calibration Point")
        self.get_Lens_calib_point_btn.clicked.connect(self.get_Lens_calib_point)

        self.clear_Lens_calib_btn = QPushButton("Clear Lens Calibration")
        self.clear_Lens_calib_btn.clicked.connect(self.clear_Lens_calib)
        self.clear_Lens_calib_btn.setDisabled(True)


        light_house_layout = QGridLayout()
        light_house_layout.addWidget(self.pause_stepper_motor_btn, 0, 0)
        light_house_layout.addWidget(self.start_stepper_motor_btn, 0, 1)
        light_house_layout.addWidget(self.move_ccw_stepper_motor_btn,1,0)
        light_house_layout.addWidget(self.move_cw_stepper_motor_btn,1,1)
        light_house_layout.addWidget(self.stop_stepper_motor_btn)
        light_house_layout.addWidget(self.get_Lens_calib_point_btn,3,0)
        light_house_layout.addWidget(self.clear_Lens_calib_btn,3,1)

        # Acquisition z start/end positions
        self.z_max_label = QLabel('Z-Max')
        self.z_max_btn = QPushButton('Set Z-Max')
        self.z_max_btn.clicked.connect(lambda: self.set_z_position('max'))

        self.z_min_label = QLabel('Z-Min')
        self.z_min_btn = QPushButton('Set Z-Min')
        self.z_min_btn.clicked.connect(lambda: self.set_z_position('min'))

        self.z_step_label = QLabel('Z-Step')
        self.z_step_text = QLineEdit('10')
        self.z_step_text.setValidator(QIntValidator(1, 500))
        self.z_step_text.setFixedWidth(50)
        self.z_step_text.setAlignment(Qt.AlignCenter)

        self.set_encoders_to_zero_btn = QPushButton("Set to zero encoders sample stage")
        self.set_encoders_to_zero_btn.clicked.connect(self.set_encoders_to_zero)
        self.acquisition_thread_function_btn = QPushButton("Start Stack Acquisition")
        self.acquisition_thread_function_btn.clicked.connect(self.start_acquisition_thread_function)
        self.stop_acquisition_btn = QPushButton("Stop Stack Acquisition")
        self.stop_acquisition_btn.clicked.connect(self.stop_acquisition)
        self.stop_acquisition_btn.setDisabled(True) #disable the stop command, only enabled during stack acquisition

        self.save_image_btn = QPushButton("Save image")
        self.save_image_btn.clicked.connect(self.save_image)

        settings_layout.addWidget(self.label_joystick)
        settings_layout.addLayout(self.joystick_layout)
        settings_layout.addLayout(x_layout)
        settings_layout.addLayout(y_layout)
        settings_layout.addLayout(z_layout)
        settings_layout.addLayout(current_layout)
        settings_layout.addLayout(acceleration_layout)
        settings_layout.addLayout(amplitude_layout)
        settings_layout.addLayout(light_house_layout)

        z_pos_layout = QHBoxLayout()
        z_pos_layout.addWidget(self.z_max_label)
        z_pos_layout.addWidget(self.z_max_btn)
        z_pos_layout.addWidget(self.z_min_label)
        z_pos_layout.addWidget(self.z_min_btn)
        z_pos_layout.addWidget(self.z_step_label)
        z_pos_layout.addWidget(self.z_step_text)

        settings_layout.addLayout(z_pos_layout)
        settings_layout.addWidget(self.set_encoders_to_zero_btn)
        settings_layout.addWidget(self.acquisition_thread_function_btn)
        settings_layout.addWidget(self.stop_acquisition_btn)
        settings_layout.addWidget(self.save_image_btn)

        main_layout.addWidget(settings_widget)
        main_layout.addWidget(self.canvas, stretch=3)  # Make the canvas stretch

        #prepare the status bar components
        self.create_status_bar()

        #start the position indicator thread
        self.stage_position = np.zeros(3) #initialize the stage position array with zeros
        self.position_update_stop_event = threading.Event()
        self.position_update_thread = threading.Thread(target=self.update_position_indicator, args=(self.position_update_stop_event, "message"), daemon=True)
        self.position_update_thread.start()

        self.start_lens_live_update_thread(only_create=True)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    

    def update_exposure_time(self):
        try:
            exposure_time = int(self.exposure_input.text())
            self.exposure_time = exposure_time
            self.cam.sdk.set_delay_exposure_time(0, 'ms', exposure_time, 'ms')
        except ValueError:
            print("Invalid exposure time")

    def fire_canvas_update_thread(self):
        self.canvas_update_thread = threading.Thread(target=self.update_canvas)
        self.canvas_update_thread.start()
        
    def get_image_from_camera(self): #todo fill and use that function
        image_data, image_metadata = self.cam.image()
        return image_data, image_metadata

    def canvas_update_timer_thread(self, stop_event, message):
        #print("canvas thread started")
        self.cam.sdk.set_recording_state('off')
        self.cam.sdk.set_trigger_mode('auto sequence') # change from auto sequence to fifo
        self.cam.sdk.set_delay_exposure_time(0, 'ms', self.exposure_time, 'ms')
        self.cam.record(4, mode="fifo")
        self.cam.wait_for_first_image()
        
        while not stop_event.is_set():
            self.cam.wait_for_new_image(delay=True, timeout=15)
            self.image_data, self.image_metadata = self.get_image_from_camera()
            self.update_canvas(self.image_data)
            
    
    def update_canvas(self, img, frame_index = 0):
        self.canvas.setImage(img)
        if not frame_index == 0:
            self.canvas.setCurrentIndex(frame_index)
        
        #print("updating canvas")

    def closeEvent(self, event):
        self.configData.saveConfig(default_config_file_path) #save the config changes to file
        try:
            event.accept()
            self.lens_live_update_stop_event.set()
            self.canvas_timer_stop_event.set()
            self.position_update_stop_event.set()
            self.cam.stop()
            self.cam.close()
            self.controller_mcm.close()
            self.arduino.close()
        except:
            print("some processes could not be closed properly")

    def save_image(self):

        self.cam.wait_for_first_image()

        img, meta = self.cam.image()
       
        # Convert to uint16
        grayscale_image_uint16 = img.astype(np.uint16) #done: check if img.astype is neccessary or clipping the data: no clipping, it is neccessary, otherwhise the tiff image will be 32bit float

        # Save the image
        image_path = f"image.tif"
        imwrite(image_path, grayscale_image_uint16)


    def create_slider_with_text(self, label, min_val, max_val, default_val, callback, channel=None):
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default_val)
        slider.setTickPosition(QSlider.TicksBelow)

        text_box = QLineEdit(str(default_val))
        text_box.setFixedWidth(40)
        text_box.setAlignment(Qt.AlignCenter)

        hbox = QHBoxLayout()
        hbox.addWidget(QLabel(label))
        hbox.addWidget(slider)
        hbox.addWidget(text_box)

        slider.valueChanged.connect(lambda value, text_box=text_box: self.update_text_box_from_slider(value, text_box))
        text_box.textChanged.connect(lambda text, slider=slider, min_val=min_val, max_val=max_val: self.update_slider_from_text_box(text, slider, min_val, max_val))

        if channel is not None:
            slider.sliderReleased.connect(lambda: callback(channel, slider.value()))
            text_box.editingFinished.connect(lambda: callback(channel, slider.value()))
        else:
            slider.sliderReleased.connect(lambda: callback(slider.value()))
            text_box.editingFinished.connect(lambda: callback(slider.value()))

        return hbox, slider, text_box

    def change_optotune_diopter(self, value):
        actualValue = 1.0*value/1000
        optoTuneThread = threading.Thread(target=self.lens.set_diopter, args=([actualValue]))
        optoTuneThread.start()

    def change_optotune_diopter_blocking(self, new_diopter_value):
        
        self.current_slider.setValue(math.floor(new_diopter_value*1000)) #change lens diopter in slider
        self.current_text.setText(str(math.floor(new_diopter_value*1000))) #change lens diopter in slider text
        self.lens.set_diopter(new_diopter_value) #change lens diopter but make it blocking

    def send_acc_serial_command(self, value):
        command = "a?" + str(value)
        self.arduino.write(bytes(command, 'utf-8'))
        time.sleep(0.5)

    def send_width_serial_command(self, value):
        command = "w?" + str(value)
        self.arduino.write(bytes(command, 'utf-8'))
        time.sleep(0.5)

    def update_text_box_from_slider(self, value, text_box):
        text_box.setText(str(value))

    def update_slider_from_text_box(self, text, slider, min_val, max_val):
        try:
            value = int(text)
            if value < min_val:
                value = min_val
            elif value > max_val:
                value = max_val
            slider.setValue(value)
        except ValueError:
            pass

    def update_ui_elements(self, channel, value):
        if channel == 0:
            new_value = value + int(self.x_text.text())
            self.x_text.setText(str(new_value))
            self.x_slider.setValue(new_value)
        elif channel == 1:
            new_value = value + int(self.y_text.text())
            self.y_text.setText(str(new_value))
            self.y_slider.setValue(new_value)
        elif channel == 2:
            new_value = value + int(self.z_text.text())
            self.z_text.setText(str(new_value))
            self.z_slider.setValue(new_value)

    def create_control_buttons(self):
        self.joystick_layout = QGridLayout()

        up_button = QPushButton('X↑')
        up_button.clicked.connect(lambda: self.move_stage_2(0, 1))

        down_button = QPushButton('X↓')
        down_button.clicked.connect(lambda: self.move_stage_2(0, -1))

        left_button = QPushButton('←Y')
        left_button.clicked.connect(lambda: self.move_stage_2(1, -1))

        right_button = QPushButton('Y→')
        right_button.clicked.connect(lambda: self.move_stage_2(1, 1))

        self.joystick_layout.addWidget(up_button, 0, 1)
        self.joystick_layout.addWidget(left_button, 1, 0)
        self.joystick_layout.addWidget(right_button, 1, 2)
        self.joystick_layout.addWidget(down_button, 2, 1)

        z_up_button = QPushButton('Z↑')
        z_up_button.clicked.connect(lambda: self.move_stage_2(2, 1))

        z_down_button = QPushButton('Z↓')
        z_down_button.clicked.connect(lambda: self.move_stage_2(2, -1))

        self.joystick_layout.addWidget(z_up_button, 0, 3)
        self.joystick_layout.addWidget(z_down_button, 2, 3)

    def move_stage(self, channel, value, blocking = False):
        if not(blocking):
            MoveStageThread1 = threading.Thread(target=self.controller_mcm.move_um, args=(channel, value, False)) #is this really non-blocking?
            MoveStageThread1.start()
        else:
            self.controller_mcm.move_um(channel,value,False)

    def move_stage_2(self, channel, direction):
        move_value = self.configData.configs["default_um_btn_move"] * direction
        MoveStageThread2 = threading.Thread(target=self.controller_mcm.move_um, args=(channel, self.configData.configs["default_um_btn_move"] * direction, True))
        MoveStageThread2.start()
        self.update_ui_elements(channel, move_value)

    def send_command_arduino(self, command):
        self.arduino.write(bytes(command, 'utf-8'))
        time.sleep(0.5)

    def start_lens_live_update_thread(self, only_create = False):
        print("createing lens adaption thread")
        self.lens_live_update_stop_event = threading.Event()
        self.lens_live_update_thread = threading.Thread(target=self.lens_live_update_thread_function, args=(self.lens_live_update_stop_event, "message"), daemon=True)
        if not only_create:
            self.lens_live_update_thread.start()
            print("starting lens adaption")

    def get_Lens_calib_point(self):
        if ((self.lensCalib[0,0]+self.lensCalib[0,1])==0): # check if first row of the matrix has already been filled with data
            targetRow = 0
        else:
            targetRow = 1
        
        self.lensCalib[targetRow,0] = self.controller_mcm.get_position_um(2)   # get current Z position and save it in lens calib matrix
        self.lensCalib[targetRow,1] = self.lens.get_diopter() # get current lens diopter and save it to the calib matrix
        
        if targetRow == 0:
            self.set_calibration_status_indicator(1) # set calib indicator to yellow once one line is filled
            self.clear_Lens_calib_btn.setDisabled(False)# enable the clear calibration button

        if targetRow == 1:
            self.bLensCalibrated = True # set the calibration flag to be true once two point calibration has been performed
            self.set_calibration_status_indicator(2) # set calib idicator to green once both lines are filled
            self.get_Lens_calib_point_btn.setDisabled(True) # disable the get calibration point button
            self.lens_calibration_line_coefficients = np.polyfit(self.lensCalib[:,0],self.lensCalib[:,1],1)
            print("".join(str(self.lens_calibration_line_coefficients)))
            self.start_lens_live_update_thread(only_create=False)
            self.current_slider.setDisabled(True)
            self.current_text.setDisabled(True)

    def get_lens_diopter_according_to_calibration(self, bFromStage = True):

        if bFromStage:
            current_z_pos = self.controller_mcm.get_position_um(2) #get actual position from controller
        else:
            current_z_pos = self.stage_position[2] #get actual position from position tracking variable

        resulting_diopter = (self.lens_calibration_line_coefficients[0]*current_z_pos)+self.lens_calibration_line_coefficients[1]
        return resulting_diopter

    def lens_live_update_thread_function(self, stop_event, message):
        # this function periodically checks if the stage has moved in Z and if so, adapts the optotune lens focus
        current_z_pos = 0
        while not stop_event.is_set():
            if not (current_z_pos == self.stage_position[2]):
                current_z_pos = self.stage_position[2]
                newDiopter = self.get_lens_diopter_according_to_calibration(bFromStage=False)
                self.change_optotune_diopter_blocking(newDiopter)
        time.sleep(self.configData.configs["default_lens_live_update_delay"]) # pause before redoing the lens refresh check


    def set_calibration_status_indicator(self, state):
        match state:
            case 0:
                print("lens uncalibrated")
                self.calib_led_indicator.setStyleSheet("border : 2px solid black; background-color : red")
            case 1:
                print("lens calibrating")
                self.calib_led_indicator.setStyleSheet("border : 2px solid black; background-color : yellow")
            case 2:
                print("lens calibrated")
                self.calib_led_indicator.setStyleSheet("border : 2px solid black; background-color : green")


    def clear_Lens_calib(self):  
        self.lensCalib = np.zeros((2,2)) #reset lens calib to 0,0;0,0
        self.bLensCalibrated = False # reset calibration flag to false
        self.set_calibration_status_indicator(0) # reset calib indicator to uncalibrated
        self.get_Lens_calib_point_btn.setDisabled(False) # re-enable the get calibration point button
        self.clear_Lens_calib_btn.setDisabled(True) # disable the clear calibration button
        self.lens_live_update_stop_event.set() #stop the lens position update thread
        self.current_slider.setDisabled(False)
        self.current_text.setDisabled(False)
        


    def set_z_position(self, position_type):
        current_z_position = self.z_slider.value()
        if position_type == 'max':
            self.z_max_label.setText(f'Z-Max: {current_z_position}')
        elif position_type == 'min':
            self.z_min_label.setText(f'Z-Min: {current_z_position}')

    def start_acquisition_thread_function(self):
        self.acquisition_thread_stop_event = threading.Event()
        self.acquisition_thread = threading.Thread(target=self.acquisition_thread_function, args=(self.acquisition_thread_stop_event, "message"), daemon=True)
        self.acquisition_thread.start()

    def acquisition_thread_function(self, stop_event, message):
        try:
            z_min = int(self.z_min_label.text().split(": ")[1])
            z_max = int(self.z_max_label.text().split(": ")[1])
            z_step = int(self.z_step_text.text())
        except ValueError:
            print("Invalid Z values or Z step")
            return

        self.acquisition_thread_function_btn.setDisabled(True) #disable stack acquisition button to avoid double clicking
        self.acquisition_running = True
        self.send_command_arduino("s?")

        self.stop_acquisition_btn.setDisabled(False) # enable the stop stack acquisition button

        # Stop the live actuisition
        self.stop_live_acquisition
        # Disable the live-view controls
        self.set_disable_live_view_controls(True)
        
        self.cam.sdk.set_delay_exposure_time(0, 'ms', self.exposure_time, 'ms')

        self.image_stack_data = np.zeros(((math.floor((z_max + z_step- z_min)/z_step)),self.configData.configs["default_cam_pix_x"],self.configData.configs["default_cam_pix_y"]))
        #imageData = np.random.randint(default_vMax, size=(2048,2048))
        #self.image_stack_data = self.image_stack_data.astype(np.uint16)
        
        i = 0
        for z in range(z_min, z_max + z_step, z_step):
            if stop_event.is_set():
                print("aborting acquisiton")
                break
            self.move_stage(2, z, True)  # here I move the stage and block the following commands
            if not z == z_min:
                self.update_ui_elements(2, z_step)
                #print("moving")
            
            if self.bLensCalibrated:
                self.focus_interpolation()
                #print("refocusing")

            # Get a single image
            
            self.cam.record()
            
            self.image_data, self.image_metadata = self.get_image_from_camera()

            self.image_stack_data[i,:,:] = self.image_data

            

            #print("taking image")

            self.update_canvas(self.image_stack_data, frame_index = i)


            # Convert to uint16
            grayscale_image_uint16 = self.image_data.astype(np.uint16)
            #print("svaing image")
            
            # Save the image
            image_path = f"image_{z}.tif"
            imwrite(image_path, grayscale_image_uint16)
            i = i+ 1

        # Pause stepper motor 
        self.send_command_arduino("p?") #todo: check if this is sensible or neccessary
        
        # Re-enable the live-view controls
        self.set_disable_live_view_controls(False)
        self.stop_acquisition_btn.setDisabled(True) # disable the stop stack acquisition button
        self.acquisition_thread_function_btn.setDisabled(False) #re-enable the stack acquisition start button
        
    def stop_acquisition(self):
        self.acquisition_thread_stop_event.set()
        self.send_command_arduino("h?")
    
    def init_live_acquisition(self):
        
        self.start_live_view_btn.setDisabled(True) #disable start button to inhibit double clicking
        
        # moved into the thread
        
        self.canvas_timer_stop_event = threading.Event()
        self.canvas_timer = threading.Thread(target=self.canvas_update_timer_thread, args=(self.canvas_timer_stop_event, "message"), daemon=True)
        self.canvas_timer.start()

        self.stop_live_view_btn.setDisabled(False) #enable stop button
        self.acquisition_thread_function_btn.setDisabled(True) #disable stack acquisition button
        
        
    def stop_live_acquisition(self):
        self.stop_live_view_btn.setDisabled(True) #immediately disable button to inhibit double clicking
        self.canvas_timer_stop_event.set()
        self.cam.stop()
        self.start_live_view_btn.setDisabled(False) #enable start button
        self.acquisition_thread_function_btn.setDisabled(False) #enable stack acquisition button
        
    def set_disable_live_view_controls(self, bDisabled):
        # Disables the live-view controls re-enables them
        if bDisabled:
            self.start_live_view_btn.setDisabled(True)
            self.stop_live_view_btn.setDisabled(True)
        else:
            self.start_live_view_btn.setDisabled(False)
            self.stop_live_view_btn.setDisabled(True)


    def focus_interpolation(self):
        
        new_diopter_value = self.get_lens_diopter_according_to_calibration()
        #print(new_diopter_value)
        if (new_diopter_value>self.configData.configs["lens_max_diopter"]):
            new_diopter_value=self.configData.configs["lens_max_diopter"]
        if (new_diopter_value<self.configData.configs["lens_min_diopter"]):
            new_diopter_value=self.self.configData.configs["lens_min_diopter"]
        
        self.change_optotune_diopter_blocking(new_diopter_value)
        
        #print("optotune lens focus changed")
        #print(str(self.lens.get_diopter()))

    def set_encoders_to_zero(self):
        for channel in range(3):
            self.controller_mcm._set_encoder_counts_to_zero(channel)
        self.x_text.setText(str(0))
        self.x_slider.setValue(0)
        self.y_text.setText(str(0))
        self.y_slider.setValue(0)
        self.z_text.setText(str(0))
        self.z_slider.setValue(0)

    
    def create_status_bar(self):
        self.calib_led_indicator = QPushButton()
        self.calib_led_indicator.setStyleSheet("border : 2px solid black; background-color : red")
        self.calib_led_indicator.setDisabled(True)
        self.status_bar = QStatusBar()
        #self.status_bar.setStyleSheet("border: 1px solid black")
        self.status_bar.addPermanentWidget(QLabel("Lens calibration status: "))
        self.status_bar.addPermanentWidget(self.calib_led_indicator)

        self.status_bar.addPermanentWidget(QLabel("Current stage position: "))
        
        
        self.status_bar.addPermanentWidget(QLabel("X="))
        self.position_indicator_X = QLabel("0 ")
        self.status_bar.addPermanentWidget(self.position_indicator_X) 
        self.status_bar.addPermanentWidget(QLabel("Y="))
        self.position_indicator_Y = QLabel("0 ")
        self.status_bar.addPermanentWidget(self.position_indicator_Y) 
        self.status_bar.addPermanentWidget(QLabel("Z="))
        self.position_indicator_Z = QLabel("0 ")
        self.status_bar.addPermanentWidget(self.position_indicator_Z) 
        self.status_bar.addPermanentWidget(QLabel(""),1) #this is a buffer to align content to the left
        #self.status_bar.setStyleSheet("border :1px solid black")
        self.setStatusBar(self.status_bar)
        #self.statusBar().setStyleSheet("border :1px solid black")
        #self.statusBar

    def update_position_indicator(self, stop_event, message):
        
        while not stop_event.is_set():
            #fill stage position array with current positions
            self.stage_position[0] = self.controller_mcm.get_position_um(0)
            self.stage_position[1] = self.controller_mcm.get_position_um(1)
            self.stage_position[2] = self.controller_mcm.get_position_um(2)

            #display current positions
            self.position_indicator_X.setText("{:005.0f}".format(self.stage_position[0]))
            self.position_indicator_Y.setText("{:005.0f}".format(self.stage_position[1]))
            self.position_indicator_Z.setText("{:005.0f}".format(self.stage_position[2]))

            #wait a while to refresh the thread
            time.sleep(self.configData.configs["default_position_update_delay"])
    

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MicroscopeControlGUI()
    window.show()
    sys.exit(app.exec_())