# -*- coding: utf-8 -*-
"""DanteRNNNEW.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1ubV-fLpQqNrjIqzvEfmNocycRAorYm19

Recursive Neural Network(RNN) for generating the Divina Commedia of Dante Alighieri.
"""

# Commented out IPython magic to ensure Python compatibility.
import numpy as np
import pandas as pd
from pathlib import Path

# %tensorflow_version 2.x
import tensorflow as tf
print(tf.__version__)

from keras.callbacks import ModelCheckpoint,  CSVLogger
from keras.preprocessing.text import Tokenizer
from keras.utils import np_utils
from matplotlib import pyplot as plt
from model import BasicDanteRNN


# Settings

# Percent of samples to use for training, might be necessary if you're running out of memory
sample_size = 1

# The latent dimension of the LSTM
latent_dim = 2048

# Number of epochs to train for
epochs = 20

# path of the data
data_path = 'data/DivinaCommedia.csv'

name = 'all_data_test_2'
output_dir = Path('output_%s' % name)
try:
  output_dir.mkdir()
except FileExistsError:
  pass

df = pd.read_csv(str(data_path))
df = df.sample(frac=sample_size)


max_line_length = int(max([df['%s' % i].astype(str).str.len().quantile(.99) for i in range(3)]))

df = df[
    (df['0'].astype(str).str.len() <= max_line_length) & 
    (df['1'].astype(str).str.len() <= max_line_length) & 
    (df['2'].astype(str).str.len() <= max_line_length)
].copy()

# preprocessing data
# Pad the lines to the max line length with new lines
for i in range(3):
    # For input, duplicate the first character
    # TODO - Why?
    df['%s_in' % i] = (df[str(i)].str[0] + df[str(i)]).str.pad(max_line_length+2, 'right', '\n')
    
    # 
    #df['%s_out' % i] = df[str(i)].str.pad(max_line_len, 'right', '\n') + ('\n' if i == 2 else df[str(i+1)].str[0])
    
    # TODO - trying to add the next line's first character before the line breaks
    if i == 2: # If it's the last line
        df['%s_out' % i] = df[str(i)].str.pad(max_line_length+2, 'right', '\n')
    else: 
        # If it's the first or second line, add the first character of the next line to the end of this line.
        # This helps with training so that the next RNN has a better chance of getting the first character right.
        df['%s_out' % i] = (df[str(i)] + '\n' + df[str(i+1)].str[0]).str.pad(max_line_length+2, 'right', '\n')
    
max_line_length += 2

inputs = df[['0_in', '1_in', '2_in']].values


tokenizer = Tokenizer(filters='', char_level=True)
tokenizer.fit_on_texts(inputs.flatten())
n_tokens = len(tokenizer.word_counts) + 1


print(df)

# X is the input for each line in sequences of one-hot-encoded values
X = np_utils.to_categorical([
  tokenizer.texts_to_sequences(inputs[:,i]) for i in range(3)
  ], num_classes=n_tokens)

outputs = df[['0_out', '1_out', '2_out']].values

# Y is the output for each line in sequences of one-hot-encoded values
Y = np_utils.to_categorical([
    tokenizer.texts_to_sequences(outputs[:,i]) for i in range(3)
], num_classes=n_tokens)

# X_syllables is the count of syllables for each line
X_syllables = df[['0_syllables', '1_syllables', '2_syllables']].values

print(max_line_length)

# The latent dimension of the LSTM
latent_dim = 2048
model = BasicDanteRNN(latent_dim, n_tokens)

model.compile(optimizer='rmsprop', loss='categorical_crossentropy')

filepath = str(output_dir / ("%s-{epoch:02d}-{loss:.2f}-{val_loss:.2f}.hdf5" % latent_dim))
checkpoint = ModelCheckpoint(filepath, monitor='loss', verbose=1, save_best_only=True, mode='min')

csv_logger = CSVLogger(str(output_dir / 'training_log.csv'), append=True, separator=',')

callbacks_list = [checkpoint, csv_logger]


#model.build(((None, 2048)))
#model.summary()

#print(model.output)

# l'input X[0] contiene 46 vettori con ognuno 41 valori
# 46 è il numero di caratteri massimo per riga
# 41 è il numero di caratteri possibili per ogni carattare

model.fit([
    X[0], X_syllables[:,0],
    X[1], X_syllables[:,1], 
    X[2], X_syllables[:,2]
], [Y[0], Y[1], Y[2]], batch_size=64, epochs=10, validation_split=.1, callbacks=callbacks_list)

def generate_text(model, start_string):
  # Evaluation step (generating text using the learned model)

  # Number of characters to generate
  num_generate = 1000

  first_char = chr(int(np.random.randint(ord('a'), ord('z')+1)))
  print(tokenizer.texts_to_sequences(first_char))
  print(tokenizer.texts_to_sequences(first_char)[0])
  # Converting our start string to numbers (vectorizing)
  input_eval = tokenizer.texts_to_sequences(first_char)[0]
  input_eval = tf.expand_dims(input_eval, 0)

  # Empty string to store our results
  text_generated = []

  # Low temperatures results in more predictable text.
  # Higher temperatures results in more surprising text.
  # Experiment to find the best setting.
  temperature = 1.0

  # Here batch size == 1
  model.reset_states()
  for i in range(num_generate):
    predictions = model(input_eval)
    # remove the batch dimension
    predictions = tf.squeeze(predictions, 0)

    # using a categorical distribution to predict the character returned by the model
    predictions = predictions / temperature
    predicted_id = tf.random.categorical(predictions, num_samples=1)[-1,0].numpy()

    # We pass the predicted character as the next input to the model
    # along with the previous hidden state
    input_eval = tf.expand_dims([predicted_id], 0)

    text_generated.append(tokenizer.sequences_to_texts([
                predicted_id
            ])[0].strip()[1:].replace(
                '   ', '\n'
            ).replace(' ', '').replace('\n', ' '))

  return (start_string + ''.join(text_generated))

print(generate_text(model, start_string=u"INFERNO: "))

# Create a generator using the training model as the template

# generator = Generator2(lstm, lines, tokenizer, n_tokens, max_line_length)
#
# for i in range(50):
#     generator.generate_haiku([11, 11, 11])
#     print()
#
# for i in range(50):
#     generator.generate_haiku(temperature=.3)
#     print()
#
# for i in range(50):
#     generator.generate_haiku(temperature=.5)
#     print()
#
# for i in range(50):
#     generator.generate_haiku(temperature=.75)
#     print()
#
# for i in range(50):
#     generator.generate_haiku(temperature=1)
#     print()