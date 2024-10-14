#include "motor.h"

TMC2130Stepper driver_stepper = TMC2130Stepper(EN_PIN, DIR_PIN, STEP_PIN, CS_PIN);
AccelStepper stepper = AccelStepper(stepper.DRIVER, STEP_PIN, DIR_PIN);

bool dir = true;
int sheet_width = 30;
long headAcceleration = 1000;

void init_motor() {
    
    pinMode(CS_PIN, OUTPUT);
    digitalWrite(CS_PIN, HIGH);
   
    driver_stepper.begin();           
    driver_stepper.rms_current(600);    // Set stepper current to 600mA
    driver_stepper.stealthChop(1);      // Enable extremely quiet stepping
    driver_stepper.stealth_autoscale(1);
    driver_stepper.microsteps(32);      // every microstep is 0,056°, if r=10cm -> every microstep is around 0,1 mm
    driver_stepper.high_speed_mode(1);

    stepper.setMaxSpeed(MAX_SCAN_SPEED);
    stepper.setAcceleration(headAcceleration); 
    stepper.setEnablePin(EN_PIN);
    stepper.setPinsInverted(false, false, true);
}

void task_move_motor(void *pvParameters) {
  command_t received_command;
  bool first_move = true;
  bool allow_oscilation = false;

  while(1)
  {
    // If there is an element in the queue...
    if(x_received_commands_queue != NULL && xQueueReceive(x_received_commands_queue, (void *)&received_command, 0) == pdTRUE){
      if(received_command.command == "w"){ // change width
        sheet_width = received_command.value;
      }else if (received_command.command == "a"){ // Change amplitude
        stepper.setAcceleration(received_command.value); 
      }else if(received_command.command == "s"){  // Start the stepper motor oscilation
        stepper.enableOutputs();
        stepper.setCurrentPosition(0);
        allow_oscilation = true;
        first_move = true;
      }else if(received_command.command == "p"){  // Pause the stepper motor oscilation
        stepper.moveTo(0);
        allow_oscilation = false;
      }else if(received_command.command == "h"){  // Stop the stepper motor oscilation
        stepper.moveTo(0);
        stepper.disableOutputs();
        stepper.stop();
        allow_oscilation = false;
      }else if(received_command.command == "r"){  // Move a microstep to the right
        stepper.enableOutputs();
        stepper.move(-1);
      }else if(received_command.command == "l"){  // Move a microstep to the left
        stepper.enableOutputs();
        stepper.move(1);        
      }
      
    }


    if(allow_oscilation){
      if (stepper.distanceToGo() == 0) {
        if (first_move){
          stepper.moveTo(sheet_width/2);
          first_move = false;
        }
        else if (dir){
          stepper.moveTo(sheet_width);  
        }else{
          stepper.moveTo(-1*sheet_width);
        }
        dir = !dir;
      }
    }
    
    stepper.run();
    
    vTaskDelay(1/ portTICK_PERIOD_MS);
  }
  
}