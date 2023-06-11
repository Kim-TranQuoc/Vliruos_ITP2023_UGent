##########################################################################################
### Model_1.py: A simple ANN model with 2 phases (train and test) ###
# Funding agency: Vlir-ous International Training Progamme (ITP) 2023 at Ghent university, Belgium
# Project title: Machine learning for climate change mitigation in buildings
# Author: Kim Q. Tran, CIRTech Institude, HUTECH university, Vietnam
# ! This work can be used, modified, and shared under the MIT License
# ! This work is included in the Github project: https://github.com/Kim-TranQuoc/Vlirous_ITP2023_UGent
# ! Email: tq.kim@hutech.edu.vn or tqkim.work@gmail.com
##########################################################################################

import ctypes
import multiprocessing as mp
from multiprocessing import Manager
from itertools import repeat, product

import tensorflow as tf
from tensorflow import keras
from keras.layers.core import Activation
from keras.utils.generic_utils import get_custom_objects
from sklearn.model_selection import KFold
from sklearn.model_selection import train_test_split
# from sklearn.metrics import mean_squared_error
# from sklearn.metrics import mean_absolute_error
from sklearn.metrics import r2_score
from sklearn.preprocessing import MinMaxScaler
# from sklearn.utils import shuffle

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import timeit
import time
import os
from datetime import datetime
import psutil
from os import getpid
import re

CPU_usage = []
var_dict = {}


class TimeHistory(keras.callbacks.Callback):
    def on_epoch_end(self, epoch, logs=None):
        logs['time'] = timeit.default_timer()


def get_data():
    data_df = pd.read_csv('./data/Data_Infor.csv', header=None)
    data_infor = data_df.to_numpy()

    data_folder_path = './data/Rand120Mod'
    data_files = [file for file in os.listdir(data_folder_path) if file.endswith(".csv")]

    data_X = np.zeros([len(data_files), 7])
    data_y = np.zeros([len(data_files), 1])
    for file_no, file_name in enumerate(data_files):
        index = np.where(data_infor[:, 0] == file_name.replace('.csv', ''))
        data_X[file_no, :] = data_infor[index, 1:8].flatten()
        data_df = pd.read_csv(os.path.join(data_folder_path, file_name), header=None)
        data_arr = data_df.to_numpy()
        data_y[file_no, :] = np.sum(np.asarray(data_arr[0:3, :]))/1000  # From kWh to MWh

    train_X, test_X, train_y, test_y = train_test_split(data_X, data_y, test_size=0.2, random_state=42)

    print('----- Data summary -----')
    print(f'> Number of data samples: {len(data_files)} samples')
    print(f'> Number of data samples for train: {train_X.shape[0]} samples')
    print(f'> Number of data samples for test: {test_X.shape[0]} samples')
    print(f'> Real ratio of train - test data : {train_X.shape[0]/len(data_files)*100:.1f}% - {test_X.shape[0]/len(data_files)*100:.1f}%')

    return train_X, train_y, test_X, test_y


def scale_data(data, data_range, scaled_range):
    scaled_data = data
    for i in range(data.shape[1]):
        scaler = MinMaxScaler(feature_range=scaled_range)
        scaler.fit(data_range[i, :].reshape(-1, 1))
        scaled_data[:, i] = scaler.transform(data[:, i].reshape(-1, 1)).flatten()
    return scaled_data


def inverse_scale_data(scaled_data, data_range, scaled_range):
    inv_scaled_data = scaled_data
    for i in range(scaled_data.shape[1]):
        scaler = MinMaxScaler(feature_range=scaled_range)
        scaler.fit(data_range[i, :].reshape(-1, 1))
        inv_scaled_data[:, i] = scaler.inverse_transform(scaled_data[:, i].reshape(-1, 1)).flatten()
    return inv_scaled_data


