#pragma once
#include <Arduino_FreeRTOS.h>
#include <TMC2130Stepper.h>
#include <AccelStepper.h>

#define EN_PIN    7  
#define DIR_PIN   8  
#define STEP_PIN  9  
#define CS_PIN    10 
#define SCAN_SPEED 8000

extern int sheetWidth;
extern long headAcceleration;

void init_motor();
void task_move_motor(void *pvParameters);