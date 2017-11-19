import tensorflow as tf
import numpy as np
import sys, os

sys.path.insert(0, '.')
sys.path.insert(0, '..')
from basemodel import BaseModel
from discriminator import ConvDiscriminator

from utilities.ops import (
    lrelu,
    linear,
    conv,
    deconv,
    batch_norm)

class VGGBase(BaseModel):
    base_defaults={
        'sess': None,
        'learning_rate': 1e-3,
        'adversarial': False,
        'adversary_lr': 1e-4,
        'adversary_lambda': 1,
        'dataset': None,
        'x_dims': [256, 256, 3],
        'conv_kernels': [32, 64, 128, 256],
        'deconv_kernels': [32, 64],
        'n_classes': None,
        'summary_iters': 50,
        'mode': 'TRAIN',
        'name': 'VGGSeg'}

    def __init__(self, **kwargs):
        self.base_defaults.update(**kwargs)
        super(VGGBase, self).__init__(**self.base_defaults)

        assert self.n_classes is not None
        if self.mode=='TRAIN': assert self.dataset.dstype=='ImageMask'

    def get_update_list(self):
        raise Exception(NotImplementedError)

    def summaries(self):
        raise Exception(NotImplementedError)

    def train_step(self, global_step):
        raise Exception(NotImplementedError)

    def snapshot(self, step):
        raise Exception(NotImplementedError)

    def restore(self, snapshot_path):
        raise Exception(NotImplementedError)

    def test_step(self, keep_prob=1.0):
        raise Exception(NotImplementedError)

    def inference(self, x_in, keep_prob):
        raise Exception(NotImplementedError)

    def loss_op(self):
        raise Exception(NotImplementedError)

    def print_info(self):
        print '------------------------ VGG ---------------------- '
        for key, value in sorted(self.__dict__.items()):
            print '|\t', key, value
        print '------------------------ VGG ---------------------- '


    def model(self, x_in, keep_prob=0.5, reuse=False, training=True):
        print 'VGG-FCN Model'
        with tf.variable_scope(self.name) as scope:
            if reuse:
                scope.reuse_variables()
            print '\t x_in', x_in.get_shape()

            c0_0 = lrelu(conv(x_in, self.conv_kernels[0], k_size=3, stride=1, var_scope='c0_0'))
            c0_1 = lrelu(conv(c0_0, self.conv_kernels[0], k_size=3, stride=1, var_scope='c0_1'))
            c0_1 = batch_norm(c0_1, reuse=reuse, training=training, var_scope='c0_1_bn')
            c0_pool = tf.nn.max_pool(c0_1, [1,2,2,1], [1,2,2,1], padding='VALID',
                name='c0_pool')
            print '\t c0_pool', c0_pool.get_shape() ## 128

            c1_0 = lrelu(conv(c0_pool, self.conv_kernels[1], k_size=3, stride=1, var_scope='c1_0'))
            c1_1 = lrelu(conv(c1_0, self.conv_kernels[1], k_size=3, stride=1, var_scope='c1_1'))
            c1_1 = batch_norm(c1_1, training=training, var_scope='c1_1_bn')
            c1_pool = tf.nn.max_pool(c1_1, [1,2,2,1], [1,2,2,1], padding='VALID',
                name='c1_pool')
            print '\t c1_pool', c1_pool.get_shape() ## 64

            c2_0 = lrelu(conv(c1_pool, self.conv_kernels[2], k_size=3, stride=1, var_scope='c2_0'))
            c2_1 = lrelu(conv(c2_0, self.conv_kernels[2], k_size=3, stride=1, var_scope='c2_1'))
            c2_1 = batch_norm(c2_1, training=training, var_scope='c2_1_bn')
            c2_pool = tf.nn.max_pool(c2_1, [1,2,2,1], [1,2,2,1], padding='VALID',
                name='c2_pool')
            print '\t c2_pool', c2_pool.get_shape() ## 32

            c3_0 = lrelu(conv(c2_pool, self.conv_kernels[3], k_size=3, stride=1, var_scope='c3_0'))
            c3_0 = tf.nn.dropout(c3_0, keep_prob=keep_prob)
            c3_1 = lrelu(conv(c3_0, self.conv_kernels[3], k_size=3, stride=1, var_scope='c3_1'))
            c3_1 = batch_norm(c3_1, training=training, var_scope='c3_1_bn')
            c3_pool = tf.nn.max_pool(c3_1, [1,2,2,1], [1,2,2,1], padding='VALID',
                name='c3_pool')
            print '\t c3_pool', c3_pool.get_shape()  ## inputs / 16 = 16

            d1 = deconv(c3_pool, self.deconv_kernels[1], upsample_rate=4, var_scope='d1')
            d1 = conv(d1, self.deconv_kernels[1], stride=1, var_scope='dc1')
            d1 = batch_norm(d1, reuse=reuse, training=training, var_scope='d1_bn')
            d1 = lrelu(d1)
            print '\t d1', d1.get_shape() ## 16*4 = 64

            d0 = deconv(d1, self.deconv_kernels[0], var_scope='d0')
            d0 = conv(d0, self.deconv_kernels[0], stride=1, var_scope='dc0')
            d0 = batch_norm(d0, training=training, var_scope='d0_bn')
            d0 = lrelu(d0)
            print '\t d0', d0.get_shape() ## 64*2 = 128

            y_hat = deconv(d0, self.n_classes, var_scope='y_hat')
            print '\t y_hat', y_hat.get_shape() ## 128*2 = 256

            return y_hat