def define_model():
    # Define model hyperparameters
    Model_HiddenLayers = [4]  # [2, 3, ...]
    Model_LayerNodes = [500, 500, 500, 500]  # [50, 100, 150, ...]
    Model_Activations = ['ReLU']  # ['ReLU', 'SoftPlus', 'Sigmoid', 'ChebyshevPoly2', 'ChebyshevPoly3']
    Model_Optimizers = ['Adam']  # ['Adam', 'SGD', 'Adadelta', 'RMSprop', 'Adagrad']
    # Check the learning rate
    Model_BatchSize = [100]  # [32, 50, 100, 200]
    Model_MaxEpoch = [500]

    # Define model architecture
    Model_Architecture = {'layers': Model_HiddenLayers[0],
                          'nodes': Model_LayerNodes}

    # Select model
    Model_Options = {'Layers': Model_Architecture['layers'],
                     'Nodes': Model_Architecture['nodes'],
                     'Activation': Model_Activations[0],
                     'Optimizer': Model_Optimizers[0],
                     'BatchSize': Model_BatchSize[0],
                     'MaxEpoch': Model_MaxEpoch[0]}
    return Model_Options


def model_train(train_X, train_y, test_X, test_y, model_hyperparams, results, result_dir):
    input_shape = (train_X.shape[1],)
    output_shape = train_y.shape[1]

    Layer_opt = model_hyperparams['Layer_opt']
    Node_opt = model_hyperparams['Node_opt']
    Activation_opt = model_hyperparams['Activation_opt']
    Optimizer_opt = model_hyperparams['Optimizer_opt']
    Batch_size_opt = model_hyperparams['Batch_size_opt']
    Max_Epoch_opt = model_hyperparams['Max_Epoch_opt']

    # Activation
    if Activation_opt == 'ReLU':
        acti_func = keras.activations.relu
    elif Activation_opt == 'SoftPlus':
        acti_func = keras.activations.softplus
    elif Activation_opt == 'Sigmoid':
        acti_func = keras.activations.sigmoid

    # Model architecture
    model = keras.Sequential([keras.layers.Dense(Node_opt[0], input_shape=input_shape, activation=acti_func)])
    for i_lay in range(Layer_opt - 1):
        model.add(keras.layers.Dense(Node_opt[i_lay+1], activation=acti_func))
    model.add(keras.layers.Dense(output_shape, activation='linear'))

    # Optimizer
    if Optimizer_opt == 'Adam':
        Opti_algo = keras.optimizers.Adam(lr=0.005, beta_1=0.9, beta_2=0.999, epsilon=1e-08)
    elif Optimizer_opt == 'SGD':
        Opti_algo = keras.optimizers.SGD(lr=0.001, momentum=0.9)
    elif Optimizer_opt == 'Adadelta':
        Opti_algo = keras.optimizers.Adadelta(lr=1.0, rho=0.95, epsilon=1e-08)
    elif Optimizer_opt == 'RMSprop':
        Opti_algo = keras.optimizers.RMSprop(lr=0.01, rho=0.9, epsilon=1e-08)
    elif Optimizer_opt == 'Adagrad':
        Opti_algo = keras.optimizers.Adagrad(lr=0.002, epsilon=1e-08)

    # Model compile
    model.compile(optimizer=Opti_algo,
                  loss=keras.losses.MeanSquaredError(),
                  metrics=[keras.metrics.RootMeanSquaredError(), keras.metrics.MeanAbsoluteError()])

    csv_logger = keras.callbacks.CSVLogger(os.path.join(result_dir, 'Train_History.csv'),
                                           separator=',', append=True)
    check_point = keras.callbacks.ModelCheckpoint(os.path.join(result_dir, 'Best_Model.h5'),
                                                  monitor='loss', mode='min', verbose=1, save_best_only=True)

    # Fit data
    history = model.fit(train_X, train_y,
                        validation_data=(test_X, test_y),
                        batch_size=Batch_size_opt,
                        epochs=Max_Epoch_opt,
                        verbose=0,
                        shuffle=True,
                        callbacks=[TimeHistory(), csv_logger, check_point])

    # Evaluation test
    results['History'] = history
    results['Best_epoch'] = np.min(np.where(np.asarray(history.history['loss']) == check_point.best)[0]) + 1

    return results


