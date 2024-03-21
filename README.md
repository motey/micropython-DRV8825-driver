# micropython-DRV8825-driver
A micropython class to controll a stepper motor with a DRV8825 driver (on a Raspberry Pico board)

> ℹ️ This is not a "official" library. Just some code i wrote and maybe it can be help you.

> :warning: I tested this with only with a Raspberry Pico and a cheap noname nema17 motor. if your setup is different your mileage may vary.


## Examples

(ToDo: Add image of eletronic setup)

**"normal"/synchronous code**

### synchronous example 1

A very basic example, that makes the motor turn two clockwise revolutions in approximately 0.5 seconds
The motor will run in [full step mode](https://www.youtube.com/watch?v=dmk6zIkj7WM).

```python
m = DRV8825StepperMotor(
    step_pin=Pin(4, Pin.OUT),
    direction_pin=Pin(5, Pin.OUT),
    enable_pin=Pin(6, Pin.OUT),
    mode_pins=(Pin(7, Pin.OUT), Pin(8, Pin.OUT), Pin(9, Pin.OUT)),
)
m.rotate(2, clockwise=True)
```
### synchronous example 2

An example, that makes the motor turn for 3 seconds counter clockwise with a speed of 1 revolution per sec. 
The motor will run in 1/16 stepping mode.
At the end the motor will be shut down (sleep mode)

```python
m = DRV8825StepperMotor(
    step_pin=Pin(4, Pin.OUT),
    direction_pin=Pin(5, Pin.OUT),
    reset_pin=Pin(2, Pin.OUT),
    sleep_pin=Pin(3, Pin.OUT),
    enable_pin=Pin(6, Pin.OUT),
    mode_pins=(Pin(7, Pin.OUT), Pin(8, Pin.OUT), Pin(9, Pin.OUT)),
    mode=DRV8825Modes.ONE_16,
    target_time_for_one_revolution_ms=1000,
)
start_time = utime.ticks_ms()
def three_seconds_are_gone() -> bool:
    if (utime.ticks_diff(utime.ticks_ms(), start_time) / 1000) > 3:
        return True
    return False
m.rotate_while(three_seconds_are_gone, clockwise=False)
m.sleep()
```

**asynchronous code**

### asynchronous example 1

An example, that makes the motor turn as long a the button on pin 12 is pressed. 
The motor will run in 1/16 stepping mode.
At the end the motor will be shut down (sleep mode)

```python
m = DRV8825StepperMotor(
    step_pin=Pin(4, Pin.OUT),
    direction_pin=Pin(5, Pin.OUT),
    reset_pin=Pin(2, Pin.OUT),
    sleep_pin=Pin(3, Pin.OUT),
    enable_pin=Pin(6, Pin.OUT),
    mode_pins=(Pin(7, Pin.OUT), Pin(8, Pin.OUT), Pin(9, Pin.OUT)),
    mode=DRV8825Modes.ONE_16,
    target_time_for_one_revolution_ms=1000,
)
btn = Pin(12)
async def button_is_pressed() -> bool:
    return bool(btn.value())

import uasyncio
uasyncio.run(m.async_rotate_while(button_is_pressed, clockwise=True))
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