class VGGTraining(VGGBase):
    train_defaults = {
    'mode': 'TRAIN'
    }

    def __init__(self, **kwargs):
        self.train_defaults.update(**kwargs)
        super(VGGTraining, self).__init__(**self.train_defaults)

        ## ------------------- Input ops ------------------- ##
        self.x_in = tf.placeholder_with_default(self.dataset.image_op,
            shape=[None, self.x_dims[0], self.x_dims[1], self.x_dims[2]],
                name='x_in')
        self.y_in = tf.placeholder_with_default(self.dataset.mask_op,
            shape=[None, self.x_dims[0], self.x_dims[1], 1], name='y_in')
        # self.x_in = self.dataset.image_op
        # self.y_in = self.dataset.mask_op
        if self.y_in.get_shape().as_list()[-1] != self.n_classes:
            self.y_in_mask = tf.cast(tf.identity(self.y_in), tf.float32)
            # self.y_in_mask = tf.divide(self.y_in_mask, self.n_classes)
            self.y_in = tf.one_hot(self.y_in, depth=self.n_classes)
            self.y_in = tf.squeeze(self.y_in)
            self.y_in = tf.reshape(self.y_in,
                [-1, self.x_dims[0], self.x_dims[1], self.n_classes])
            print 'Converted y_in to one_hot: ', self.y_in.get_shape()

        ## ------------------- Model ops ------------------- ##
        # self.keep_prob = tf.placeholder('float', name='keep_prob')
        self.keep_prob = tf.placeholder_with_default(0.5, shape=[], name='keep_prob')
        self.training = tf.placeholder_with_default(True, shape=[], name='training')
        self.y_hat = self.model(self.x_in, keep_prob=self.keep_prob, reuse=False,
            training=self.training)
        self.y_hat_smax = tf.nn.softmax(self.y_hat)
        self.y_hat_mask = tf.expand_dims(tf.argmax(self.y_hat, -1), -1)
        self.y_hat_mask = tf.cast(self.y_hat_mask, tf.float32)
        # self.y_hat_mask = tf.divide(self.y_hat_mask, self.n_classes)
        print 'Model output y_hat:', self.y_hat.get_shape()

        ## ------------------- Training ops ------------------- ##
        self.var_list = self.get_update_list()
        self.seg_optimizer = tf.train.AdamOptimizer(self.learning_rate, name='VGG_seg_Adam')

        if self.adversarial:
            # self.adv_optimizer = tf.train.AdamOptimizer(self.adversary_lr, name='VGG_adv_Adam')
            self.discriminator = ConvDiscriminator(sess=self.sess,
                x_real=self.y_in, x_fake=tf.nn.softmax(self.y_hat))
            # self.discriminator = ConvDiscriminator(sess=self.sess,
            #     x_real=self.y_in_mask, x_fake=self.y_hat_mask)
            self.discriminator.print_info()
            self.training_op_list += self.discriminator.training_op_list
            self.summary_op_list += self.discriminator.summary_op_list

        self.make_training_ops()
        # self.loss = self.loss_op()

        ## ------------------- Testing ops ------------------- ##
        #self.x_test = tf.placeholder('float',
        #    shape=[None, self.x_dims[0], self.x_dims[1], self.x_dims[2]],
        #    name='x_test')
        #self.y_hat_test = self.model(self.x_test, keep_prob=self.keep_prob, reuse=True, training=False)

        ## ------------------- Gather Summary ops ------------------- ##
        self.summary_op_list += self.summaries()
        self.summary_op = tf.summary.merge(self.summary_op_list)
        self.training_op_list.append(self.summary_op)

        ## ------------------- TensorFlow helpers ------------------- ##
        self.summary_writer = tf.summary.FileWriter(self.log_dir,
            graph=self.sess.graph, flush_secs=30)
        ## Append a model name to the save path
        self.save_dir = os.path.join(self.save_dir, 'vgg_segmentation.ckpt')
        self.saver = tf.train.Saver(max_to_keep=5)
        self.sess.run(tf.global_variables_initializer())

    def make_training_ops(self):
        self.seg_loss = tf.nn.softmax_cross_entropy_with_logits(
            labels=self.y_in, logits=self.y_hat)
        self.seg_loss = tf.reduce_mean(self.seg_loss)

        self.seg_loss_sum = tf.summary.scalar('seg_loss', self.seg_loss)
        self.summary_op_list.append(self.seg_loss_sum)

        ## For batch norm
        # update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
        # with tf.control_dependencies(update_ops):
        #     self.segmentation_train_op = self.seg_optimizer.minimize(
        #         self.seg_loss, var_list=self.var_list)