def main():
    total_time_start = timeit.default_timer()

    # Make result directory
    script_dir = os.path.dirname(__file__)
    current_file = os.path.splitext(os.path.basename(__file__))[0]
    dt_string = datetime.now().strftime("%y%m%d_%H%M%S")
    result_dir = os.path.join(script_dir, 'Results', 'Train_Test', current_file, dt_string)
    if not os.path.isdir(result_dir):
        os.makedirs(result_dir)

    # Get data
    train_X, train_y, test_X, test_y = get_data()
    new_df = pd.DataFrame(np.hstack((train_X, train_y)))
    new_df.to_csv(os.path.join(result_dir, 'Train_Data.csv'), header=None, index=False)
    new_df = pd.DataFrame(np.hstack((test_X, test_y)))
    new_df.to_csv(os.path.join(result_dir, 'Test_Data.csv'), header=None, index=False)

    # Scale data
    data_range = np.array([[0, 5], [100, 500], [50, 350], [0.5, 1.5], [1, 3], [0.4, 1.6], [18, 28]])
    scaled_range = (0, 1)
    train_X = scale_data(train_X, data_range, scaled_range)
    test_X = scale_data(test_X, data_range, scaled_range)

    # Get model
    Model_Options = define_model()

    # Start task
    Model_report = []
    model_time_start = timeit.default_timer()

    model_hyperparams = Manager().dict()
    model_hyperparams['Layer_opt'] = Model_Options['Layers']
    model_hyperparams['Node_opt'] = Model_Options['Nodes']
    model_hyperparams['Activation_opt'] = Model_Options['Activation']
    model_hyperparams['Optimizer_opt'] = Model_Options['Optimizer']
    model_hyperparams['Batch_size_opt'] = Model_Options['BatchSize']
    model_hyperparams['Max_Epoch_opt'] = Model_Options['MaxEpoch']

    results = {}

    # Selection print
    print(f'----- Training Process -----')

    # Training
    train_time_start = timeit.default_timer()
    results = model_train(train_X, train_y, test_X, test_y, model_hyperparams, results, result_dir)
    train_time_stop = timeit.default_timer()

    # Evaluation
    model = keras.models.load_model(os.path.join(result_dir, 'Best_Model.h5'))
    model_hyperparams['Total_params'] = model.count_params()

    train_scores = model.evaluate(train_X, train_y, batch_size=None)
    test_scores = model.evaluate(test_X, test_y, batch_size=None)

    # Save predictions
    predict_train_y = model.predict(train_X, batch_size=None)
    predict_test_y = model.predict(test_X, batch_size=None)

    # Inverse scale data
    train_X = inverse_scale_data(train_X, data_range, scaled_range)
    test_X = inverse_scale_data(test_X, data_range, scaled_range)

    new_df = pd.DataFrame(np.hstack((train_X, predict_train_y)))
    new_df.to_csv(os.path.join(result_dir, 'Predict_Train_Data.csv'), header=None, index=False)
    new_df = pd.DataFrame(np.hstack((test_X, predict_test_y)))
    new_df.to_csv(os.path.join(result_dir, 'Predict_Test_Data.csv'), header=None, index=False)

    # Accessment scores
    best_epoch = results['Best_epoch']
    print('----- Training Accessment -----')
    print(f'> Best epoch: {best_epoch}')
    print(f'> Train: - Loss MSE: {train_scores[0]:.3e}')
    print(f'         - Metric RMSE: {train_scores[1]:.3e}')
    print(f'         - Metric MAE: {train_scores[2]:.3e}')
    print(f'> Test: - Loss MSE: {test_scores[0]:.3e}')
    print(f'        - Metric RMSE: {test_scores[1]:.3e}')
    print(f'        - Metric MAE: {test_scores[2]:.3e}')

    # Statistics scores
    r2_scores = np.array([r2_score(train_y, predict_train_y), r2_score(test_y, predict_test_y)])
    n = np.array([train_X.shape[0], test_X.shape[0]])
    k = np.array([train_X.shape[1], test_X.shape[1]])
    adj_r2_scores = (1 - (1 - r2_scores) * (n - 1) / (n - k - 1))
    print('----- Statistics Scores -----')
    print(f'> Train: - R2 score: {r2_scores[0]:.3e}')
    print(f'         - Adj R2 score: {adj_r2_scores[0]:.3e}')
    print(f'> Test: - R2 score: {r2_scores[1]:.3e}')
    print(f'        - Adj R2 score: {adj_r2_scores[1]:.3e}')

    predict_train_y = model.predict(train_X)
    predict_test_y = model.predict(test_X)
    new_df = pd.DataFrame(np.hstack((train_X, predict_train_y)))
    new_df.to_csv(os.path.join(result_dir, 'Predict_Train_Data.csv'), header=None, index=False)
    new_df = pd.DataFrame(np.hstack((test_X, predict_test_y)))
    new_df.to_csv(os.path.join(result_dir, 'Predict_Test_Data.csv'), header=None, index=False)

    r2_train = r2_score(train_y, predict_train_y)
    (n_train, k_train) = train_X.shape
    adj_r2_train = 1 - (1 - r2_train) * (n_train - 1) / (n_train - k_train - 1)
    r2_test = r2_score(test_y, predict_test_y)
    (n_test, k_test) = train_X.shape
    adj_r2_test = 1 - (1 - r2_test) * (n_test - 1) / (n_test - k_test - 1)

    # Display training time
    print('----- Trainning summary ----- ')
    print('> Model total parameters:')
    print(model_hyperparams['Total_params'])
    model_time_stop = timeit.default_timer()
    print(f'> Training time = {train_time_stop - train_time_start:.3f}s')
    print(f'> Model time = {model_time_stop - model_time_start:.3f}s')
    print('=====')
    print()

    # Save result
    Model_report.append(['Model_1', model_hyperparams['Layer_opt'],
                         model_hyperparams['Node_opt'], model_hyperparams['Activation_opt'],
                         model_hyperparams['Total_params'], model_hyperparams['Optimizer_opt'],
                         model_hyperparams['Batch_size_opt'], model_hyperparams['Max_Epoch_opt'],
                         train_scores[0], train_scores[1], train_scores[2],
                         test_scores[0], test_scores[1], test_scores[2],
                         r2_train, adj_r2_train, r2_test, adj_r2_test,
                         train_time_stop - train_time_start, model_time_stop - model_time_start,
                         best_epoch])

    # Display history graph
    # Loss Value
    history = results['History']
    plt.figure('Convergence History')
    plt.plot(history.history['loss'], c='b', label='Train')
    plt.plot(history.history['test_loss'], c='r', label='Test')
    plt.legend(loc='upper right')
    plt.title('Model Loss (MSE) Convergence History')
    plt.xlabel('Epochs')
    plt.ylabel('Loss value')
    plt.savefig(os.path.join(result_dir, 'Convergence_History.png'), dpi=400)

    # Display statistic comparison graph
    plt.figure('Comparison of true and predicted dataset')
    plot_range = [min(np.concatenate((train_y, test_y))), max(np.concatenate((train_y, test_y)))]
    plt.plot(plot_range, plot_range, c='k', label='X=Y')
    plt.scatter(train_y, predict_train_y, c='b', label='Train')
    plt.scatter(test_y, predict_test_y, c='r', label='Test')
    plt.legend(loc='lower right')
    plt.title('Statistic Comparison of True and Predicted Data')
    plt.xlabel('True data')
    plt.ylabel('Predicted data')
    plt.text(plot_range[0], 0.95*plot_range[1], f'R2_train =  {r2_scores[0]:.3f}', ha='left', va='bottom')
    plt.text(plot_range[0], 0.95*plot_range[1], f'Adj-R2_train = {adj_r2_scores[0]:.3f}', ha='left', va='top')
    plt.text(plot_range[0], 0.875*plot_range[1], f'R2_test =  {r2_scores[1]:.3f}', ha='left', va='bottom')
    plt.text(plot_range[0], 0.875*plot_range[1], f'Adj-R2_test = {adj_r2_scores[1]:.3f}', ha='left', va='top')
    plt.savefig(os.path.join(result_dir, 'Statistics_Score.png'), dpi=400)
    # plt.show()
    plt.close('all')

    # Save result
    headers = ['Model Architecture', 'Number of Layers', 'Nodes per layer', 'Activation Function',
               'Total Parameters', 'Optimizer',
               'Batch Size', 'Max Epoch',
               'train_MSE', 'train_RMSE', 'train_MAE',
               'test_MSE', 'test_RMSE', 'test_MAE',
               'R2_train', 'Adj-R2_train', 'R2_test', 'Adj-R2_test',
               'Training Time (s)', 'Model Time (s)',
               'Best Epoch']

    new_df = pd.DataFrame(Model_report)
    new_df.to_csv(os.path.join(result_dir, 'Result.csv'), header=headers, index=False)

    # Total time
    total_time_stop = timeit.default_timer()
    print(f'>> Total running time = {total_time_stop - total_time_start:.3f}s')


if __name__ == '__main__':
    # for i_tune in range(10):
    main()
