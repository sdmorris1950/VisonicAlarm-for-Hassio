"""Interfaces with the Visonic Alarm sensors."""

from datetime import timedelta
import logging

from homeassistant.const import (
    STATE_CLOSED,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_UNKNOWN,
)
from homeassistant.helpers.entity import Entity

from . import HUB as hub, KEYFOB_DICT as keyfobs

_LOGGER = logging.getLogger(__name__)

STATE_ALARM_ARMING_EXIT_DELAY_HOME = "arming_exit_delay_home"
STATE_ALARM_ARMING_EXIT_DELAY_AWAY = "arming_exit_delay_away"
STATE_ALARM_ENTRY_DELAY = "entry_delay"

STATE_ATTR_SYSTEM_NAME = "system_name"
STATE_ATTR_SYSTEM_SERIAL_NUMBER = "serial_number"
STATE_ATTR_SYSTEM_MODEL = "model"
STATE_ATTR_SYSTEM_READY = "ready"
STATE_ATTR_SYSTEM_ACTIVE = "active"
STATE_ATTR_SYSTEM_CONNECTED = "connected"

CONTACT_ATTR_ZONE = "zone"
CONTACT_ATTR_NAME = "name"
CONTACT_ATTR_DEVICE_TYPE = "device_type"
CONTACT_ATTR_SUBTYPE = "subtype"

KEYFOB_ATTR_KEYFOB_NUMBER = "keyfob_number"
KEYFOB_ATTR_LAST_TIME_USED = "last_time_used"
KEYFOB_ATTR_LAST_OPERATION = "last_operation"

SCAN_INTERVAL = timedelta(seconds=10)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Visonic Alarm platform."""
    hub.update()

    keyfobs.clear()

    events = hub.alarm.get_events(timestamp_hour_offset=hub.config["event_hour_offset"])

    for device in hub.alarm.devices:
        if device is not None:
            if device.subtype is not None:
                if (
                    "CONTACT" in device.subtype
                    or "MOTION" in device.subtype
                    or "CURTAIN" in device.subtype
                    or "KEYFOB" in device.subtype
                ):
                    _msg = f"New device found [Type:{device.subtype}] [ID:{device.id}]"
                    _LOGGER.debug(_msg)
                    if "KEYFOB" in device.subtype:
                        user = f"user {device.device_number}"

                        last_time_used = None
                        last_operation = None
                        # get the last event for this keyfob
                        for _event in events:
                            if user == _event["appointment"].lower():
                                last_time_used = _event["datetime"]
                                last_operation = _event["description"]
                                break

                        keyfobs.update(
                            {
                                user: [
                                    device.name,
                                    device.id,
                                    last_time_used,
                                    last_operation,
                                ]
                            }
                        )

                    add_devices([VisonicAlarmContact(hub.alarm, device.id)], True)


class VisonicAlarmContact(Entity):
    """Implementation of a Visonic Alarm Contact sensor."""

    def __init__(self, alarm, contact_id):
        """Initialize the sensor."""
        self._state = STATE_UNKNOWN
        self._alarm = alarm
        self._id = contact_id
        self._name = None
        self._zone = None
        self._device_type = None
        self._keyfob_number = None
        self._subtype = None
        self._last_time_used = None
        self._last_operation = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return str(self._name)

    @property
    def unique_id(self):
        """Return a unique id."""
        return self._id

    @property
    def keyfob_number(self):
        """Return the keyfob number."""
        return self._keyfob_number

    @property
    def last_time_used(self):
        """Return a last time keyfob used."""
        return self._last_time_used

    # @last_time_used.setter
    # def last_time_used(self, value):
    #     self._last_time_used = value

    @property
    def last_operation(self):
        """Return a last keyfob operation."""
        return self._last_operation

    # @last_operation.setter
    # def last_operation(self, value):
    #     self._last_operation = value

    @property
    def state_attributes(self):
        """Return the state attributes of the alarm system."""
        if "KEYFOB" in self._subtype:
            return {
                CONTACT_ATTR_ZONE: self._zone,
                CONTACT_ATTR_NAME: self._name,
                CONTACT_ATTR_DEVICE_TYPE: self._device_type,
                CONTACT_ATTR_SUBTYPE: self._subtype,
                KEYFOB_ATTR_KEYFOB_NUMBER: self._keyfob_number,
                KEYFOB_ATTR_LAST_TIME_USED: self._last_time_used,
                KEYFOB_ATTR_LAST_OPERATION: self._last_operation,
            }
        return {
            CONTACT_ATTR_ZONE: self._zone,
            CONTACT_ATTR_NAME: self._name,
            CONTACT_ATTR_DEVICE_TYPE: self._device_type,
            CONTACT_ATTR_SUBTYPE: self._subtype,
        }

    @property
    def icon(self):
        """Return icon."""
        icon = None
        if not self._zone and "24H" in self._zone:
            if self._state == STATE_CLOSED:
                icon = "mdi:hours-24"
            else:
                icon = "mdi:alarm-light"
        elif "KEYFOB" in self._subtype:
            icon = "mdi:key-outline"
        elif self._state == STATE_CLOSED:
            icon = "mdi:door-closed"
        elif self._state == STATE_OPEN:
            icon = "mdi:door-open"
        elif self._state == STATE_OFF:
            icon = "mdi:motion-sensor-off"
        elif self._state == STATE_ON:
            icon = "mdi:motion-sensor"
        return icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data."""
        try:
            hub.update()

            device = self._alarm.get_device_by_id(self._id)

            status = device.state

            if status is None:
                _LOGGER.warning("Device could not be found: %s", self._id)
                return

            if "CURTAIN" in device.subtype or "MOTION" in device.subtype:
                alarm_state = self._alarm.state
                alarm_zone = device.zone

                if alarm_state in ("DISARM", "ARMING"):
                    if "24H" in alarm_zone:
                        self._state = STATE_ON
                    else:
                        self._state = STATE_OFF
                elif alarm_state == "HOME":
                    if "INTERIOR" in alarm_zone:
                        self._state = STATE_OFF
                    else:
                        self._state = STATE_ON
                elif alarm_state in ("AWAY", "DISARMING"):
                    self._state = STATE_ON
                else:
                    self._state = STATE_UNKNOWN
            elif "KEYFOB" in device.subtype:
                self._state = STATE_CLOSED
                self._keyfob_number = device.device_number
                _user = f"user {device.device_number}"
                self._last_time_used = keyfobs[_user][2]
                self._last_operation = keyfobs[_user][3]
            elif "CONTACT" in device.subtype:
                if status == "opened":
                    self._state = STATE_OPEN
                else:
                    self._state = STATE_CLOSED
            elif status == "opened":
                self._state = STATE_OPEN
            elif status == "closed":
                self._state = STATE_CLOSED
            else:
                self._state = STATE_UNKNOWN

            # orig_level = _LOGGER.level
            # _LOGGER.setLevel(logging.DEBUG)
            # _LOGGER.debug("alarm.state %s", self._alarm.state)
            # _LOGGER.setLevel(orig_level)

            self._zone = device.zone
            self._name = device.name
            self._device_type = device.device_type
            self._subtype = device.subtype

            _LOGGER.debug("Device state updated to %d W", self._state)
        except OSError as error:
            _LOGGER.warning("Could not update the device information: %s", error)
