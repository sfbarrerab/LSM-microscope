//*********************************** */
// The motor used is a 42HS48 which have a max 2A current
// and every step is 1,8°. This means 200 steps
//*********************************** */

#pragma once
#include <Arduino_FreeRTOS.h>
#include <TMC2130Stepper.h>
#include <AccelStepper.h>
#include "serial_comm.h"

#define EN_PIN    7  
#define DIR_PIN   8  
#define STEP_PIN  9  
#define CS_PIN    10 
#define SCAN_SPEED 1000

extern int sheet_width;
extern long headAcceleration;

void init_motor();
void task_move_motor(void *pvParameters);