"""
Support for Ring Doorbell/Chimes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/ring/
"""
import asyncio
import logging

from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.dispatcher import (
     async_dispatcher_connect, dispatcher_send)
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL, ATTR_ATTRIBUTION)

from requests.exceptions import HTTPError, ConnectTimeout

REQUIREMENTS = ['ring_doorbell==0.1.9']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by Ring.com"

NOTIFICATION_ID = 'ring_notification'
NOTIFICATION_TITLE = 'Ring Setup'

DATA_RING = 'ring'
DOMAIN = 'ring'
DEFAULT_CACHEDB = '.ring_cache.pickle'
DEFAULT_ENTITY_NAMESPACE = 'ring'

SCAN_INTERVAL = timedelta(seconds=90)

KEY_MAP = {
    'battery': 'Battery',
    'ding': 'Ding',
    'last_activity': 'Last Activity',
    'last_ding': 'Last Ding',
    'last_motion': 'Last Motion',
    'motion': 'Motion',
    'volume': 'Volume',
    'wifi_signal_category': 'WiFi Signal Category',
    'wifi_signal_strength': 'WiFi Signal Strength',
}

CATEGORY_MAP = {
    'battery': ['doorbell', 'stickup_cams'],
    'ding': ['doorbell'],
    'last_activity': ['doorbell', 'stickup_cams'],
    'last_ding': ['doorbell'],
    'last_motion': ['doorbell', 'stickup_cams'],
    'motion': ['doorbell', 'stickup_cams'],
    'volume': ['chime', 'doorbell', 'stickup_cams'],
    'wifi_signal_category': ['chime', 'doorbell', 'stickup_cams'],
    'wifi_signal_strength': ['chime', 'doorbell', 'stickup_cams'],
}

ICON_MAP = {
    'battery': 'battery-50',
    'last_activity': 'history',
    'last_ding': 'history',
    'last_motion': 'history',
    'volume': 'bell-ring',
    'wifi_signal_category': 'wifi',
    'wifi_signal_strength': 'wifi',
}

UNIT_OF_MEASUREMENT_MAP = {
    'battery': '%',
    'last_activity': None,
    'last_ding': None,
    'last_motion': None,
    'volume': None,
    'wifi_signal_category': None,
    'wifi_signal_strength': 'dBm',
}

BINARY_SENSORS = ['ding', 'motion']

SENSORS = [ 'battery', 'last_activity', 'last_ding', 'last_motion',
            'volume', 'wifi_signal_category', 'wifi_signal_strength']

SIGNAL_UPDATE_RING = "ring_update"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Ring component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    try:
        from ring_doorbell import Ring

        cache = hass.config.path(DEFAULT_CACHEDB)
        ring = Ring(username=username, password=password, cache_file=cache)
        if not ring.is_connected:
            return False

        hass.data[DATA_RING] = RingHub(ring)

    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Ring service: %s", str(ex))
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    def hub_refresh(event_time):
        """Call Ring hub to refresh information."""
        _LOGGER.debug("Updating Ring Hub component.")
        hass.data[DATA_RING].data.update()
        dispatcher_send(hass, SIGNAL_UPDATE_RING)

    # Call the Ring to refresh updates
    track_time_interval(hass, hub_refresh, scan_interval)

    return True


class RingHub(object):
    """Representation of a base Ring device."""

    def __init__(self, data):
        """Initialize the entity."""
        self.data = data


class RingEntity(Entity):
    """Entity class for RainCloud devices."""

    def __init__(self, data, sensor_type):
        """Initialize the RainCloud entity."""
        self.data = data
        self._sensor_type = sensor_type


class RingEntity(Entity):
    """Entity class for Ring devices."""

    def __init__(self, data, sensor_type, timezone):
        """Initialize the Ring entity."""
        self.data = data
        self._sensor_type = sensor_type
        self._name = "{0} {1}".format(
            self.data.name, KEY_MAP.get(self._sensor_type))
        self._state = None
        self._extra = None
        self._video_url = None
        self._timezone = str(timezone)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_RING, self._update_callback)

    def _update_callback(self):
        """Callback update method."""
        self.schedule_update_ha_state(True)

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return UNIT_OF_MEASUREMENT_MAP.get(self._sensor_type)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        attrs['device_id'] = self.data.id
        attrs['firmware'] = self.data.firmware
        attrs['kind'] = self.data.kind
        attrs['timezone'] = self.data.timezone
        attrs['type'] = self.data.family
        attrs['wifi_name'] = self.data.wifi_name

        if self._extra and self._sensor_type.startswith('last_'):
            attrs['created_at'] = self._extra['created_at']
            attrs['answered'] = self._extra['answered']
            attrs['recording_status'] = self._extra['recording']['status']
            attrs['category'] = self._extra['kind']

        if self.data.alert and self.data.alert_expires_at:
            attrs['expires_at'] = self.data.alert_expires_at
            attrs['state'] = self.data.alert.get('state')

        if self._video_url:
            attrs['video_url'] = self._video_url

        return attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._sensor_type == 'battery' and self._state is not None:
            return icon_for_battery_level(battery_level=int(self._state),
                                          charging=False)
        return ICON_MAP.get(self._sensor_type)
