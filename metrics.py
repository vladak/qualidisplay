"""
Metrics class abstracts acquiring metrics (to a degree)
"""

import json
import adafruit_logging as logging
import ssl
import time

import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_minimqtt.adafruit_minimqtt import MMQTTException


def message_handler(client, topic, message):
    """
    process MQTT message and store the data in the Metrics object passed
    as a user data inside the MQTT client object.
    """
    metrics = client.user_data
    assert metrics

    logger = logging.getLogger(__name__)
    logger.debug(f"got {message} on {topic}")

    if topic not in metrics.topic2names.keys():
        logger.debug(f"Topic {topic} not subscribed")
        return

    payload_dict = json.loads(message)

    metric_names = metrics.topic2names.get(topic)
    for metric_name in metric_names:
        metric_value = payload_dict.get(metric_name)
        if metric_value is not None:
            metrics.logger.debug(f"got {metric_name} {metric_value}")
            metrics.values[metric_name] = (metric_value, time.monotonic())


# pylint: disable=too-few-public-methods
class Metrics:
    """
    class to retrieve metrics
    """

    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-instance-attributes
    def __init__(
        self,
        log_level,
        pool,
        hostname,
        port,
        metric_timeout,
        loop_timeout,
        topic_n_name,
    ):
        """
        Connect to the MQTT broker and subcribe to the topics.
        """

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        self.mqtt = MQTT.MQTT(
            broker=hostname,
            port=port,
            socket_pool=pool,
            ssl_context=ssl.create_default_context(),
            user_data=self,
            socket_timeout=0.1,
        )
        self.logger.info(f"Connecting to MQTT broker {hostname} on port {port}")
        self.mqtt.connect()

        self.metric_timeout = metric_timeout
        self.loop_timeout = loop_timeout

        #
        # Construct 2 dictionaries:
        #  - to map topic name to list of value names
        #  - to store tuples of value and timestamp of its last update
        #
        self.values = {}
        self.topic2names = {}
        for (topic, value_name) in topic_n_name:
            if value_name is None:
                raise ValueError(f"value name for topic {topic} is None")
            self.values[value_name] = (None, None)
            if self.topic2names.get(topic) is None:
                self.topic2names[topic] = [value_name]
            else:
                self.topic2names[topic].append(value_name)

        self.logger.debug(f"topic2name = {self.topic2names}")
        self.logger.debug(f"values = {self.values}")

        self.mqtt.on_message = message_handler
        # Avoid subscribing to the same topic multiple times by constructing a set.
        topics = [(topic, 0) for topic in set(self.topic2names.keys())]
        self.logger.info(f"subscribing to {topics}")
        self.mqtt.subscribe(topics)

    def get_metrics(self):
        """
        Retrieve metrics from MQTT return them as a tuple.
        Should be called periodically w.r.t. MQTT timeout.
        If a metric cannot be retrieved, None is used instead.
        :return: dictionary of name to value
        """

        # Make sure to stay connected to the broker e.g. in case of keep alive.
        try:
            self.mqtt.loop(self.loop_timeout)
        except MMQTTException as e:
            self.logger.warning(f"Got MQTT exception: {e}")
            self.mqtt.reconnect()

        #
        # If some of the metrics has not been updated for certain time,
        # consider it not available to avoid presenting stale values.
        #
        now = time.monotonic()
        if now > self.metric_timeout:
            time_threshold = now - self.metric_timeout
            for name, value_n_ts in self.values.items():
                value = value_n_ts[0]
                ts = value_n_ts[0]
                # TODO
                #if ts is not None and ts < time_threshold:
                #    self.logger.warning(f"{name} last updated before time threshold")
                #    self.values[name] = (None, None)
                #else:
                #    self.logger.debug(f"{name} = {value}")

        ret_dict = {name: value for name, (value, _) in self.values.items()}
        self.logger.debug(f"returning {ret_dict}")
        return ret_dict
