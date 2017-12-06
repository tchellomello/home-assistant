"""
This component provides HA sensor support for Ring Door Bell/Chimes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ring/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.ring import (
    CONF_ATTRIBUTION, DEFAULT_ENTITY_NAMESPACE, DATA_RING,
    CATEGORY_MAP, SENSORS, RingEntity)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS,
    STATE_UNKNOWN, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

DEPENDENCIES = ['ring']

_LOGGER = logging.getLogger(__name__)

SENSOR_KIND = {
    'last_activity': None,
    'last_ding': 'ding',
    'last_motion': 'motion',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ENTITY_NAMESPACE, default=DEFAULT_ENTITY_NAMESPACE):
        cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        vol.All(cv.ensure_list, [vol.In(SENSORS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for a Ring device."""
    ring = hass.data[DATA_RING].data

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        for device in ring.chimes:
            if 'chime' in CATEGORY_MAP.get(sensor_type):
                sensors.append(RingSensor(device, sensor_type, hass.config.time_zone))

        for device in ring.doorbells:
            if 'doorbell' in CATEGORY_MAP.get(sensor_type):
                sensors.append(RingSensor(device, sensor_type, hass.config.time_zone))

        for device in ring.stickup_cams:
            if 'stickup_cams' in CATEGORY_MAP.get(sensor_type, hass.config.time_zone):
                sensors.append(RingSensor(device, sensor_type, hass.config.time_zone))

    add_devices(sensors, True)
    return True


class RingSensor(RingEntity):
    """A sensor implementation for Ring device."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data and updates the state."""
        if self._sensor_type == 'battery':
            self._state = self.data.battery_life

        elif self._sensor_type.startswith('last_'):
            history = self.data.history(limit=5,
                                         timezone=self._timezone,
                                         kind=SENSOR_KIND.get(self._sensor_type),
                                         enforce_limit=True)
            if history:
                self._extra = history[0]
                created_at = self._extra['created_at']
                self._state = '{0:0>2}:{1:0>2}'.format(
                    created_at.hour, created_at.minute)

        else:
            self._state = getattr(self.data, self._sensor_type)
