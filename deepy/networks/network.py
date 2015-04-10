#!/usr/bin/env python
# -*- coding: utf-8 -*-

# TODO: Allow Plugging another network inside

import logging as loggers
import gzip
import cPickle as pickle

import theano.tensor as T
import theano

from deepy.layers.layer import NeuralLayer
from deepy.conf import NetworkConfig

logging = loggers.getLogger(__name__)

DEEPY_MESSAGE = "deepy =============================>"

class NeuralNetwork(object):
    """
    Basic neural network class.
    """

    def __init__(self, input_dim, config=None, input_variable=None):
        logging.info(DEEPY_MESSAGE)
        self.network_config = config if config else NetworkConfig()
        self.input_dim = input_dim
        self.parameter_count = 0

        self.parameters = []
        self.free_parameters = []

        self.training_updates = []
        self.updates = []

        self.input_variables = []
        self.target_variables = []

        self.training_callbacks = []
        self.testing_callbacks = []
        self.epoch_callbacks = []

        self.layers = []

        self._hidden_outputs = []
        self.training_monitors = []
        self.testing_monitors = []

        self._input_variable = input_variable
        self.setup_variables()

        if self.network_config.layers:
            self.stack_layers(self.network_config.layers)

    def stack(self, layer):
        """
        Stack a neural layer.
        :type layer: NeuralLayer
        """
        layer.name += "%d" % (len(self.layers) + 1)
        if not self.layers:
            layer.connect(self.input_dim, network_config=self.network_config)
        else:
            layer.connect(self.layers[-1].output_dim, previous_layer=self.layers[-1], network_config=self.network_config)
        layer.setup()
        self._output = layer.output(self._output)
        self._test_output = layer.test_output(self._test_output)
        self._hidden_outputs.append(self._output)
        self.parameter_count += layer.parameter_count
        self.parameters.extend(layer.parameters)
        self.free_parameters.extend(layer.free_parameters)
        self.training_monitors.extend(layer.training_monitors)
        self.testing_monitors.extend(layer.testing_monitors)
        self.updates.extend(layer.updates)
        self.training_updates.extend(layer.training_updates)
        self.input_variables.extend(layer.external_inputs)

        self.training_callbacks.extend(layer.training_callbacks)
        self.testing_callbacks.extend(layer.testing_callbacks)
        self.epoch_callbacks.extend(layer.epoch_callbacks)
        self.layers.append(layer)

    def first_layer(self):
        return self.layers[0] if self.layers else None

    def stack_layers(self, *layers):
        for layer in layers:
            self.stack(layer)

    def prepare_training(self):
        self.report()
        for i, h in enumerate(self._hidden_outputs):
            self.training_monitors.append(('h{}<0.1'.format(i+1), 100 * (abs(h) < 0.1).mean()))
            self.training_monitors.append(('h{}<0.9'.format(i+1), 100 * (abs(h) < 0.9).mean()))

    @property
    def all_parameters(self):
        params = []
        params.extend(self.parameters)
        params.extend(self.free_parameters)

        return params

    def setup_variables(self):
        if self._input_variable:
            x = self._input_variable
        else:
            x = T.matrix('x')
        self.input_variables.append(x)
        self._output = x
        self._test_output = x

    def _compile(self):
        if not hasattr(self, '_compute'):
            self._compute = theano.function(
                filter(lambda x: x not in self.target_variables, self.input_variables),
                self.test_output, updates=self.updates, allow_input_downcast=True)

    def compute(self, *x):
        self._compile()
        return self._compute(*x)

    @property
    def output(self):
        return self._output

    @property
    def test_output(self):
        return self._test_output

    @property
    def cost(self):
        return T.constant(0)

    @property
    def test_cost(self):
        return self.cost

    def save_params(self, path):
        logging.info("saving parameters to %s" % path)
        opener = gzip.open if path.lower().endswith('.gz') else open
        handle = opener(path, 'wb')
        pickle.dump([p.get_value().copy() for p in self.all_parameters], handle)
        handle.close()

    def load_params(self, path):
        logging.info("loading parameters from %s" % path)
        opener = gzip.open if path.lower().endswith('.gz') else open
        handle = opener(path, 'rb')
        saved = pickle.load(handle)
        for target, source in zip(self.all_parameters, saved):
            logging.info('%s: setting value %s', target.name, source.shape)
            target.set_value(source)
        handle.close()

    def report(self):
        logging.info("network inputs: %s", " ".join(map(str, self.input_variables)))
        logging.info("network targets: %s", " ".join(map(str, self.target_variables)))
        logging.info("network parameters: %s", " ".join(map(str, self.all_parameters)))
        logging.info("parameter count: %d", self.parameter_count)

    def epoch_callback(self):
        for cb in self.epoch_callbacks:
            cb()

    def training_callback(self):
        for cb in self.training_callbacks:
            cb()

    def testing_callback(self):
        for cb in self.training_callbacks:
            cb()