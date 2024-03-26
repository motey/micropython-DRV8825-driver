# micropython-DRV8825-driver
A micropython class to control a stepper motor with a DRV8825 driver (on a Raspberry Pico board)

> ℹ️ This is not a "official" library. Just some code i wrote for myself to learn control a stepper motors with a Raspberry Pico. Maybe it can be help you.

> :warning: I tested this with only with a Raspberry Pico and a cheap noname nema17 motor. if your setup is different your mileage may vary.

> ℹ️: This lib may be a little bit overengineered depending on your usecase. You may want to cherrypick some methods and build a slimmer lib based on this one.

- [micropython-DRV8825-driver](#micropython-drv8825-driver)
  - [Examples](#examples)
    - [synchronous methods](#synchronous-methods)
      - [synchronous example 1 - steps()](#synchronous-example-1---steps)
      - [synchronous example 2 - rotate()](#synchronous-example-2---rotate)
      - [synchronous example 3 - rotate\_while()](#synchronous-example-3---rotate_while)
    - [non blocking methods](#non-blocking-methods)
      - [non blocking example 1 - steps\_non\_blocking()](#non-blocking-example-1---steps_non_blocking)
      - [non blocking example 2 - rotate\_non\_blocking()](#non-blocking-example-2---rotate_non_blocking)
      - [non blocking example 3 - rotate\_while\_non\_blocking()](#non-blocking-example-3---rotate_while_non_blocking)
    - [asynchronous methods](#asynchronous-methods)
      - [asynchronous example 1](#asynchronous-example-1)
  - [Installation](#installation)
    - [Install typing support](#install-typing-support)
    - [local code completion in VSCode for board libs](#local-code-completion-in-vscode-for-board-libs)


## Examples

(ToDo: Add image of eletronic setup)

### synchronous methods

Synchronous mode is the most simple method to turn the stepper motor. It is straightforward, easy to understand and easy to reimplement when you just want to re-use snippets of this class.
As a blocking function is comes with some caveats:  
- The speed can vary based the work load of the microcontroller.  
- You can not do anything else until the motor movement is finished.  

#### synchronous example 1 - steps()

A very basic example, that moves the motor 100 steps counter clockwise.
The motor will run in [full step mode](https://www.youtube.com/watch?v=dmk6zIkj7WM).

```python
m = DRV8825StepperMotor(
    step_pin=Pin(4, Pin.OUT),
    direction_pin=Pin(5, Pin.OUT),
    reset_pin=Pin(2, Pin.OUT),
    sleep_pin=Pin(3, Pin.OUT),
    enable_pin=Pin(6, Pin.OUT),
    mode_pins=(Pin(7, Pin.OUT), Pin(8, Pin.OUT), Pin(9, Pin.OUT)),
)
m.steps(100, clockwise=False)
# shutoff motor
m.sleep()
```

#### synchronous example 2 - rotate()

A very basic example, that makes the motor turn 2 full revolutions in two seconds.
The motor will run in half step mode.

```python
m = DRV8825StepperMotor(
    step_pin=Pin(4, Pin.OUT),
    direction_pin=Pin(5, Pin.OUT),
    reset_pin=Pin(2, Pin.OUT),
    sleep_pin=Pin(3, Pin.OUT),
    enable_pin=Pin(6, Pin.OUT),
    mode_pins=(Pin(7, Pin.OUT), Pin(8, Pin.OUT), Pin(9, Pin.OUT)),
    mode=DRV8825StepperMotor.MODE_HALF,
    target_time_for_one_revolution_ms=1000,
)
m.rotate(2, clockwise=True)
# shutoff motor
m.sleep()
```
#### synchronous example 3 - rotate_while()

`rotate_while` will turn the motor until a provided function returns `False`.

This example makes the motor turn for 3 seconds counter clockwise with a speed of 2 revolution per sec (500ms per rotation). 
The motor will run in 1/16 stepping mode.

```python
import utime
m = DRV8825StepperMotor(
    step_pin=Pin(4, Pin.OUT),
    direction_pin=Pin(5, Pin.OUT),
    reset_pin=Pin(2, Pin.OUT),
    sleep_pin=Pin(3, Pin.OUT),
    enable_pin=Pin(6, Pin.OUT),
    mode_pins=(Pin(7, Pin.OUT), Pin(8, Pin.OUT), Pin(9, Pin.OUT)),
    mode=DRV8825StepperMotor.MODE_ONE_16,
    target_time_for_one_revolution_ms=500,
)
start_time = utime.ticks_ms()

def three_seconds_are_gone() -> bool:
    time_gone_sec = utime.ticks_diff(utime.ticks_ms(), start_time) / 1000
    if time_gone_sec > 3.0:
        return False
    return True
m.rotate_while(three_seconds_are_gone, clockwise=False)
m.sleep()
```

### non blocking methods

You can call these method to move the motor and also continue your script

#### non blocking example 1 - steps_non_blocking()

This example will make the motor do 100 steps.

```python
m = DRV8825StepperMotor(
    step_pin=Pin(4, Pin.OUT),
    direction_pin=Pin(5, Pin.OUT),
    reset_pin=Pin(2, Pin.OUT),
    sleep_pin=Pin(3, Pin.OUT),
    enable_pin=Pin(6, Pin.OUT),
    mode_pins=(Pin(7, Pin.OUT), Pin(8, Pin.OUT), Pin(9, Pin.OUT)),
    mode=DRV8825StepperMotor.MODE_HALF,
    target_time_for_one_revolution_ms=500,
)

res = m.steps_non_blocking(100,callback=None)
while not res.done:
    # you can do things here while the motor is turning
    pass
m.sleep()
```

#### non blocking example 2 - rotate_non_blocking()

This example will make the motor do one revolution. During the rotation the console will print `Do other stuff while the motor is rotating`.
When the movement is finished the console will print `Motor has done 200.0 steps in 500 ms`

```python
m = DRV8825StepperMotor(
    step_pin=Pin(4, Pin.OUT),
    direction_pin=Pin(5, Pin.OUT),
    reset_pin=Pin(2, Pin.OUT),
    sleep_pin=Pin(3, Pin.OUT),
    enable_pin=Pin(6, Pin.OUT),
    mode_pins=(Pin(7, Pin.OUT), Pin(8, Pin.OUT), Pin(9, Pin.OUT)),
    mode=DRV8825StepperMotor.MODE_HALF,
    target_time_for_one_revolution_ms=500,
)

def motor_movement_is_done(result: DRV8825StepperMotor.NonBlockResult):
    print("Hey, iam your motor and done twisting around.")
    return f"Motor has done {result.get_steps_done()} steps in {result.get_run_time_ms()} ms"

res = m.rotate_non_blocking(1, callback=motor_movement_is_done)
while not res.done:
    print("Do other stuff while the motor is rotating")
print(res.callback_result)  # <- prints: 'Motor has done 200.0 steps in 500 ms'
m.sleep()
```

#### non blocking example 3 - rotate_while_non_blocking()

This example will spin the motor until a button (on PIN 15) is pressed.
The console output can be something like `You pressed the button after 3.41 seconds. The motor did 2728.0 steps in this time`
```python
m = DRV8825StepperMotor(
    step_pin=Pin(4, Pin.OUT),
    direction_pin=Pin(5, Pin.OUT),
    reset_pin=Pin(2, Pin.OUT),
    sleep_pin=Pin(3, Pin.OUT),
    enable_pin=Pin(6, Pin.OUT),
    mode_pins=(Pin(7, Pin.OUT), Pin(8, Pin.OUT), Pin(9, Pin.OUT)),
    mode=DRV8825StepperMotor.MODE_HALF,
    target_time_for_one_revolution_ms=500,
)

button = Pin(15, Pin.IN, pull=Pin.PULL_UP)


def button_is_not_pressed():
    return bool(button.value())


res = m.rotate_while_non_blocking(button_is_not_pressed)
while not res.done:
    # you can do things here
    pass
print(
    f"You pressed the button after {res.get_run_time_ms() / 1000} seconds. The motor did {res.get_steps_done()} steps in this time"
)
m.sleep()
```

### asynchronous methods

> :warning: Async method examples are still work in progress


#### asynchronous example 1

An example, that makes the motor turn as long a the button on pin 12 is pressed.  
The motor will run in 1/16 stepping mode.

```python
import uasyncio
m = DRV8825StepperMotor(
    step_pin=Pin(4, Pin.OUT),
    direction_pin=Pin(5, Pin.OUT),
    reset_pin=Pin(2, Pin.OUT),
    sleep_pin=Pin(3, Pin.OUT),
    enable_pin=Pin(6, Pin.OUT),
    mode_pins=(Pin(7, Pin.OUT), Pin(8, Pin.OUT), Pin(9, Pin.OUT)),
    mode=DRV8825StepperMotor.MODE_FULL,
    target_time_for_one_revolution_ms=1000,
)
button = Pin(15, Pin.IN, pull=Pin.PULL_UP)

def button_is_not_pressed():
    return bool(button.value())

res: DRV8825StepperMotor.MotorMoveResult = uasyncio.run(
    m.rotate_while_async(button_is_not_pressed, clockwise=True)
)
```


## Installation

For now there is no real installation. Just copy the code/classes from `DRV8825.py` into your script.
This code uses typing (which i recommend for any project). You need to install typing lib support on your board.

### Install typing support

You need to setup https://docs.micropython.org/en/latest/reference/mpremote.html

https://micropython-stubs.readthedocs.io/en/stable/_typing_mpy.html

`mpremote a1 mip install github:josverl/micropython-stubs/mip/typing.mpy`

`mpremote a1 mip install github:josverl/micropython-stubs/mip/typing_extensions.mpy`

pip install git+https://github.com/stlehmann/micropython-ssd1306

### local code completion in VSCode for board libs

See https://micropython-stubs.readthedocs.io/en/main/20_using.html#install-the-stub-packages-to-your-system


For a Raspberry Pico just run:  

`pip install -U  micropython-rp2-pico-stubs`
