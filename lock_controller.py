"""
lock_controller.py

Abstracts away the hardware layer so the main face-recognition script never
needs to know or care what kind of lock hardware the user has.

Supported lock_type values (set in config.yaml):
    none            - simulation only, prints to console
    gpio_relay      - Raspberry Pi GPIO + relay module
    arduino_serial  - Arduino / microcontroller over USB serial
    mqtt            - wireless trigger (ESP32, smart home, etc.)
"""

import time


class LockController:
    def __init__(self, config):
        self.lock_type = config.get("lock_type", "none")
        self.config = config
        self._setup()

    def _setup(self):
        if self.lock_type == "none":
            pass  # nothing to initialize

        elif self.lock_type == "gpio_relay":
            try:
                import RPi.GPIO as GPIO
            except ImportError:
                raise ImportError(
                    "RPi.GPIO not found. Install it with: pip install RPi.GPIO "
                    "(only works on a Raspberry Pi)."
                )
            self.GPIO = GPIO
            self.pin = self.config.get("gpio_pin", 18)
            self.GPIO.setmode(self.GPIO.BCM)
            self.GPIO.setup(self.pin, self.GPIO.OUT)
            self.GPIO.output(self.pin, self.GPIO.LOW)

        elif self.lock_type == "arduino_serial":
            try:
                import serial
            except ImportError:
                raise ImportError(
                    "pyserial not found. Install it with: pip install pyserial"
                )
            port = self.config.get("serial_port", "/dev/ttyUSB0")
            baud = self.config.get("baud_rate", 9600)
            self.ser = serial.Serial(port, baud, timeout=1)
            time.sleep(2)  # allow Arduino to reset after serial connect

        elif self.lock_type == "mqtt":
            try:
                import paho.mqtt.client as mqtt
            except ImportError:
                raise ImportError(
                    "paho-mqtt not found. Install it with: pip install paho-mqtt"
                )
            self.mqtt_client = mqtt.Client()
            broker = self.config.get("mqtt_broker", "localhost")
            port = self.config.get("mqtt_port", 1883)
            self.mqtt_client.connect(broker, port, 60)
            self.mqtt_topic = self.config.get("mqtt_topic", "door/lock")

        else:
            raise ValueError(f"Unknown lock_type: '{self.lock_type}'")

    def unlock(self, duration=5):
        """Trigger the lock to open, wait, then re-lock."""
        if self.lock_type == "none":
            print(f"[SIMULATION] Door would UNLOCK now for {duration} seconds.")

        elif self.lock_type == "gpio_relay":
            self.GPIO.output(self.pin, self.GPIO.HIGH)
            time.sleep(duration)
            self.GPIO.output(self.pin, self.GPIO.LOW)

        elif self.lock_type == "arduino_serial":
            self.ser.write(b"UNLOCK\n")
            time.sleep(duration)
            self.ser.write(b"LOCK\n")

        elif self.lock_type == "mqtt":
            self.mqtt_client.publish(self.mqtt_topic, "UNLOCK")
            time.sleep(duration)
            self.mqtt_client.publish(self.mqtt_topic, "LOCK")

    def deny(self):
        """Called when a face is seen but does not match."""
        print("[ACCESS DENIED]")

    def cleanup(self):
        """Release hardware resources on shutdown."""
        if self.lock_type == "gpio_relay":
            self.GPIO.cleanup()
        elif self.lock_type == "arduino_serial":
            self.ser.close()
        elif self.lock_type == "mqtt":
            self.mqtt_client.disconnect()
