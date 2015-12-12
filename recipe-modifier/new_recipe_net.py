from __future__ import absolute_import
# from __future__ import division
from __future__ import print_function

import time

import tensorflow.python.platform

import numpy as np
import tensorflow as tf

from tensorflow.models.rnn import rnn
from tensorflow.models.rnn import rnn_cell
from tensorflow.models.rnn import seq2seq


class RecipeNet(object):
	def __init__(self, is_training, config):
		self._batch_size = 1

		encoder_size = config.encoder_hidden_size
		vocab_size = config.vocab_size

		# Slightly better results can be obtained with forget gate biases
		# initialized to 1 but the hyperparameters of the model would need to be
		# different than reported in the paper.
		encoder_lstm_cell = rnn_cell.BasicLSTMCell(encoder_size, forget_bias=0.0)
		if is_training and config.keep_prob < 1:
			encoder_lstm_cell = rnn_cell.DropoutWrapper(encoder_lstm_cell, output_keep_prob=config.keep_prob)
		self.encoder = rnn_cell.MultiRNNCell([encoder_lstm_cell] * config.num_layers)

		self._initial_encoder_state = tf.ones([recipe_processor_size])
		self._embedding_matrix = tf.get_variable("embedding_matrix", [vocab_size, encoder_size])


		recipe_processor_size = config.recipe_processor_hidden_size

		recipe_processor_lstm_cell = rnn_cell.BasicLSTMCell(recipe_processor_size, forget_bias=0.0)
		if is_training and config.keep_prob < 1:
			recipe_processor_lstm_cell = rnn_cell.DropoutWrapper(recipe_processor_lstm_cell, output_keep_prob=config.keep_prob)
		self.recipe_processor = rnn_cell.MultiRNNCell([recipe_processor_lstm_cell] * config.num_layers)

		self._initial_recipe_processor_state = tf.ones([recipe_processor_size])

		self.index_predictor_W = weight_variable([recipe_processor_size, 2])
		self.index_predictor_b = bias_variable([2])

		# self._input_refinement = tf.placeholder(tf.int32, [self._batch_size, None])
		# self._input_recipe_segment = tf.placeholder(tf.int32, [self._batch_size, None])
		
		# self._target = tf.placeholder(tf.int32, [self._batch_size, 1])

		# with tf.device("/cpu:0"):
		# 	# embedding = tf.get_variable("embedding", [vocab_size, encoder_size])
		# 	inputs = tf.split(
		# 		1, num_steps, tf.nn.embedding_lookup(embedding, self._input_refinement))
		# 	inputs = [tf.squeeze(input_, [1]) for input_ in inputs]

		# if is_training and config.keep_prob < 1:
		# 	inputs = [tf.nn.dropout(input_, config.keep_prob) for input_ in inputs]

		# # Simplified version of tensorflow.models.rnn.rnn.py's rnn().
		# # This builds an unrolled LSTM for tutorial purposes only.
		# # In general, use the rnn() or state_saving_rnn() from rnn.py.
		# #
		# # The alternative version of the code below is:
		# #
		# encoder_outputs, encoder_states = rnn.rnn(self.encoder, inputs, initial_state=self._initial_encoder_state)

		# output = tf.reshape(tf.concat(1, encoder_outputs), [-1, encoder_size])
		# logits = tf.nn.xw_plus_b(output,
		# 						tf.get_variable("softmax_w", [encoder_size, vocab_size]),
		# 						tf.get_variable("softmax_b", [vocab_size]))
		# loss = seq2seq.sequence_loss_by_example([logits],
		# 										[tf.reshape(self._targets, [-1])],
		# 										[tf.ones([self._batch_size * num_steps])],
		# 										vocab_size)
		# self._cost = cost = tf.reduce_sum(loss) / self._batch_size
		# self._final_state = encoder_states[-1]

		# if not is_training:
		#   return

		# self._lr = tf.Variable(0.0, trainable=False)
		# tvars = tf.trainable_variables()
		# grads, _ = tf.clip_by_global_norm(tf.gradients(cost, tvars),
		#                                   config.max_grad_norm)
		# optimizer = tf.train.GradientDescentOptimizer(self.lr)
		# self._train_op = optimizer.apply_gradients(zip(grads, tvars))

	def get_encoded_segment(self, segment):
		input_segment = tf.constant(segment)
		inputs = tf.split(1, len(segment), tf.nn.embedding_lookup(self._embedding_matrix, input_segment))
		inputs = [tf.squeeze(input_, [1]) for input_ in inputs]

		encoder_outputs, encoder_states = rnn.rnn(self.encoder, inputs, initial_state=self._initial_encoder_state)
		return encoder_outputs[-1]

	def get_index_predictions(self, recipe_segments, refinement):
		encoded_recipe_segments = []
		for segment in recipe_segments:
			encoded_recipe_segments.append(self.get_encoded_segment(segment))
		encoded_refinement = self.get_encoded_segment(refinement)

		inputs = [tf.concat(0,[encoded_refinement, seg]) for seg in encoded_recipe_segments]
		recipe_processor_outputs, recipe_processor_states = rnn.rnn(self.recipe_processor, inputs, initial_state=self._initial_recipe_processor_state)

		logits_per_index = []
		for output in recipe_processor_outputs:
			logits_per_index.append( tf.nn.xw_plus_b(output, self.index_predictor_W, self.index_predictor_b) )
		return logits_per_index

	def process_labeled_example(self, recipe_segments, refinement, refinement_index):

		logits = tf.concat(0, self.get_index_predictions(recipe_segments, refinement))

		print('logits shape: {0}'.format(logits.get_shape()))

		targets_as_list = [0]*len(recipe_segments)
		targets_as_list[refinement_index] = 1
		targets = tf.constant(targets_as_list, tf.int32)

		loss = seq2seq.sequence_loss_by_example([logits],
												[targets],
												[tf.ones([len(recipe_segments)])],
												2)
		self._cost = cost = tf.reduce_sum(loss)

		self._lr = tf.Variable(0.0, trainable=False)
		tvars = tf.trainable_variables()
		grads, _ = tf.clip_by_global_norm(tf.gradients(cost, tvars),
		                                  config.max_grad_norm)
		optimizer = tf.train.GradientDescentOptimizer(self.lr)
		self._train_op = optimizer.apply_gradients(zip(grads, tvars))


	def assign_lr(self, session, lr_value):
    	session.run(tf.assign(self.lr, lr_value))

	# @property
	# def input_data(self):
	# 	return self._input_data

	# @property
	# def targets(self):
	# 	return self._targets

	# @property
	# def initial_state(self):
	# 	return self._initial_state

	@property
	def cost(self):
		return self._cost

	# @property
	# def final_state(self):
	# 	return self._final_state

	@property
	def lr(self):
		return self._lr

	@property
	def train_op(self):
		return self._train_op

	def weight_variable(shape):
		initial = tf.truncated_normal(shape, stddev=0.1)
		return tf.Variable(initial)

	def bias_variable(shape):
		initial = tf.constant(0.1, shape=shape)
		return tf.Variable(initial)

class Config(object):
	"""Configuration parameters."""
	init_scale = 0.1
	learning_rate = 1.0
	max_grad_norm = 5
	num_layers = 2
	num_steps = 20
	encoder_hidden_size = 200
	recipe_processor_hidden_size = 400  # must be 2x the size of encoder_hidden_size
	max_epoch = 4
	max_max_epoch = 8
	keep_prob = 1.0
	lr_decay = 0.5
	batch_size = 20

	def __init__(self, n=10000):
		self.vocab_size = n

