import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QLineEdit, QGridLayout, QMainWindow, QStatusBar
from PyQt5.QtGui import QIntValidator
from PyQt5.QtCore import Qt, QTimer, QMetaObject
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

default_um_btn_move = 10

class MplCanvas(FigureCanvas):
    def __init__(self):
        self.fig, self.ax = plt.subplots()
        self.img_plot = self.ax.imshow(np.zeros((2048, 2048)), cmap='gray', norm=Normalize(vmin=0, vmax=255))
        self.ax.set_ylim(0, 2048)
        self.ax.set_xlim(0, 2048)
        super().__init__(self.fig)

class MicroscopeControlGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize components
        self.controller_mcm = mc.Controller(which_port='COM4',
                                        stages=('ZFM2020', 'ZFM2020', 'ZFM2020'),
                                        reverse=(False, False, False),
                                        verbose=True,
                                        very_verbose=False)
        for channel in range(3):
            self.controller_mcm._set_encoder_counts_to_zero(channel)

        self.lens = Lens('COM5', debug=False)
        self.cam = pco.Camera(interface="USB 3.0")
        self.arduino = serial.Serial(port="COM6", baudrate=115200, timeout=1)

        # optotune calibration variables
        self.lens_calib = np.zeros((2,2))
        self.calibration_status = 0
        self.c1_linear_regresion = 0
        self.c2_linear_regresion = 0

        self.initUI()

    def initUI(self):
        self.setWindowTitle('LSM Control')

        # Create the canvas for the camera
        self.canvas = MplCanvas()

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
        self.exposure_input = QLineEdit("10")
        self.exposure_input.returnPressed.connect(self.update_exposure_time)
        exposure_layout.addWidget(exposure_label)
        exposure_layout.addWidget(self.exposure_input)

        # Add vmin input
        vmin_layout = QHBoxLayout()
        vmin_label = QLabel("vmin:")
        self.vmin_input = QLineEdit("0")
        self.vmin_input.returnPressed.connect(self.update_vmin_vmax)
        vmin_layout.addWidget(vmin_label)
        vmin_layout.addWidget(self.vmin_input)

        # Add vmax input
        vmax_layout = QHBoxLayout()
        vmax_label = QLabel("vmax:")
        self.vmax_input = QLineEdit("255")
        self.vmax_input.returnPressed.connect(self.update_vmin_vmax)
        vmax_layout.addWidget(vmax_label)
        vmax_layout.addWidget(self.vmax_input)

        # Add the exposure and min/max controls to the settings layout
        settings_layout.addLayout(exposure_layout)
        settings_layout.addLayout(vmin_layout)
        settings_layout.addLayout(vmax_layout)

        # Label um step fixed size
        self.label_joystick = QLabel('10 um steps for sample stage')
        self.create_control_buttons()

        # Camera plot thorugh a canvas
        self.timer_plot_camera = QTimer()
        self.timer_plot_camera.timeout.connect(self.update_canvas)

        self.init_live_acquisition()
     
        # Sliders stage
        x_layout, self.x_slider, self.x_text = self.create_slider_with_text('X Position (um)', -10000, 10000, 0, self.move_stage, channel=0)
        y_layout, self.y_slider, self.y_text = self.create_slider_with_text('Y Position (um)', -10000, 10000, 0, self.move_stage, channel=1)
        z_layout, self.z_slider, self.z_text = self.create_slider_with_text('Z Position (um)', -10000, 10000, 0, self.move_stage, channel=2)

        # Sliders optotune lens and arduino stepper motor
        mili_diopter_layout, self.diopter_slider, self.diopter_text = self.create_slider_with_text('mili Diopter', -500, 500, 0, self.change_optotune_diopter)
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

        # Optotune calibration btns
        self.get_lens_calib_point_btn = QPushButton("Get Lens Calibration Point")
        self.get_lens_calib_point_btn.clicked.connect(self.get_lens_calib_point)

        self.clear_lens_calib_btn = QPushButton("Clear Lens Calibration")
        self.clear_lens_calib_btn.clicked.connect(self.clear_lens_calib)
        self.clear_lens_calib_btn.setDisabled(True)

        # Create status bar
        self.create_status_bar() 


        light_house_layout = QGridLayout()
        light_house_layout.addWidget(self.pause_stepper_motor_btn, 0, 0)
        light_house_layout.addWidget(self.start_stepper_motor_btn, 0, 1)
        light_house_layout.addWidget(self.move_ccw_stepper_motor_btn,1,0)
        light_house_layout.addWidget(self.move_cw_stepper_motor_btn,1,1)
        light_house_layout.addWidget(self.stop_stepper_motor_btn)
        light_house_layout.addWidget(self.get_lens_calib_point_btn,3,0)
        light_house_layout.addWidget(self.clear_lens_calib_btn,3,1)

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

        self.set_encoders_to_cero_btn = QPushButton("Set to cero encoders sample stage")
        self.set_encoders_to_cero_btn.clicked.connect(self.set_encoders_to_cero)
        self.start_acquisition_btn = QPushButton("Start Stack Acquisition")
        self.start_acquisition_btn.clicked.connect(self.start_acquisition)
        self.stop_acquisition_btn = QPushButton("Stop Stack Acquisition")
        self.stop_acquisition_btn.clicked.connect(self.stop_acquisition)

        self.save_image_btn = QPushButton("Save image")
        self.save_image_btn.clicked.connect(self.save_image)

        settings_layout.addWidget(self.label_joystick)
        settings_layout.addLayout(self.joystick_layout)
        settings_layout.addLayout(x_layout)
        settings_layout.addLayout(y_layout)
        settings_layout.addLayout(z_layout)
        settings_layout.addLayout(mili_diopter_layout)
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
        settings_layout.addWidget(self.set_encoders_to_cero_btn)
        settings_layout.addWidget(self.start_acquisition_btn)
        settings_layout.addWidget(self.stop_acquisition_btn)
        settings_layout.addWidget(self.save_image_btn)

        main_layout.addWidget(settings_widget)
        main_layout.addWidget(self.canvas, stretch=3)  # Make the canvas stretch

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def update_exposure_time(self):
        try:
            exposure_time = int(self.exposure_input.text())
            self.cam.sdk.set_delay_exposure_time(0, 'ms', exposure_time, 'ms')
        except ValueError:
            print("Invalid exposure time")

    def update_vmin_vmax(self):
        try:
            vmin = int(self.vmin_input.text())
            vmax = int(self.vmax_input.text())
            self.canvas.img_plot.set_norm(Normalize(vmin=vmin, vmax=vmax))
            self.canvas.draw()
        except ValueError:
            print("Invalid vmin or vmax")

    def update_canvas(self):
        img, meta = self.cam.image()
        self.canvas.img_plot.set_array(img)
        self.canvas.draw()

    def closeEvent(self, event):
        event.accept()
        self.timer_plot_camera.stop()
        self.cam.stop()
        self.cam.close()
        self.controller_mcm.close()
        self.arduino.close()

    def save_image(self):

        self.cam.wait_for_first_image()

        img, meta = self.cam.image()
        img = img.reshape((2048, 2048))
        

        # Apply the vmin and vmax normalization
        img_normalized = np.clip(img, int(self.vmin_input.text()), int(self.vmax_input.text()))

        # Scale the image to the range of uint16 (0 to 65535)
        img_scaled = (img_normalized - img_normalized.min()) / (img_normalized.max() - img_normalized.min()) * 65535

        # Convert to uint16
        grayscale_image_uint16 = img_scaled.astype(np.uint16)

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

    def change_optotune_diopter(self, value, blocking = False):
        if blocking == True:
            self.lens.set_diopter((float)(value/1000.0))
        else:
            thread = threading.Thread(target=self.lens.set_diopter, args=([(float)(value/1000.0)]))
            thread.start()
        print("Diopter set to: ", value)

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

    def update_xyz_ui_elements(self, channel, value):
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
        up_button.clicked.connect(lambda: self.move_stage_with_btns(0, 1))

        down_button = QPushButton('X↓')
        down_button.clicked.connect(lambda: self.move_stage_with_btns(0, -1))

        left_button = QPushButton('←Y')
        left_button.clicked.connect(lambda: self.move_stage_with_btns(1, -1))

        right_button = QPushButton('Y→')
        right_button.clicked.connect(lambda: self.move_stage_with_btns(1, 1))

        self.joystick_layout.addWidget(up_button, 0, 1)
        self.joystick_layout.addWidget(left_button, 1, 0)
        self.joystick_layout.addWidget(right_button, 1, 2)
        self.joystick_layout.addWidget(down_button, 2, 1)

        z_up_button = QPushButton('Z↑')
        z_up_button.clicked.connect(lambda: self.move_stage_with_btns(2, 1))

        z_down_button = QPushButton('Z↓')
        z_down_button.clicked.connect(lambda: self.move_stage_with_btns(2, -1))

        self.joystick_layout.addWidget(z_up_button, 0, 3)
        self.joystick_layout.addWidget(z_down_button, 2, 3)

    def move_stage(self, channel, value, blocking = False):
        if not(blocking):
            thread = threading.Thread(target=self.controller_mcm.move_um, args=(channel, value, False))
            thread.start()
        else:
            self.controller_mcm.move_um(channel,value,False)

    def move_stage_with_btns(self, channel, direction):
        move_value = default_um_btn_move * direction
        thread = threading.Thread(target=self.controller_mcm.move_um, args=(channel, default_um_btn_move * direction, True))
        thread.start()
        self.update_xyz_ui_elements(channel, move_value)

    def send_command_arduino(self, command):
        self.arduino.write(bytes(command, 'utf-8'))
        time.sleep(0.5)

    def set_z_position(self, position_type):
        current_z_position = self.z_slider.value()
        if position_type == 'max':
            self.z_max_label.setText(f'Z-Max: {current_z_position}')
        elif position_type == 'min':
            self.z_min_label.setText(f'Z-Min: {current_z_position}')

    def start_acquisition(self):
        try:
            z_min = int(self.z_min_label.text().split(": ")[1])
            z_max = int(self.z_max_label.text().split(": ")[1])
            z_step = int(self.z_step_text.text())
        except ValueError:
            print("Invalid Z values or Z step")
            return
        
        if self.calibration_status != 2:
            print("Optotune calibration is not completed")
            return
        
        # get the coefficientes of the linear regression
        self.linear_interpolation_optotune()

        self.run_acquisition = True
        #self.send_command_arduino("s?")

        # Stop the function that update the canvas
        self.timer_plot_camera.stop()

        # stop the previous recorder and init a new one
        self.cam.stop()

        for z in range(z_min, z_max + z_step, z_step):
            # Stop if the "stop acquisition" btn is pressed
            if not self.run_acquisition:
                break
            # Move the stage and block the following commands until the movement finish
            self.move_stage(2, z, True) 

            # Update the gui elements until we reach the last position 
            if not z == z_min:
                self.update_xyz_ui_elements(2, z_step)

            # get the diopter value for the new z position
            diopter_value = self.focus_interpolation(z)
            
            # Adjust the diopter, block the rest to get the right image
            self.change_optotune_diopter(diopter_value,blocking=True)

            # Get a single image
            self.cam.sdk.set_delay_exposure_time(0, 'ms', int(self.exposure_input.text()), 'ms')
            self.cam.record()
            
            img, meta = self.cam.image()

            # plot the image in the gui
            self.canvas.img_plot.set_array(img)
            self.canvas.draw()

            # Adjust and store the image
            img = img.reshape((2048, 2048))
            
            # Apply the vmin and vmax normalization
            img_normalized = np.clip(img, int(self.vmin_input.text()), int(self.vmax_input.text()))

            # Scale the image to the range of uint16 (0 to 65535)
            img_scaled = (img_normalized - img_normalized.min()) / (img_normalized.max() - img_normalized.min()) * 65535

            # Convert to uint16
            grayscale_image_uint16 = img_scaled.astype(np.uint16)

            # Save the image
            image_path = f"image_{z}.tif"
            imwrite(image_path, grayscale_image_uint16)

        # Pause stepper motor
        self.send_command_arduino("p?")
        # Restart live acquisition
        self.init_live_acquisition()


    def stop_acquisition(self):
        self.run_acquisition = False
        self.send_command_arduino("h?")
    
    def init_live_acquisition(self):
        self.cam.sdk.set_recording_state('off')
        self.cam.sdk.set_trigger_mode('auto sequence')
        self.cam.sdk.set_delay_exposure_time(0, 'ms', int(self.exposure_input.text()), 'ms')
        self.cam.record(4, mode="ring buffer")
        self.cam.wait_for_first_image()
        # 10 fps
        self.timer_plot_camera.start(100)


    # Got the right diopter value for the given z position according to the linear regression
    def focus_interpolation(self,z):
        diopter_value_mili = (self.c1_linear_regresion*z + self.c2_linear_regresion)*1000
        return diopter_value_mili

    def set_encoders_to_cero(self):
        for channel in range(3):
            self.controller_mcm._set_encoder_counts_to_zero(channel)
        self.x_text.setText(str(0))
        self.x_slider.setValue(0)
        self.y_text.setText(str(0))
        self.y_slider.setValue(0)
        self.z_text.setText(str(0))
        self.z_slider.setValue(0)


    def get_lens_calib_point(self):
        # check if the matrix is empty
        if (np.sum(self.lens_calib)==0): 
            target_row = 0
            # set indicator to "calibration in process"
            self.set_calibration_status_indicator(1)
            # enable the clear calibration button
            self.clear_lens_calib_btn.setDisabled(False)
        else:
            target_row = 1
            # set indicator to "calibration completed"
            self.set_calibration_status_indicator(2)
            # disable the get calibration point button
            self.get_lens_calib_point_btn.setDisabled(True) 
        
        # get z position
        self.lens_calib[target_row,0] = self.controller_mcm.get_position_um(2)   
        self.lens_calib[target_row,1] = self.lens.get_diopter()


    def linear_interpolation_optotune(self):
        self.c1_linear_regresion, self.c2_linear_regresion = np.polyfit(self.lens_calib[:,0],self.lens_calib[:,1],1)
    
    # state = 0 => not calibrated
    # state = 1 => calibration in process
    # state = 2 => calibration completed
    def set_calibration_status_indicator(self, state):
        self.calibration_status = state
        match state:
            case 0:
                self.calib_led_indicator.setStyleSheet("border : 2px solid black; background-color : red")
            case 1:
                self.calib_led_indicator.setStyleSheet("border : 2px solid black; background-color : yellow")
            case 2:
                self.calib_led_indicator.setStyleSheet("border : 2px solid black; background-color : green")


    def clear_lens_calib(self):  
        self.lens_calib = np.zeros((2,2)) 
        # reset calib indicator to  "not calibrated"
        self.set_calibration_status_indicator(0) 
        # enable get calibration point button and disable clear calibration button
        self.get_lens_calib_point_btn.setDisabled(False) 
        self.clear_lens_calib_btn.setDisabled(True) 
    
    def create_status_bar(self):
        self.calib_led_indicator = QPushButton()
        self.calib_led_indicator.setStyleSheet("border : 2px solid black; background-color : red")
        self.status_bar = QStatusBar()
        
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
        self.setStatusBar(self.status_bar)

        

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MicroscopeControlGUI()
    window.show()
    sys.exit(app.exec_())