<<<<<<< HEAD

=======
        #
>>>>>>> 2a38db8a768fb62d8dfa5a313c4e38cdf8c86c9c
        # self.training_op_list.append(self.segmentation_train_op)

        if self.adversarial:
            # p_real_fake = tf.stop_gradient(self.discriminator.model(self.y_hat_mask, reuse=True))
            p_real_fake = self.discriminator.p_real_fake
            real_target = tf.ones_like(p_real_fake)
            self.adv_loss = tf.nn.sigmoid_cross_entropy_with_logits(
                labels=real_target, logits=p_real_fake)
            self.adv_loss = tf.reduce_mean(self.adv_loss)
            
            self.adv_loss_sum = tf.summary.scalar('adv_loss', self.adv_loss)
            self.summary_op_list.append(self.adv_loss_sum)

            # self.adversarial_train_op = self.adv_optimizer.minimize(
            #     self.adv_loss, var_list=self.var_list)
            # self.training_op_list.append(self.adversarial_train_op)
<<<<<<< HEAD
            self.loss = self.seg_loss + self.adv_loss
=======
            self.loss = self.seg_loss + self.adversary_lambda * self.adv_loss
>>>>>>> 2a38db8a768fb62d8dfa5a313c4e38cdf8c86c9c
        else:
            self.loss = self.seg_loss

        update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
        with tf.control_dependencies(update_ops):
<<<<<<< HEAD
            self.training_op = self.optimizer.minimize(self.loss, var_list=self.var_list)
        self.training_op_list.append(self.training_op)

=======
            self.training_op = self.seg_optimizer.minimize(
                self.loss, var_list=self.var_list)

        self.training_op_list.append(self.training_op)



