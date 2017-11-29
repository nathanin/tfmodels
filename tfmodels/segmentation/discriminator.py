import tensorflow as tf
from ..generative.discriminator_basemodel import BaseDiscriminator
from ..utilities.ops import *

class SegmentationDiscriminator(BaseDiscriminator):
    seg_discrim_defaults={
        'discriminator_train_op_list': [],
        'kernels': [32, 32, 32, 128],
        'learning_rate': 5e-5,
        'name': 'adversary',
        'soften_labels': True,
        'soften_sddev': 0.01,
        'x_in': None,
        'y_real': None,
        'y_fake': None,
    }

    def __init__(self, **kwargs):
        self.seg_discrim_defaults.update(kwargs)
        super(SegmentationDiscriminator, self).__init__(**self.seg_discrim_defaults)

        assert self.y_fake is not None
        assert self.y_real is not None

        ## Label softening add noise ~ N(0,0.01)
        if self.soften_labels:
            epsilon = tf.random_normal(shape=tf.shape(self.y_real),
                mean=0.0, stddev=self.soften_sddev)
            self.y_real = self.y_real + epsilon

        ## Set up the real prob, fake prob
        self.p_real_fake, self.real_features = self.model(self.y_fake, self.x_in)
        self.p_real_real, self.fake_features = self.model(self.y_real, self.x_in, reuse=True)

        ## Then call _make_training_op
        self._make_training_op()


    def model(self, y_hat, x_in, keep_prob=0.5, reuse=False, training=True):
        print 'Convolutional Discriminator'
        nonlin = self.nonlin
        print 'Nonlinearity: ', nonlin

        with tf.variable_scope(self.name) as scope:
            if reuse:
                scope.reuse_variables()
            print '\t y_hat', y_hat.get_shape()

            y_hat_x_in = tf.concat([y_hat, x_in], axis=-1)
            print '\t y_hat_x_in', y_hat_x_in.get_shape()

            h0_0 = nonlin(conv(y_hat_x_in, self.kernels[0], k_size=5, stride=1, var_scope='h0_0'))
            h0_1 = nonlin(conv(h0_0, self.kernels[0], k_size=5, stride=1, var_scope='h0_1'))
            h0_pool = tf.nn.max_pool(h0_1, [1,4,4,1], [1,4,4,1], padding='VALID', name='h0_pool')
            print '\t h0_pool', h0_pool.get_shape()

            h1_0 = nonlin(conv(h0_pool, self.kernels[1], stride=1, var_scope='h1_0'))
            h1_1 = nonlin(conv(h1_0, self.kernels[1], stride=1, var_scope='h1_1'))
            h1_pool = tf.nn.max_pool(h1_1, [1,2,2,1], [1,2,2,1], padding='VALID', name='h1_pool')
            print '\t h1_pool', h1_pool.get_shape()

            h2_0 = nonlin(conv(h1_pool, self.kernels[2], stride=1, var_scope='h2_0'))
            h2_1 = nonlin(conv(h2_0, self.kernels[2], stride=1, var_scope='h2_1'))
            h2_pool = tf.nn.max_pool(h2_1, [1,2,2,1], [1,2,2,1], padding='VALID', name='h2_pool')
            print '\t h2_pool', h2_pool.get_shape()

            h_flat = tf.contrib.layers.flatten(h2_pool)
            h_flat = tf.contrib.nn.alpha_dropout(h_flat, keep_prob=keep_prob, name='h_flat_do')
            print '\t h_flat', h_flat.get_shape()

            h3 = nonlin(linear(h_flat, self.kernels[3], var_scope='h3'))
            # h3 = tf.contrib.nn.alpha_dropout(h3, keep_prob=keep_prob, name='h3_do')
            print '\t h3', h3.get_shape()

            p_real = linear(h3, 1, var_scope='p_real')
            print '\t p_real', p_real.get_shape()

            return p_real, h3


    def inference(self, x_in, keep_prob=1.0):
        p_real_ = self.sess.run([self.p_real_fake], feed_dict={self.x_fake: x_in})[0]
        return p_real_


    def _make_loss(self):
        real_target = tf.ones_like(self.p_real_real)
        fake_target = tf.zeros_like(self.p_real_fake)

        if self.soften_labels:
            real_epsilon = tf.random_normal(shape=tf.shape(real_target),
                mean=0.0, stddev=self.soften_sddev)
            fake_epsilon = tf.random_normal(shape=tf.shape(fake_target),
                mean=0.0, stddev=self.soften_sddev)
            real_target = real_target + real_epsilon
            fake_target = fake_target + fake_epsilon

        loss_real = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(
            labels=real_target, logits=self.p_real_real))
        loss_fake = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(
            labels=fake_target, logits=self.p_real_fake))
        # return (loss_real + loss_fake) / 2.0
        return loss_real + loss_fake


    def _make_training_op(self):
        with tf.name_scope('discriminator_losses'):
            self.var_list = self.get_update_list()
            self.optimizer = tf.train.AdamOptimizer(self.learning_rate,
                name='{}_Adam'.format(self.name))

            self.loss = self._make_loss()
            self.train_op = self.optimizer.minimize(self.loss,
                var_list=self.var_list, name='{}_train'.format(self.name))
            self.discriminator_train_op_list.append(self.train_op)

            # Summary
            self.disciminator_loss_sum = tf.summary.scalar('{}_loss'.format(self.name),
                self.loss)
            self.summary_op_list.append(self.disciminator_loss_sum)
