import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QLineEdit, QCheckBox, QFrame
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer
import MCM300 as mc
import pco
import threading
import serial
import time
from optotune_lens import Lens
from pycromanager import Acquisition, multi_d_acquisition_events


class MicroscopeControlGUI(QWidget):
    def __init__(self):
        super().__init__()
        #Init the stage
        self.controller_mcm = mc.Controller(which_port='COM4',
                                        stages=('ZFM2020', 'ZFM2020', 'ZFM2020'),
                                        reverse=(False, False, False),
                                        verbose=True,
                                        very_verbose=False)
        #set all the counters for the stage in 0
        for channel in range(3):
            self.controller_mcm._set_encoder_counts_to_zero(channel)
        
        # Init the optotune lens
        self.lens = Lens('COM5', debug=False)
        print(self.lens.firmware_type)
        print(self.lens.firmware_version)
        print(self.lens.get_firmware_branch())
        print('Lens serial number:', self.lens.lens_serial)
        print('Lens temperature:', self.lens.get_temperature())
        self.lens.to_current_mode()

        # Init arduino serial communication
        self.arduino = serial.Serial(port="COM6", baudrate=115200, timeout=1)

        self.initUI()

    def initUI(self):
        
        self.setWindowTitle('LSM Control')

        # Sliders for velocity and position
        self.x_slider, self.x_text = self.create_slider_with_text('X Position (um)', -10000, 10000, 0, self.move_stage, channel = 0)
        self.y_slider, self.y_text = self.create_slider_with_text('Y Position (um)', -10000, 10000, 0, self.move_stage, channel = 1)
        self.z_slider, self.z_text = self.create_slider_with_text('Z Position (um)', -10000, 10000, 0, self.move_stage, channel = 2)

        # Slider for current value
        self.current_slider, self.current_text = self.create_slider_with_text('Current', -300, 300, 0, self.change_optotune_current)

        # Sliders for motor frequency and amplitude
        self.frequency_slider, self.frequency_text = self.create_slider_with_text('Acceleration', 1000, 10000, 1000, self.send_acc_serial_command)
        self.amplitude_slider, self.amplitude_text = self.create_slider_with_text('Amplitude', 50, 500, 100, self.send_width_serial_command)

        # Button for manual contrast adjustment
        self.save_stack = QPushButton('Start stack')
        self.save_stack.clicked.connect(self.manual_contrast)
        self.save_stack.clicked

        # Layout setup
        vbox = QVBoxLayout()
        vbox.addStretch(1)
        vbox.addLayout(self.x_slider)
        vbox.addLayout(self.y_slider)
        vbox.addLayout(self.z_slider)
        vbox.addLayout(self.current_slider)
        vbox.addLayout(self.frequency_slider)
        vbox.addLayout(self.amplitude_slider)
        #vbox.addLayout(self.save_stack)

        self.setLayout(vbox)

        self.show()
    
    def closeEvent(self, event):
        # This method is called when the window is closed
        # Close the camera
        self.camera.close()
        event.accept()

    def create_slider_with_text(self, label, min_val, max_val, default_val, callback, channel = None):
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

        # Update textbox and slider values if one fo them changed
        slider.valueChanged.connect(lambda value, text_box=text_box: self.update_text_box_from_slider(value, text_box))
        text_box.textChanged.connect(lambda text, slider=slider, min_val=min_val, max_val=max_val: self.update_slider_from_text_box(text, slider, min_val, max_val))
        
        # move the stage only when the slider is released or after pressing enter in the textbox (more safe)
        if channel is not None:
            slider.sliderReleased.connect(lambda: callback(channel, slider.value())) 
            text_box.editingFinished.connect(lambda: callback(channel, slider.value()))  
        else:    
            # General callback function
            slider.sliderReleased.connect(lambda: callback(slider.value())) 

        return hbox, text_box
    
    def move_stage(self, channel, value):
        thread = threading.Thread(target=self.controller_mcm.move_um, args=(channel, value))
        thread.start()

    def change_optotune_current(self,value):
        thread = threading.Thread(target=self.lens.set_current, args=([value]))
        thread.start()

    
    def send_acc_serial_command(self,value):
        command = "a?"+str(value)
        self.arduino.write(bytes(command, 'utf-8'))
        time.sleep(0.5)  

    def send_width_serial_command(self,value):
        command = "w?"+str(value)
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

    def create_text_input(self, label):
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel(label))
        hbox.addWidget(QLineEdit())

        return hbox

    def manual_contrast(self):
        # Callback for manual contrast adjustment
        pass

    def auto_contrast(self, state):
        # Callback for automatic contrast correction
        pass

    def print_values(self):
        # Print values of GUI components
        print("X Position:", self.x_text.text())
        print("Y Position:", self.y_text.text())
        print("Z Position:", self.z_text.text())
        print("Current:", self.current_text.text())
        print("Frequency:", self.frequency_text.text())
        print("Amplitude:", self.amplitude_text.text())
        print("Exposure:", self.exposure_text.itemAt(1).widget().text())
        print("Alpha:", self.alpha_text.itemAt(1).widget().text())
        print("Auto contrast:", self.auto_contrast_checkbox.isChecked())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MicroscopeControlGUI()      
    sys.exit(app.exec_())
