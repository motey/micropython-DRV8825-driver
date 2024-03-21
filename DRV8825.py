from typing import Tuple, Literal, Callable, Awaitable, Optional
from machine import Pin
from utime import sleep_us
import uasyncio

HIGH = True
LOW = False


class DRV8825SteppingMode:
    def __init__(
        self,
        name: str,
        mode_setting: Tuple[bool, bool, bool],
        microsteps: Literal[1, 2, 4, 8, 16, 32],
    ):
        self.name = name
        self.mode_setting = mode_setting
        self.microsteps = microsteps


class DRV8825Modes:
    FULL = DRV8825SteppingMode("FULL", (LOW, LOW, LOW), 1)
    HALF = DRV8825SteppingMode("HALF", (HIGH, LOW, LOW), 2)
    QUARTER = DRV8825SteppingMode("QUARTER", (LOW, HIGH, LOW), 4)
    ONE_8 = DRV8825SteppingMode("1/8", (HIGH, HIGH, LOW), 8)
    ONE_16 = DRV8825SteppingMode("1/16", (LOW, LOW, HIGH), 16)
    ONE_32 = DRV8825SteppingMode("1/32", (HIGH, LOW, HIGH), 32)


class DRV8825StepperMotor:
    # https://www.studiopieters.nl/drv8825-pinout/

    def __init__(
        self,
        step_pin: Pin,
        direction_pin: Optional[Pin] = None,
        reset_pin: Optional[Pin] = None,
        sleep_pin: Optional[Pin] = None,
        enable_pin: Optional[Pin] = None,
        mode_pins: Optional[Tuple[Pin, Pin, Pin]] = None,
        fault_pin: Optional[Pin] = None,
        mode: DRV8825SteppingMode = DRV8825Modes.FULL,
        full_steps_for_one_revolution: int = 200,
        target_time_for_one_revolution_ms: float = 500,
        skip_motor_init: bool = False,
    ):
        """Init function for DRV8825StepperMotor

        Args:
            step_pin (Pin): board gpio that connect to the drv8825 STP pin
            direction_pin (Optional[Pin], optional): board gpio that connect to the drv8825 DIR pin. Defaults to None.
            reset_pin (Optional[Pin], optional): board gpio that connect to the drv8825 RST pin. Defaults to None.
            sleep_pin (Optional[Pin], optional): board gpio that connect to the drv8825 SLP pin. Defaults to None.
            enable_pin (Optional[Pin], optional): board gpio that connect to the drv8825 EN pin. Defaults to None.
            mode_pins (Optional[Tuple[Pin, Pin, Pin]], optional): Tuple of board gpio pins that connect to the drv8225s M0, M1, M2 pin. Defaults to None.
            fault_pin (Optional[Pin], optional): board gpio that connect to the drv8825 FLT pin. Defaults to None.
            mode (Optional[DRV8825SteppingMode], optional): Microstepping mode defined in class `DRV8825Modes`. Defaults to DRV8825Modes.FULL
            full_steps_for_one_revolution (Optional[int], optional): Amount of steps needed for a fill revolution in FULL step mode. Depends on the motor you are using. Look up in the specs. Defaults to 200.. Defaults to 200.
            target_time_for_one_revolution_ms (Optional[float], optional): Translates into speed. We try to match the target time but can not guarante it. Defaults to 500.. Defaults to 500.
            skip_motor_init (Optional[bool], optional): if set to true and the respective pins are provided the motor will be enabled, un-reseted, un-sleeped and the stepper mode will be set. If set to False you need to prepare the motor yourself.
        """
        self.step_pin = step_pin
        self.direction_pin = direction_pin
        self.reset_pin = reset_pin
        self.sleep_pin = sleep_pin
        self.enable_pin = enable_pin
        self.mode_pins = mode_pins
        self.fault_pin = fault_pin
        self.full_steps_for_one_revolution = full_steps_for_one_revolution
        self.target_time_for_one_revolution_ms = target_time_for_one_revolution_ms
        self.mode = mode

        self.pulse_delay_us: float = 0.0
        self.steps_for_one_revolution = 0

        if not skip_motor_init:
            self._init_motor()

    def _init_motor(self):
        if self.enable_pin:
            self.enable()
        if self.reset_pin:
            self.reset(False)
        if self.sleep_pin:
            self.sleep(False)
        self.set_mode(self.mode)

    def set_mode(self, mode: DRV8825SteppingMode):
        """All modes are defined in DRV8825Modes

        Args:
            res (Tuple[bool, bool, bool]): _description_
        """
        # Calcuate pulse delay time (Wait time before triggering the next motor step aka. energizing to next the coil)
        self.steps_for_one_revolution = self.mode.microsteps * (
            self.full_steps_for_one_revolution
        )

        delay_ms = self.target_time_for_one_revolution_ms / int(
            self.steps_for_one_revolution * 2
        )

        ## the pulse delay offset value is not based on anything. it just works ¯\_(ツ)_/¯.
        ## The resulting time for one revolution is in all my test cases closer to self.target_time_for_one_revolution_ms as without
        ## (ToDo: find explanation)
        pulse_delay_offset = self.mode.microsteps
        self.pulse_delay_us = int(delay_ms * 1000) - pulse_delay_offset

        # Set the microstepping on the DRV8825 driver
        if self.mode_pins and len(self.mode_pins) == 3:
            for index, pin in enumerate(self.mode_pins):
                pin.value(mode.mode_setting[index])
        else:
            print(
                f"Warning: Microstepping mode set to {mode.name}, but mode pins (M0,M1,M3) were not provided. Make sure mode pins are set otherwise/externaly."
            )
        self.mode = mode

    def enable(self, enable: bool = True):
        """Enable or disable the driver"""
        # from https://lastminuteengineers.com/drv8825-stepper-motor-driver-arduino-tutorial/
        """EN is an active low input pin.
        When this pin is pulled LOW, the DRV8825 driver is enabled.
        By default, this pin is pulled low, so unless you pull it high,
        the driver is always enabled.
        This pin is particularly useful when implementing an emergency stop or shutdown system.
        """
        if self.enable_pin:
            self.enable_pin.value(not enable)
        else:
            raise ValueError(
                "Can not switch EN pin. Pin was not provided on instantiation of `DRV8825StepperMotor`."
            )

    def sleep(self, sleep_: bool = True):
        """Set the driver in "sleep"-mode (or disable sleep mode)"""
        # from https://lastminuteengineers.com/drv8825-stepper-motor-driver-arduino-tutorial/
        """SLP is an active low input pin.
        Pulling this pin LOW puts the driver into sleep mode,
        reducing power consumption to a minimum.
        You can use this to save power, especially when the motor is not in use."""
        if self.sleep_pin:
            self.sleep_pin.value(not sleep_)
        else:
            raise ValueError(
                "Can not switch SLP pin. Pin was not provided on instantiation of `DRV8825StepperMotor`."
            )

    def reset(self, reset: bool = False):
        """Activate or disable reset mode"""
        # from https://lastminuteengineers.com/drv8825-stepper-motor-driver-arduino-tutorial/
        """RST is an active low input as well. 
        When this pin is pulled LOW, all STEP inputs are ignored. 
        It also resets the driver by setting the internal translator to a predefined “home” state. 
        Home state is basically the initial position from which the motor starts, 
        and it varies based on microstep resolution.
        """
        if self.reset_pin:
            self.reset_pin.value(not reset)
        else:
            raise ValueError(
                "Can not switch RST pin. Pin was not provided on instantiation of `DRV8825StepperMotor`."
            )

    def direction_clockwise(self, clockwise: Optional[bool] = True):
        """If set True the motor will turn clockwise. Otherwise counterclockwise

        Args:
            clockwise (bool, optional): _description_. Defaults to True.
        """
        # from https://lastminuteengineers.com/drv8825-stepper-motor-driver-arduino-tutorial/
        """
        DIR input controls the spinning direction of the motor. Pulling it HIGH turns the motor clockwise, while pulling it LOW turns it counterclockwise.
        """
        if self.direction_pin:
            self.direction_pin.value(clockwise)
        else:
            raise ValueError(
                "Can not switch DIR pin. Pin was not provided on instantiation of `DRV8825StepperMotor`."
            )

    def is_direction_clockwise(self) -> bool:
        """Check current set roatation direction of motor

        Raises:
            ValueError: Fails if DIR pin is not provided

        Returns:
            bool: _description_
        """
        if self.direction_pin:
            return bool(self.direction_pin.value())
        else:
            raise ValueError(
                "Can determine direction. DIR pin was not provided on instantiation of `DRV8825StepperMotor`."
            )

    def step(self, steps: int = 1, clockwise: Optional[bool] = None):
        """Turn the motor one step

        Args:
            steps (int, optional): _description_. Defaults to 1.
            clockwise (bool, optional): _description_. Defaults to None.
        """
        if clockwise:
            self.direction_clockwise(clockwise)
        for i in range(steps * 2):
            sleep_us(self.pulse_delay_us)
            self.step_pin.value(not self.step_pin.value())

    def rotate(self, revolutions: float = 1.0, clockwise: Optional[bool] = None):
        """Turn the motor X revolutions (One revolution -> 360°). Can be a float to turn fractional revolution (1.5 will make one and a half revolution)

        Args:
            rotations (float, optional): _description_. Defaults to 1.0.
            clockwise (bool, optional): _description_. Defaults to False.
        """
        self.step(
            steps=int(self.steps_for_one_revolution * revolutions),
            clockwise=clockwise,
        )

    def rotate_while(
        self, while_check_func: Callable[[], bool], clockwise: Optional[bool] = None
    ):
        """Provide a function that returns a boolean. The motor will rotate until the function returns False.
        example:
        ```python
        def button_is_pressed() -> bool:
            return my_button_pin.value()
        m.rotate_while(button_is_pressed)
        ```
        Args:
            while_check_func (Callable[[], bool]): _description_
            clockwise (bool, optional): _description_. Defaults to None.
        """
        if clockwise:
            self.direction_clockwise(clockwise)
        while while_check_func():
            self.step(1, clockwise)

    async def async_step(self, steps: int = 1, clockwise: Optional[bool] = None):
        """Async (uasyncio) version of DRV8825StepperMotor.step()


        Args:
            steps (int, optional): _description_. Defaults to 1.
            clockwise (bool, optional): _description_. Defaults to None.
        """
        if clockwise:
            self.direction_clockwise(clockwise)
        for i in range(steps * 2):
            await uasyncio.sleep_us(self.pulse_delay_us)
            self.step_pin.value(not self.step_pin.value())

    async def async_rotate(
        self, revolutions: int | float = 1.0, clockwise: bool = False
    ):
        """Async (uasyncio) version of DRV8825StepperMotor.rotate()
        Turn the motor X revolutions (One revolution -> 360°). Can be a float to turn fractional revolution (1.5 will make one and a half revolution)

        Args:
            rotations (float, optional): _description_. Defaults to 1.0.
            clockwise (bool, optional): _description_. Defaults to False.
        """
        await self.async_step(
            steps=int(self.steps_for_one_revolution * revolutions),
            clockwise=clockwise,
        )

    async def async_rotate_while(
        self,
        while_check_func: Callable[[], Awaitable[bool]],
        clockwise: Optional[bool] = None,
    ):
        """Provide a async function that returns a boolean. The motor will rotate until the function returns False.
        example:
        ```python
        import uasyncio
        start_time = utime.ticks_ms()
        async def are_3_seconds_gone() -> bool:
            if (utime.ticks_diff(utime.ticks_ms(), start_time) / 1000) > 3:
                return True
            return False
        uasyncio.run(m.async_rotate_while(are_3_seconds_gone, clockwise=False))
        ```
        Args:
            while_check_func (Callable[[], Awaitable[bool]]): _description_
            clockwise (bool, optional): _description_. Defaults to None.
        """
        if clockwise:
            self.direction_clockwise(clockwise)
        while not await while_check_func():
            self.step(1, clockwise)
