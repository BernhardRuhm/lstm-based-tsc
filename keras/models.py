import tensorflow as tf
from tensorflow import keras

from keras.layers import Conv1D, BatchNormalization, GlobalAveragePooling1D, Permute, Dropout, Flatten
from keras.layers import Input, InputLayer, Dense, LSTM, Concatenate, Activation, RNN 
from keras.models import Sequential, Model 

from custom_layers import FocusedLSTMCell, PositionalEncoding 


def gen_vanilla_dense(input_dim, seq_len, n_layers, hidden_size, n_classes, batch_size, positional_encoding=False):
    model = Sequential()
    model.add(InputLayer(input_shape=(seq_len, input_dim), batch_size=batch_size))

    if positional_encoding == True:
        model.add(PositionalEncoding())

    for _ in range(n_layers-1):
        model.add(LSTM(hidden_size, return_sequences=True))

    model.add(LSTM(hidden_size))
    model.add(Dense(n_classes, activation="softmax"))

    return model

def gen_focused_dense(input_dim, seq_len, n_layers, hidden_size, n_classes, batch_size, positional_encoding=False):
    model = Sequential() 
    model.add(InputLayer(input_shape=(seq_len, input_dim), batch_size=batch_size))

    if positional_encoding == True:
        model.add(PositionalEncoding())

    for _ in range(n_layers-1):
        model.add(RNN(cell=FocusedLSTMCell(hidden_size), return_sequences=True))

    model.add(RNN(cell=FocusedLSTMCell(hidden_size)))
    model.add(Dense(n_classes, activation="softmax"))
    
    return model

def gen_lstmfcn(input_dim, seq_len, n_layers, hidden_size, n_classes, batch_size, positional_encoding=False):

    ip = Input(shape=(seq_len, input_dim), batch_size=batch_size)

    x = LSTM(hidden_size)(ip)
    x = Dropout(0.8)(x)

    # y = Permute((2, 1))(ip)
    y = Conv1D(32, 8, padding='same', kernel_initializer='he_uniform')(ip)
    y = BatchNormalization()(y)
    y = Activation('relu')(y)

    y = Conv1D(64, 5, padding='same', kernel_initializer='he_uniform')(y)
    y = BatchNormalization()(y)
    y = Activation('relu')(y)

    y = Conv1D(32, 3, padding='same', kernel_initializer='he_uniform')(y)
    y = BatchNormalization()(y)
    y = Activation('relu')(y)

    y = GlobalAveragePooling1D()(y)
    
    x = Concatenate(axis=1)([x, y])
    out = Dense(n_classes, activation='softmax')(x)

    model = Model(ip, out)

    return model


valid_models = [
    ("lstm_fcn", gen_lstmfcn),
    ("vanilla_lstm", gen_vanilla_dense), 
    ("focused_lstm", gen_focused_dense)
]
