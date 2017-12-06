"""
This component provides HA sensor support for Ring Door Bell/Chimes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.ring/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.ring import (
    BINARY_SENSORS, CATEGORY_MAP, DATA_RING,
    DEFAULT_ENTITY_NAMESPACE, RingEntity)

from homeassistant.const import (
    CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS)

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)

DEPENDENCIES = ['ring']

DEVICE_CLASS_MAP = {
   'ding': 'occupancy',
   'motion': 'motion',
}

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ENTITY_NAMESPACE, default=DEFAULT_ENTITY_NAMESPACE):
        cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSORS)):
        vol.All(cv.ensure_list, [vol.In(BINARY_SENSORS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for a Ring device."""
    ring = hass.data[DATA_RING].data

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        for device in ring.doorbells:
            if 'doorbell' in CATEGORY_MAP.get(sensor_type):
                sensors.append(RingBinarySensor(device,
                                                sensor_type,
                                                hass.config.time_zone))

        for device in ring.stickup_cams:
            if 'stickup_cams' in CATEGORY_MAP.get(sensor_type):
                sensors.append(RingBinarySensor(device,
                                                sensor_type,
                                                hass.config.time_zone))
    add_devices(sensors, True)
    return True


class RingBinarySensor(RingEntity, BinarySensorDevice):
    """A binary sensor implementation for Ring device."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return DEVICE_CLASS_MAP.get(self._sensor_type)

    def update(self):
        """Get the latest data and updates the state."""
        self.data.check_alerts()

        if self.data.alert:
            if self._sensor_type == self.data.alert.get('kind') and \
               self.data.account_id == self.data.alert.get('doorbot_id'):
                self._state = True
        else:
            self._state = False
