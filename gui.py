import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QLineEdit, QCheckBox, QFrame
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QTimer

class MicroscopeControlGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        
        # Create timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.print_values)
        self.timer.start(1000)  # Update every 1000 ms

        self.setWindowTitle('LSM Control')

        self.line_label = QLabel(self)
        self.line_label.setFrameShape(QFrame.HLine)  # Set frame shape to horizontal line
        self.line_label.setStyleSheet("QLabel { border: 2px solid black; }")
        self.line_label.setGeometry(10, 100, self.width()-10, 1)  # Set position and size of the line

        self.setWindowTitle('PyQt5 Horizontal Line Example')
        self.setGeometry(300, 300,  500, 200)



        # Image display
        self.image_label = QLabel()
        self.image_label.setFixedSize(400, 300)
        self.image_label.setAlignment(Qt.AlignCenter)

        # Sliders for velocity and position
        self.velocity_slider, self.velocity_text = self.create_slider_with_text('Velocity', -100, 100, 0)
        self.x_slider, self.x_text = self.create_slider_with_text('X Position', -100, 100, 0)
        self.y_slider, self.y_text = self.create_slider_with_text('Y Position', -100, 100, 0)
        self.z_slider, self.z_text = self.create_slider_with_text('Z Position', -100, 100, 0)

        # Slider for current value
        self.current_slider, self.current_text = self.create_slider_with_text('Current', -100, 100, 0)

        # Sliders for motor frequency and amplitude
        self.frequency_slider, self.frequency_text = self.create_slider_with_text('Frequency', -100, 100, 0)
        self.amplitude_slider, self.amplitude_text = self.create_slider_with_text('Amplitude', -100, 100, 0)

        # Text fields for manual input
        self.exposure_text = self.create_text_input('Exposure')
        self.alpha_text = self.create_text_input('Alpha')

        # Button for manual contrast adjustment
        self.contrast_button = QPushButton('Manual Contrast')
        self.contrast_button.clicked.connect(self.manual_contrast)

        # Checkbox for automatic contrast correction
        self.auto_contrast_checkbox = QCheckBox('Automatic Contrast')
        self.auto_contrast_checkbox.stateChanged.connect(self.auto_contrast)

        # Layout setup
        vbox = QVBoxLayout()
        vbox.addWidget(self.image_label)
        vbox.addStretch(1)
        vbox.addLayout(self.velocity_slider)
        vbox.addLayout(self.x_slider)
        vbox.addLayout(self.y_slider)
        vbox.addLayout(self.z_slider)
        vbox.addLayout(self.current_slider)
        vbox.addLayout(self.frequency_slider)
        vbox.addLayout(self.amplitude_slider)
        vbox.addLayout(self.exposure_text)
        vbox.addLayout(self.alpha_text)
        vbox.addWidget(self.contrast_button)
        vbox.addWidget(self.auto_contrast_checkbox)

        self.setLayout(vbox)

        self.show()

    def create_slider_with_text(self, label, min_val, max_val, default_val):
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

        return hbox, text_box

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
    
    def resizeEvent(self, event):
      # Update the line's geometry when the window is resized
      self.line_label.setGeometry(10, 100, self.width() - 10, 1)

    def print_values(self):
      # Print values of GUI components
      print("Velocity:", self.velocity_text.text())
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