>>>>>>> 2a38db8a768fb62d8dfa5a313c4e38cdf8c86c9c

    def get_update_list(self):
        t_vars = tf.trainable_variables()
        return [var for var in t_vars if self.name in var.name]

    def summaries(self):
        ## Input image
        x_in_sum = tf.summary.image('x_in', self.x_in, max_outputs=4)
        y_in_sum = tf.summary.image('y_in', self.y_in_mask, max_outputs=4)
        y_hat_sum = tf.summary.image('y_hat', self.y_hat_mask, max_outputs=4)
        ## Loss scalar
        loss_sum = tf.summary.scalar('loss', self.loss)
        ## Filters
        # TODO

        return [x_in_sum, y_in_sum, y_hat_sum, loss_sum]

    def train_step(self, global_step):
        summary_str = self.sess.run(self.training_op_list)[-1]
        if global_step % self.summary_iters == 0:
            self.summary_writer.add_summary(summary_str, global_step)

    def train_step_return_values(self, global_step):
        train_return_ = self.sess.run(self.training_op_list+[self.x_in, self.y_in, self.y_hat_mask])
        return_x = train_return_[-3]
        return_y = train_return_[-2]
        return_y_hat = train_return_[-1]
        if global_step % self.summary_iters == 0:
            summary_str = train_return_[-4]
            self.summary_writer.add_summary(summary_str, global_step)

        return return_x, return_y, return_y_hat

    def snapshot(self, step):
        print 'Snapshotting to [{}] step [{}]'.format(self.save_dir, step),
        self.saver.save(self.sess, self.save_dir, global_step=step)
        print 'Done'

    def restore(self, snapshot_path):
        print 'Restoring from {}'.format(snapshot_path)
        try:
            self.saver.restore(self.sess, snapshot_path)
            print 'Success!'
        except:
            print 'Failed! Continuing without loading snapshot.'

    def inference(self, x_in, keep_prob):
        feed_dict = {self.x_in: x_in,
                     self.keep_prob: keep_prob,
                     self.training: False}
        y_hat_ = self.sess.run([self.y_hat_smax], feed_dict=feed_dict)[0]
        # y_hat_smax = tf.nn.softmax(y_hat_)

        return y_hat_




class VGGInference(VGGBase):
    inference_defaults = {
        'mode': 'TEST'
    }

    def __init__(self, **kwargs):
        self.inference_defaults.update(**kwargs)
        super(VGGInference, self).__init__(**self.inference_defaults)

        ## ------------------- Input ops ------------------- ##
        self.x_in = tf.placeholder('float',
            shape=[None, self.x_dims[0], self.x_dims[1], self.x_dims[2]],
            name='x_in')

        ## ------------------- Model ops ------------------- ##
        # self.keep_prob = tf.placeholder('float', name='keep_prob')
        self.keep_prob = tf.placeholder_with_default(0.5, shape=[], name='keep_prob')
        self.training = tf.placeholder_with_default(False, shape=[], name='training')
        self.y_hat = self.model(self.x_in, keep_prob=self.keep_prob, reuse=False,
            training=self.training)

        # self.y_hat_mask = tf.expand_dims(tf.argmax(self.y_hat, -1), -1)
        # self.y_hat_mask = tf.cast(self.y_hat_mask, tf.float32)

        self.saver = tf.train.Saver(max_to_keep=5)
        self.sess.run(tf.global_variables_initializer())

    def inference(self, x_in, keep_prob):
        feed_dict = {self.x_in: x_in,
                     self.keep_prob: keep_prob}
        y_hat_ = self.sess.run([self.y_hat_smax], feed_dict=feed_dict)[0]
        # y_hat_smax = tf.nn.softmax(y_hat_)

        return y_hat_


    def restore(self, snapshot_path):
        print 'Restoring from {}'.format(snapshot_path)
        try:
            self.saver.restore(self.sess, snapshot_path)
            print 'Success!'
        except:
            print 'Failed! Continuing without loading snapshot.'
