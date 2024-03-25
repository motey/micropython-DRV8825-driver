from typing import Tuple, Literal, Callable, Awaitable, Optional, Dict, Any
from machine import Pin, Timer
from utime import sleep_us
import uasyncio


class DRV8825StepperMotor:
    # https://www.studiopieters.nl/drv8825-pinout/
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

    MODE_FULL = DRV8825SteppingMode("FULL", (LOW, LOW, LOW), 1)
    MODE_HALF = DRV8825SteppingMode("HALF", (HIGH, LOW, LOW), 2)
    MODE_QUARTER = DRV8825SteppingMode("QUARTER", (LOW, HIGH, LOW), 4)
    MODE_ONE_8 = DRV8825SteppingMode("1/8", (HIGH, HIGH, LOW), 8)
    MODE_ONE_16 = DRV8825SteppingMode("1/16", (LOW, LOW, HIGH), 16)
    MODE_ONE_32 = DRV8825SteppingMode("1/32", (HIGH, LOW, HIGH), 32)

    class NonBlockResult:
        def __init__(self):
            self.done = False
            self.pulses_done: int = 0
            self._start_tick_ms: Optional[float] = None
            self._finish_tick_ms: Optional[float] = None
            self.callback_result: Any = None

        def get_run_time_ms(self) -> float:
            if self._start_tick_ms is None:
                raise ValueError("Non blocking function not yet started.")
            if self._finish_tick_ms is None:
                return utime.ticks_diff(utime.ticks_ms(), self._start_tick_ms)
            return utime.ticks_diff(self._finish_tick_ms, self._start_tick_ms)

        def get_steps_done(self) -> float:
            return self.pulses_done / 2

    class NonBlockTimerContainer:

        def __init__(
            self,
            timer: Timer,
            target_steps: Optional[int] = None,
            keep_running_check_callback: Optional[Callable[[], bool]] = None,
            finished_callback: Optional[
                Optional[
                    Callable[
                        ["DRV8825StepperMotor.NonBlockResult"],
                        "DRV8825StepperMotor.NonBlockResult",
                    ]
                ]
            ] = None,
        ):
            if target_steps and keep_running_check_callback:
                raise ValueError(
                    f"Either set 'target_steps' or 'keep_running_check_callback', not both."
                )
            elif not target_steps and not keep_running_check_callback:
                raise ValueError(
                    f"Either set 'target_steps' or 'keep_running_check_callback'."
                )
            self.timer = timer
            self.steps_remaining = target_steps
            self.keep_running_check_callback = keep_running_check_callback
            self.finished_callback = finished_callback
            self.result = DRV8825StepperMotor.NonBlockResult()

        def make_pulse(self) -> bool:
            if self.result._start_tick_ms is None:
                self.result._start_tick_ms = utime.ticks_ms()
            result = False

            if self.keep_running_check_callback is not None:
                result = self.keep_running_check_callback()
            elif self.steps_remaining == 0:
                result = False
            elif self.steps_remaining:
                self.steps_remaining = self.steps_remaining - 1
                result = True
            if result:
                self.result.pulses_done = self.result.pulses_done + 1
            # just to make the linter happy.
            return result

        def finish(self) -> "DRV8825StepperMotor.NonBlockResult":
            self.timer.deinit()
            self.result._finish_tick_ms = utime.ticks_ms()
            self.result.done = True
            if self.finished_callback:
                self.result.callback_result = self.finished_callback(self.result)
            return self.result

    def __init__(
        self,
        step_pin: Pin,
        direction_pin: Optional[Pin] = None,
        reset_pin: Optional[Pin] = None,
        sleep_pin: Optional[Pin] = None,
        enable_pin: Optional[Pin] = None,
        mode_pins: Optional[Tuple[Pin, Pin, Pin]] = None,
        fault_pin: Optional[Pin] = None,
        mode: DRV8825SteppingMode = MODE_FULL,
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
        self._timer_container: Optional[DRV8825StepperMotor.NonBlockTimerContainer] = (
            None
        )

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
        self.pulse_delay_us = int(delay_ms * 1000)

        ## the pulse delay offset value is not based on anything. it just works in blocking functions ¯\_(ツ)_/¯
        ## The resulting time for one revolution is in all my test cases closer to self.target_time_for_one_revolution_ms as without
        # it is not used in non blocking (incl. asynco) functions
        ## (ToDo: find explanation and document)
        self.pulse_delay_offset_blocking_step = -self.mode.microsteps

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

    def step(self):
        """Create a single pulse on the STP pin. A.k.a make one step."""
        self.step_pin.toggle()

    def steps(self, amount: int = 1, clockwise: Optional[bool] = None):
        """Turn the motor one step. This is the most simple method but also a blocking one.
        It is easy to understand but comes with some caveats:
            * The speed can vary based the work load of the microcontroller.
            * You can not do anything else until the motor movement is finished.
        If you need a non blocking way have a look at DRV8825StepperMotor.steps_non_blocking() and/or DRV8825StepperMotor.steps_async()

        Args:
            amount (int, optional): _description_. Defaults to 1.
            clockwise (bool, optional): _description_. Defaults to None.
        """
        if clockwise:
            self.direction_clockwise(clockwise)
        for i in range(amount * 2):
            sleep_us(self.pulse_delay_us + self.pulse_delay_offset_blocking_step)
            self.step()

    def rotate(
        self,
        revolutions: float = 1.0,
        clockwise: Optional[bool] = None,
    ):
        """Turn the motor X revolutions (One revolution -> 360°). Can be a float to turn fractional revolution (1.5 will make one and a half revolution)
        This is a blocking function, see DRV8825StepperMotor.steps() to be aware of the caveats.

        Args:
            revolutions (float, optional): _description_. Defaults to 1.0.
            clockwise (bool, optional): _description_. Defaults to False.
        """
        step_count = int(self.steps_for_one_revolution * revolutions)
        self.steps(
            amount=step_count,
            clockwise=clockwise,
        )

    def rotate_while(
        self, while_check_func: Callable[[], bool], clockwise: Optional[bool] = None
    ):
        """Provide a function that returns a boolean. The motor will rotate until the function returns False.
        Args:
            while_check_func (Callable[[], bool]): _description_
            clockwise (bool, optional): _description_. Defaults to None.
        """
        if clockwise:
            self.direction_clockwise(clockwise)
        while while_check_func():
            self.steps(1)

    def _step_non_blocking_timer_callback(self, t: Timer):
        if self._timer_container:
            if self._timer_container.make_pulse():
                self.step()
            else:
                self._timer_container.finish()

    def _steps_non_blocking(
        self, timer_container: NonBlockTimerContainer, clockwise: Optional[bool] = None
    ):
        if clockwise:
            self.direction_clockwise(clockwise)

        self._timer_container = timer_container
        # Micropython Timers frequencies are defined in hertz(hz). Lets first calculate our delay into Hz.
        frequency_hz: int = int((1 / (self.pulse_delay_us / 1000 / 1000)))

        self._timer_container.timer.init(
            freq=frequency_hz,
            mode=Timer.PERIODIC,
            callback=self._step_non_blocking_timer_callback,
        )
        return self._timer_container.result

    def steps_non_blocking(
        self,
        amount: int = 1,
        clockwise: Optional[bool] = None,
        callback: Optional[Callable[[NonBlockResult], Any]] = None,
        timer_id: int = -1,
    ) -> NonBlockResult:
        """Do x steps. Same as DRV8825StepperMotor.steps(), but non blocking.
        This means you can call this function and the code will continue and not wait for the motor move to be finished.
        The non blocking behaviour is achieved by using a Machine.Timer().

        Args:
            steps (int, optional): _description_. Defaults to 1.
            clockwise (Optional[bool], optional): _description_. Defaults to None.
            callback (Optional[Callable], optional): _description_. Defaults to None.
            timer_id (int, optional): _description_. Defaults to -1.
        """
        non_block_timer_container = DRV8825StepperMotor.NonBlockTimerContainer(
            timer=Timer(timer_id),
            target_steps=amount * 2,
            finished_callback=callback,
        )
        return self._steps_non_blocking(
            timer_container=non_block_timer_container,
            clockwise=clockwise,
        )

    def rotate_non_blocking(
        self,
        revolutions: float = 1.0,
        clockwise: Optional[bool] = None,
        callback: Optional[Callable[[NonBlockResult], Any]] = None,
        timer_id: int = -1,
    ) -> NonBlockResult:
        """Do x revolutions. Same as DRV8825StepperMotor.rotate(), but non blocking.
        This means you can call this function and the code will continue and not wait for the motor move to be finished.
        The non blocking behaviour is achieved by using a Machine.Timer().

        Args:
            revolutions (float, optional): _description_. Defaults to 1.0.
            clockwise (Optional[bool], optional): _description_. Defaults to None.
            callback (Optional[Callable], optional): _description_. Defaults to None.
            timer_id (int, optional): _description_. Defaults to -1.
        """
        step_count = int(self.steps_for_one_revolution * revolutions)
        return self.steps_non_blocking(
            amount=step_count,
            clockwise=clockwise,
            timer_id=timer_id,
            callback=callback,
        )

    def rotate_while_non_blocking(
        self,
        while_check_func: Callable[[], bool],
        clockwise: Optional[bool] = None,
        callback: Optional[Callable[[NonBlockResult], Any]] = None,
        timer_id: int = -1,
    ) -> NonBlockResult:
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

        return self._steps_non_blocking(
            timer_container=DRV8825StepperMotor.NonBlockTimerContainer(
                timer=Timer(timer_id),
                keep_running_check_callback=while_check_func,
                finished_callback=callback,
            )
        )

    async def step_async(self, steps: int = 1, clockwise: Optional[bool] = None):
        """Async (uasyncio) version of DRV8825StepperMotor.step()


        Args:
            steps (int, optional): _description_. Defaults to 1.
            clockwise (bool, optional): _description_. Defaults to None.
        """
        if clockwise:
            self.direction_clockwise(clockwise)
        for i in range(steps * 2):
            await uasyncio.sleep_ms(self.pulse_delay_us / 1000)
            self.step()

    async def rotate_async(
        self, revolutions: int | float = 1.0, clockwise: bool = False
    ):
        """Async (uasyncio) version of DRV8825StepperMotor.rotate()
        Turn the motor X revolutions (One revolution -> 360°). Can be a float to turn fractional revolution (1.5 will make one and a half revolution)

        Args:
            rotations (float, optional): _description_. Defaults to 1.0.
            clockwise (bool, optional): _description_. Defaults to False.
        """
        await self.step_async(
            steps=int(self.steps_for_one_revolution * revolutions),
            clockwise=clockwise,
        )

    async def rotate_while_async(
        self,
        while_check_func: Callable[[], Awaitable[bool]],
        clockwise: Optional[bool] = None,
    ):
        """Provide a async function that returns a boolean. The motor will rotate until the function returns False.
        example:
        Args:
            while_check_func (Callable[[], Awaitable[bool]]): _description_
            clockwise (bool, optional): _description_. Defaults to None.
        """
        if clockwise:
            self.direction_clockwise(clockwise)
        while not await while_check_func():
            self.steps(1, clockwise)
