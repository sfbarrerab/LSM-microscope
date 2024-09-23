# LSM microscope hardware controller 

This github will include the necessary software to control the different components of the LSM setup

## Environment

In order to use the software it is recommended to crate a virtual environment (you need to install python beforehand :snake:). You can create the virtual environment running the next command `python -m venv lsm_env`.

To activate the environment, open a console in the path were you clone the repository and run the command `.\lsm_env\Scripts\activate` 

If the environment is properly activated you will see the name of the environment before the path in the command line (example bellow)

![Activate venv](images_readme/activate_env.png)

If you got this error, 

![error activate venv](images_readme/error_venv.PNG)

Run the command `Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force` and try to activate the environment again.

Once you are in the environment, you will need to install the required libraries. These libraries are in the requirements.txt file. You can install them running the command `pip install -r requirements.txt`. It can take some minutes, so grab a coffee in the meanwhile :coffee: :smile:

To deactivate the environment and return to the global Python environment, simply use the `deactivate` command.

## Hardware

The software of the LSM controll the following modules:

- Thorlabs XYZ stage MCM3001
- Optotune Lens EL-16-40-TC (Lense Driver 4i)
- PCO CMOS Edge 4.2 SUB camera
- [JSS-step motor 42HS series](https://www.jss-motor.com/product/nema17-42HS-2-phase-1-8%C2%B0-hybrid-stepper-motor.html) (through an arduino UNO and silent step driver TMC2130 V2)

![Pinout step motor driver](images_readme/silent_step_pinout.PNG)

## Known bugs

The GUI is going to froze when you try to move the motor in a position out of the range of the motor.