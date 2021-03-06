# -*- coding: utf-8 -*-
"""DeepComedy.ipynb

Automatically generated by Colaboratory.

# DeepComedy: AI Generated Divine Comedy

Author: **Alessandro Pavesi, Federico Battistella**

This Notebook contains a **text generator RNN** that was trained on the **Divina Commedia** (the *Divine Comedy*) by **Dante Alighieri**. 

The structure is extremely complex: the poem is composed by three Cantiche, each Cantica has 33 Terzine, each Terzina is composed by three verses, each verse is composed of 11 syllables, and its rhymes follow an **A-B-A-B-C-B-C** structure.

The final goal of this project is to rewrite one Canto.
"""

# Commented out IPython magic to ensure Python compatibility.
import time
import re

import numpy as np
import pandas as pd

# %tensorflow_version 2.x
import tensorflow as tf
print(tf.__version__)

from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import Embedding, LSTM, Dense, Dropout, Attention, Flatten, Input, BatchNormalization
from tensorflow.keras.activations import elu, relu, softmax
from tensorflow.keras.metrics import categorical_accuracy, sparse_categorical_crossentropy, categorical_crossentropy

from matplotlib import pyplot as plt

"""# Preliminaries Steps

## Import and initial cleaning

We delete all the special character, numbers and brackets to keep a uniform version of the text.
We also remove the title of each Canto and each introductory text at his start.
Moreover we remove the last row of each Canto to have only terzine.
"""

# Read the Divina Commedia
with open( "DivinaCommedia.txt", 'r', encoding="utf8") as file:
    divina_commedia = file.read()

# Replace rare characters
divina_commedia = divina_commedia.replace("ä", "a")
divina_commedia = divina_commedia.replace("é", "è")
divina_commedia = divina_commedia.replace("ë", "è")
divina_commedia = divina_commedia.replace("Ë", "E")
divina_commedia = divina_commedia.replace("ï", "i")
divina_commedia = divina_commedia.replace("Ï", "I")
divina_commedia = divina_commedia.replace("ó", "ò")
divina_commedia = divina_commedia.replace("ö", "o")
divina_commedia = divina_commedia.replace("ü", "u")

divina_commedia = divina_commedia.replace("(", "-")
divina_commedia = divina_commedia.replace(")", "-")

divina_commedia = re.sub(r'[0-9]+', '', divina_commedia)
divina_commedia = re.sub(r'\[.*\r?\n', '', divina_commedia)
divina_commedia = re.sub(r'.*Canto.*\r?\n', '', divina_commedia)
divina_commedia = re.sub(r'.*?\n\n\n\n', "", divina_commedia)  # remove the last row of each Canto, it's alone and can ruin the generation on correct terzine

# divina_commedia = divina_commedia.replace(" \n", "\n")  # with this i lose the "terzina": results are not so exciting
#divina_commedia = divina_commedia.replace(" \n", "<eot>")  # end of terzina
#divina_commedia = divina_commedia.replace("\n", "<eor>")

print(divina_commedia[1:1000])

# Check lenght of text
print(len(divina_commedia))

"""## Vocabulary and Char2Idx

Creation of an vector of ids for each character in the Comedy's vocabulary
"""

# Store unique characters into a dict with numerical encoding
unique_chars = list(set(divina_commedia))
unique_chars.sort()  # to make sure you get the same encoding at each run

# Store them in a dict, associated with a numerical index
char2idx = { char[1]: char[0] for char in enumerate(unique_chars) }

"""## Encoding

Encode each character with a numerical vector of predefined length
"""

def numerical_encoding(text, char_dict):
    """ Text to list of chars, to np.array of numerical idx """
    chars_list = [ char for char in text ]
    chars_list = [ char_dict[char] for char in chars_list ]
    chars_list = np.array(chars_list)
    return chars_list

# Let's see what will look like
print("{}".format(divina_commedia[276:511]))
print("\nbecomes:")
print(numerical_encoding(divina_commedia[276:511], char2idx))

"""# Processing Data for DanteRNN

We need to generate the input for our RNN, the input sequence and an output sequence needs to be of equal length, in which each character is shifted left of one position.

For example, the first verse:

> Nel mezzo del cammin di nostra vita

would be translated in a train sequence as:

`Nel mezzo del cammin di nostra vit`

be associated with the target sequence:

`el mezzo del cammin di nostra vita`


Train and target sets are fundamentally the same matrix, with the train having the last row removed, and the target set having the first removed.
"""

# Apply it on the whole Comedy
encoded_text = numerical_encoding(divina_commedia, char2idx)

print(encoded_text[311:600])

def get_text_matrix(sequence, len_input):
    
    # create empty matrix
    X = np.empty((len(sequence)-len_input, len_input))
    
    # fill each row/time window from input sequence
    for i in range(X.shape[0]):
        X[i,:] = sequence[i : i+len_input]
        
    return X

len_text = 150
text_matrix = get_text_matrix(encoded_text, len_text)

print(text_matrix.shape)

print("100th train sequence:\n")
print(text_matrix[ 100, : ])
print("\n\n100th target sequence:\n")
print(text_matrix[ 101, : ])

"""# Custom Loss
Evaluate the structure of the rhymes, based on the real scheme with the aim to recreate the same exact rhyme structure of the Comedy
"""

from functools import reduce


def divide_versi(y):
  doppiozero = False

  y_divided = [[]]
  for ly in y:
    ly = int(ly)

    # I have to clean the list of punctuation marks,
    # in chartoidx means the numbers 1 to 10 inclusive.
    if ly in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
        continue
    else:
      # if it is zero it means \ n so I add a new line
      if ly is 0:
        if not doppiozero:
          y_divided.append([])
        doppiozero = True
        continue

      y_divided[-1].append(ly)
      doppiozero = False

  if y_divided is not []:
    if y[-1] != 0:
      # since the last line does not end with 0 it means that it is incomplete and I remove it
      y_divided.pop()

  # i need to re check because maybe i pop the only one
  if len(y_divided) != 0:
    if len(y_divided[0]) < 3:
      # if the first line is less than 4 I can't do anything about it so I delete it
      y_divided.pop(0)

  return y_divided

def rhymes_extractor(y_divided):
  # I extract the rhyme scheme from y
  rhymes = []
  for i in range(len(y_divided)):
    # with the end of the line (last two letters) I check if the other lines
    # end with the same letters
    vy = y_divided[i]

    last_word_1 = vy[-2:]

    # ABA BCB CDC

    # I have to check if line i rhymes with line i + 2
    if i+2 < len(y_divided):
      next_vy = y_divided[i+2]
      if last_word_1 == next_vy[-2:]:
        rhymes.append((i, i+2))
    
    if i+4 < len(y_divided):
      next_vy = y_divided[i+4]
      if last_word_1 == next_vy[-2:]:
        rhymes.append((i, i+4))

  return rhymes


def get_custom_loss(x_batch, y_batch):
  summed_custom_loss = 0

  # max number of rhymes (arbitrary choosen, it's an hyperparameter)
  max_rhymes = 4

  x_bin_tot = np.ones(shape=(len(x_batch), max_rhymes), dtype='float32')
  y_bin_tot = np.ones(shape=(len(x_batch), max_rhymes), dtype='float32')

  # iterate over each vector
  for v in range(len(x_batch)):
    x = x_batch[v]
    y = y_batch[v]

    # given that the model returns a matrix with shape (len_text, vocab_size) with the probability
    # for each of the vocab_size character i need to use a categorical to choose the best
    # then flatten the matrix into a list for evaluating
    predicted_text = list(tf.random.categorical(x, num_samples=1).numpy())
    x = np.concatenate(predicted_text).ravel().tolist()

    # dividing the vector in verse
    x_divided = divide_versi(x)
    y_divided = divide_versi(y)

    # extract the structure of the rhymes from generated and groud truth
    x_rhymes = rhymes_extractor(x_divided)
    y_rhymes = rhymes_extractor(y_divided)

    # it returns me a list with the number of rhyming lines
    # Example: [(1,3), (2,4)] means that lines 1 and 3 rhyme and that the
    # lines 2 and 4 as well

    # I create a vector of 1 for y because the rhymes are always there
    y_bin = np.ones(max_rhymes, dtype='float32')
    # I create a vector of 1 for the rhymes generated, I will put 0 if it rhyme
    # Is NOT present in dante, discount with a 0.5 since there is at least the rhyme
    x_bin = np.ones(max_rhymes, dtype='float32')

    if x_rhymes == []:
      x_bin = np.zeros(max_rhymes, dtype='float32')

    # if the generated rhyme is in Dante's original rhymes then I sign it as valid
    # I keep maximum max_ryhmes rhymes: I can because in 150-200 characters I don't have more than 5-6 lines
    # so in Dante I would have 2 rhymes, I exceed 2 to help the network create even wrong rhymes
    for i in range(max_rhymes+1):
      if i < len(y_rhymes):
        # check dante's rhyme with predicted rhymes, if it not exist set 0.0
        if y_rhymes[i] not in x_rhymes:
          x_bin[i] = 0.0
        # check predicted rhyme with Dante's rhymes, if not exist set 0.5 to increase number of rhymes produced
        if i < len(x_rhymes) and x_rhymes[i] not in y_rhymes:
          x_bin[i] = 0.5

    # concatenate vectors with rhyming encoding
    x_bin_tot[v] = x_bin
    y_bin_tot[v] = y_bin
  
  # MSE over vector
  r = tf.keras.losses.mean_squared_error(y_bin_tot, x_bin_tot)

  return np.mean(r)

"""# Training Model

At this point, we can specify the RNN architecture with all its hyperparameters.

## Parameters
"""

# size of vocabulary
vocab_size = len(char2idx)

# size of mini batches during training
batch_size = 200  # 100

# size of training subset at each epoch
subset_size = batch_size * 100

# vector size of char embeddings
embedding_size = 200  # 200 250

lstm_unit_1 = 2048
lstm_unit_2 = 4096

# debug variables
debug_model = False
if debug_model:
  lstm_unit_1 = 1024
  lstm_unit_2 = 2048

dropout_value = 0.5
hidden_size = 256  # for Dense() layers 250

n_epochs = 75
learning_rate = 0.001  # 0.0001

"""## Metrics"""

def perplexity_metric(loss):
    """Calculates perplexity metric = 2^(entropy) or e^(entropy)"""
    return tf.exp(loss)

"""## Custom learning rate"""

class CustomSchedule(tf.keras.optimizers.schedules.LearningRateSchedule):
  def __init__(self, d_model, warmup_steps=10):
    super(CustomSchedule, self).__init__()

    self.d_model = d_model
    self.d_model = tf.cast(self.d_model, tf.float32)

    self.warmup_steps = warmup_steps

  def __call__(self, step):
    arg1 = tf.math.rsqrt(step ** 1.5)
    arg2 = step * ((self.warmup_steps+10) ** -1.3)
    lr = tf.math.rsqrt(self.d_model) * tf.math.minimum(arg1, arg2)
    return lr

d_model = 500
learning_rate_custom_1 = CustomSchedule(d_model)
plt.plot(learning_rate_custom_1(tf.range(n_epochs, dtype=tf.float32)))
plt.ylabel("Learning Rate")
plt.xlabel("Train Step")


learning_rate_custom_2 = tf.optimizers.schedules.ExponentialDecay(
    initial_learning_rate=0.001,
    decay_steps=35,
    decay_rate=0.90,
    staircase=True)
plt.plot(learning_rate_custom_2(tf.range(n_epochs, dtype=tf.float32)))
plt.ylabel("Learning Rate")
plt.xlabel("Train Step")

"""Optimizer selected: Adamax"""

optimizer = tf.keras.optimizers.Adamax(learning_rate=learning_rate_custom_2)

"""## Architecture"""

# Input Layer
X = Input(shape=(None, ), batch_size=batch_size)

# Embedding Layer
embedded = Embedding(vocab_size, embedding_size, 
                     batch_input_shape=(batch_size, None), 
                     embeddings_regularizer=tf.keras.regularizers.L2()
                     )(X)

# Dense layer
embedded = Dense(embedding_size, relu)(embedded)

# First LSTM
encoder_output, hidden_state, cell_state = LSTM(units=lstm_unit_1,return_sequences=True,return_state=True)(embedded)
encoder_output = BatchNormalization()(encoder_output)

# Dropout
encoder_output = Dropout(dropout_value)(encoder_output)
# Dense layer
encoder_output = Dense(embedding_size, activation='relu')(encoder_output)

# Dropout
encoder_output = Dropout(dropout_value)(encoder_output)

# Concat of first LSTM hidden state
initial_state_double = [tf.concat([hidden_state, hidden_state], 1), tf.concat([hidden_state, hidden_state], 1)]

# Second LSTM
encoder_output, hidden_state, cell_state = LSTM(units=lstm_unit_2,
                                                return_sequences=True, 
                                                return_state=True)(encoder_output, initial_state=initial_state_double) 
encoder_output = BatchNormalization()(encoder_output)

# Dropout
encoder_output = Dropout(dropout_value)(encoder_output)
# Dense layer
encoder_output = Dense(hidden_size, activation='relu')(encoder_output)

# Dropout
encoder_output = Dropout(dropout_value)(encoder_output)

# Prediction Layer
Y = Dense(units=vocab_size)(encoder_output)

# Compile model
model = Model(inputs=X, outputs=Y)
model.compile(loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits = True), optimizer=optimizer)
print(model.summary())

"""## Training"""

min_custom_loss = 1.0  # max value for the custom loss
min_custom_epoch = 0  # epoch of minimum custom loss

def train_on_batch(x, y, min_custom_loss):
    with tf.GradientTape() as tape:
        # returns a tensor with shape (batch_size, len_text)
        y_predicted = model(x)

        scce = tf.keras.losses.sparse_categorical_crossentropy(y, y_predicted, from_logits = True)
        # we cant return a tensor with that shape so we return a float that are summed
        custom = get_custom_loss(y_predicted, y)

        current_loss = tf.reduce_mean(scce + custom)

    gradients = tape.gradient(current_loss, model.trainable_variables)
    optimizer.apply_gradients(zip(gradients, model.trainable_variables))

    perp = perplexity_metric(tf.reduce_mean(scce))

    # checking for the best model using custom loss
    # needed to do here because here we can save the model
    if custom < min_custom_loss:
      min_custom_loss = custom
      model.save("best_model.h5", overwrite=True)
    return current_loss, scce, custom, perp, min_custom_loss


loss_history = []
custom_loss_history = []
perplexity_history = []


for epoch in range(n_epochs):
    
    start = time.time()
    
    # Take subsets of train and target
    sample = np.random.randint(0, text_matrix.shape[0]-1, subset_size)
    sample_train = text_matrix[ sample , : ]
    sample_target = text_matrix[ sample+1 , : ]

    for iteration in range(sample_train.shape[0] // batch_size):
        take = iteration * batch_size
        x = sample_train[ take:take+batch_size , : ]

        y = sample_target[ take:take+batch_size , : ]

        current_loss, scce, custom, perplexity, new_min_custom_loss = train_on_batch(x, y, min_custom_loss)

        # save infos about the new min_custom_loss
        if new_min_custom_loss < min_custom_loss:
          min_custom_loss = new_min_custom_loss
          min_custom_epoch = epoch

        loss_history.append(current_loss)
        custom_loss_history.append(custom)
        perplexity_history.append(perplexity)
    
    print("{}.  \t  Total-Loss: {}  \t  Custom-Loss: {}  \t Perplexity: {}  \t Time: {} sec/epoch".format(
        epoch+1, current_loss.numpy(), custom, perplexity, round(time.time()-start, 2)))

model.save(F"/content/gdrive/My Drive/DeepComedyModels/deep_comedy_custom_loss_01_62char.h5")

"""## Graphs"""

fig, ax1 = plt.subplots()

color = 'tab:red'
ax1.set_xlabel('Iterations')
ax1.set_ylabel('Total Loss', color=color)
ax1.plot(loss_history, color=color)
ax1.tick_params(axis='y', labelcolor=color)

ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis

color = 'tab:blue'
ax2.set_ylabel('Custom Loss', color=color)  # we already handled the x-label with ax1
ax2.plot(custom_loss_history, color=color)
ax2.tick_params(axis='y', labelcolor=color)

fig.tight_layout()  # otherwise the right y-label is slightly clipped
plt.show()
print("The min custom loss is at iteration: {}".format(min_custom_epoch*1000))

plt.plot(perplexity_history)
plt.xlabel("Iterations")
plt.ylabel("Perplexity")
plt.show()

"""# Generative Model

At this point, let's check how the model generates text. In order to do it, we must make some changes to my RNN architecture above.

First, we must change the fixed batch size. After training, we want to feed just one sentence into my Network to make it continue the character sequence. We will feed a string into the model, make it predict the next character, update the input sequence, and repeat the process until a long generated text is obtained. Because of this, the succession of input sequences is now different from training session, in which portions of text were sampled randomly. we now have to set `stateufl = True` in the `LSTM()` layer, so that each LSTM cell will keep in memory the internal state from the previous sequence. With this we make the model remember better sequential information while generating text.

We will instantiate a new `generator` RNN with these new features, and transfer the trained weights of my `RNN` into it.

## Architecture
"""

# Input Layer
X = Input(shape=(None, ), batch_size=1)
embedded = Embedding(vocab_size, embedding_size)(X)
embedded = Dense(embedding_size, relu)(embedded)

encoder_output, hidden_state, cell_state = LSTM(units=lstm_unit_1,
                                                         return_sequences=True,
                                                         return_state=True,
                                              stateful=True)(embedded)
encoder_output = BatchNormalization()(encoder_output)
encoder_output = Dropout(dropout_value)(encoder_output)
encoder_output = Dense(embedding_size, activation='relu')(encoder_output)

initial_state_double = [tf.concat([hidden_state, hidden_state], 1), tf.concat([hidden_state, hidden_state], 1)]

encoder_output, hidden_state, cell_state = LSTM(units=lstm_unit_2,
                                                         return_sequences=True,
                                                         return_state=True,
                                                stateful=True)(encoder_output, initial_state=initial_state_double)

encoder_output = BatchNormalization()(encoder_output)
encoder_output = Dropout(dropout_value)(encoder_output)
encoder_output = Dense(hidden_size, activation='relu')(encoder_output)
encoder_output = Dropout(dropout_value)(encoder_output)

Y = Dense(units=vocab_size)(encoder_output)

# Compile model
generator = Model(inputs=X, outputs=Y)
generator.compile(loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits = True), optimizer=optimizer)
print(generator.summary())

"""## Loading weights"""

# Import trained weights from RNN to generator
load_file = False
if load_file:
  generator.load_weights("best_model.h5")
else:
  generator.set_weights(model.get_weights())

"""## Generating methods"""

def generate_text(start_string, model, num_generate = 1000, temperature = 1.0):
    
    # Vectorize input string
    input_eval = [char2idx[s] for s in start_string]  
    input_eval = tf.expand_dims(input_eval, 0)
    
    text_generated = [] # List to append predicted chars 
    predicted_ids = []
    
    idx2char = { v: k for k, v in char2idx.items() }  # invert char-index mapping
    
    model.reset_states()
    
    for i in range(num_generate):
        predictions = model(input_eval)
        predictions = tf.squeeze(predictions, 0)
        
        # sample next char based on distribution and temperature
        predictions = predictions / temperature
        predicted_id = tf.random.categorical(predictions, num_samples=1)[-1,0].numpy()
        
        input_eval = tf.expand_dims([predicted_id], 0)  # one letter input
        
        # build the input for the next iteration, based on the last 5 characters generated
        # become like a poetry!
        #predicted_ids.append(predicted_id)
        #if len(predicted_ids) > 5:
        #  predicted_ids = predicted_ids[1:]
        #input_eval = tf.expand_dims(predicted_ids, 0)

        text_generated.append(idx2char[predicted_id])
        
    return (start_string + ''.join(text_generated))

"""## Text generation"""

# Let's feed the first lines:
start_string = """
Nel mezzo del cammin di nostra vita
mi ritrovai per una selva oscura,
chè la diritta via era smarrita.

"""

for t in [0.1, 0.2, 0.3, 0.5, 1.0]:
    print("####### TEXT GENERATION - temperature = {}\n".format(t))
    print(generate_text(start_string, generator, num_generate = 1000, temperature = t))
    print("\n\n\n")

# Exam mode for 1 Canto so 33 terzine. 4000 characters to write
start_inferno = """
Nel mezzo del cammin di nostra vita
mi ritrovai per una selva oscura,
chè la diritta via era smarrita.

"""

start_purgatorio = """
Per correr miglior acque alza le vele
omai la navicella del mio ingegno,
che lascia dietro a se mar si crudele;

"""

start_paradiso = """
La gloria di colui che tutto move
per l'universo penetra, e risplende
in una parte più e meno altrove.

"""

start_new = """
"""
start = time.time()
generated = generate_text(start_inferno, generator, num_generate = 7000, temperature = 0.1)
print("Time to generate {} characters: {} sec".format(7000, round(time.time()-start, 2)))

print(generated)

"""## Save generated Canto to file for Plagiarism Test and Metrics"""

with open("generated.txt", "w+") as text_file:
    text_file.write(generated)

"""# Plagiarism Test

Include the file **ngrams_plagiarism.py** downloaded from Virtuale

This mehod needs two file, we called it generated.txt (the same for the Metrics) and Inferno.txt (the first Canto of the Inferno).
"""

from ngrams_plagiarism import ngrams_plagiarism

gen = open('generated.txt').read()
truth = open('Inferno.txt').read()
ngrams_plagiarism(gen, truth)

"""# Metrics

Include the content of the folder **Deep Comedy Metrics** downloaded from Virtuale.

This method needs one file:
*   generated.txt: the file generated by the network

with UTF-8 Encoding!



"""

!python3 main.py

"""# Custom loss used for debug and explaination"""

#@title
#@DEBUG CUSTOM LOSS

x = [[49, 46, 36, 44, 49, 32, 48, 36,  1, 45,  1, 35, 51, 36,  1, 45,  1, 50,
 48, 36,  1, 46, 36, 48,  1, 49, 36, 30,  5,  0, 44, 45, 44,  1, 42, 32,
  1, 37, 45, 48, 50, 51, 44, 32,  1, 35, 40,  1, 46, 48, 40, 43, 32,  1,
 52, 32, 34, 32, 44, 50, 36,  5,  0, 44, 45, 44,  1, 35, 36, 34, 40, 43,
 32, 49,  5,  1, 47, 51, 32, 36,  1, 49, 51, 44, 50,  1, 46, 32, 51, 46,
 36, 48, 51, 43,  1, 14, 36, 40,  5,  1,  0,  0, 32, 35, 35, 40, 43, 32,
 44, 35, 60,  5,  1, 43, 32,  1, 34, 45, 44, 50, 48, 45,  1, 32, 42,  1,
 43, 45, 44, 35, 45,  1, 36, 48, 48, 32, 44, 50, 36,  0, 42, 40, 34, 36,
 44, 55, 32,  1, 35, 40], 
 [42,  1, 34, 45, 44, 49, 40, 38, 42, 40, 45,  1, 44, 36, 42,  1, 47, 51,
 32, 42, 36,  1, 45, 38, 44, 36,  1, 32, 49, 46, 36, 50, 50, 45,  0, 34,
 48, 36, 32, 50, 45,  1, 58,  1, 52, 40, 44, 50, 45,  1, 46, 48, 40, 32,
  1, 34, 39, 36,  1, 52, 32, 35, 32,  1, 32, 42,  1, 37, 45, 44, 35, 45,
  5,  1,  0,  0, 46, 36, 48, 60,  1, 34, 39, 36,  1, 32, 44, 35, 32, 49,
 49, 36,  1, 52, 36, 48,  4,  1, 42, 45,  1, 49, 51, 45,  1, 35, 40, 42,
 36, 50, 50, 45,  0, 42, 32,  1, 49, 46, 45, 49, 32,  1, 35, 40,  1, 34,
 45, 42, 51, 40,  1, 34, 39,  4, 32, 35,  1, 32, 42, 50, 36,  1, 38, 48,
 40, 35, 32,  0, 35, 40,]]
y = [[46, 36, 44, 49, 32, 48, 36,  1, 45,  1, 35, 51, 36,  1, 45,  1, 50, 48,
 36,  1, 46, 36, 48,  1, 49, 36, 40,  5,  0, 44, 45, 44,  1, 42, 32,  1,
 37, 45, 48, 50, 51, 44, 32,  1, 35, 40,  1, 46, 48, 40, 43, 32,  1, 52,
 32, 34, 32, 44, 50, 36,  5,  0, 44, 45, 44,  1, 35, 36, 34, 40, 43, 32,
 49,  5,  1, 47, 51, 32, 36,  1, 49, 51, 44, 50,  1, 46, 32, 51, 46, 36,
 48, 51, 43,  1, 14, 36, 40,  5,  1,  0,  0, 32, 35, 35, 40, 43, 32, 44,
 35, 60,  5,  1, 43, 32,  1, 34, 45, 44, 50, 48, 45,  1, 32, 42,  1, 43,
 45, 44, 35, 45,  1, 36, 48, 48, 32, 44, 50, 36,  0, 42, 40, 34, 36, 44,
 55, 32,  1, 35, 40,  1], [ 1, 34, 45, 44, 49, 40, 38, 42, 40, 45,  1, 44, 36, 42,  1, 47, 51, 32,
 42, 36,  1, 45, 38, 44, 36,  1, 32, 49, 46, 36, 50, 50, 45,  0, 34, 48,
 36, 32, 50, 45,  1, 58,  1, 52, 40, 44, 50, 45,  1, 46, 48, 40, 32,  1,
 34, 39, 36,  1, 52, 32, 35, 32,  1, 32, 42,  1, 37, 45, 44, 35, 45,  5,
  1,  0,  0, 46, 36, 48, 60,  1, 34, 39, 36,  1, 32, 44, 35, 32, 49, 49,
 36,  1, 52, 36, 48,  4,  1, 42, 45,  1, 49, 51, 45,  1, 35, 40, 42, 36,
 50, 50, 45,  0, 42, 32,  1, 49, 46, 45, 49, 32,  1, 35, 40,  1, 34, 45,
 42, 51, 40,  1, 34, 39,  4, 32, 35,  1, 32, 42, 50, 36,  1, 38, 48, 40,
 35, 32,  0, 35, 40, 49,] ]

'''
EXPERIMENT
CUSTOM LOSS
'''
from functools import reduce


def divide_versi(y):
  doppiozero = False

  y_divided = [[]]
  for ly in y:
    ly = int(ly)

    # devo pulire la lista dai segni di punteggiatura, 
    # in chartoidx significa i numeri da 1 a 10 compresi.
    if ly in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:  # con i Tensor non funziona
    # if ly is 1 or ly is 2 or ly is 3 or ly is 4 or ly is 5 or ly is 6 or ly is 7 \
    #     or ly is 8 or ly is 9 or ly is 10:
        continue
    else:
      # se è zero vuol dire \n quindi aggiungo una nuova riga
      if ly is 0:
        if not doppiozero:
          y_divided.append([])
        doppiozero = True
        continue

      y_divided[-1].append(ly)
      doppiozero = False

  if y_divided is not []:
    if y[-1] != 0:
      # dato che l'ultima riga non finisce con 0 vuol dire che è incompleta e la rimuovo
      y_divided.pop()

  # i need to re check because maybe i pop the only one
  if len(y_divided) != 0:
    if len(y_divided[0]) < 3:
      # se la prima riga è minore di 4 non posso farci nulla quindi la elimino
      y_divided.pop(0)

  return y_divided

def rhymes_extractor(y_divided):
  # estraggo lo schema di rime da y
  rhymes = []
  for i in range(len(y_divided)):
    # con la fine del verso (ultime due lettere) controllo se le altre righe 
    # finiscono con le stesse lettere
    vy = y_divided[i]

    last_word_1 = vy[-2:]

    # ABA BCB CDC

    # devo controllare se la riga i fa rima con la riga i+2 
    if i+2 < len(y_divided):
      next_vy = y_divided[i+2]
      # print(vy[-2:])
      # print(next_vy[-2:])
      if last_word_1 == next_vy[-2:]:
        rhymes.append((i, i+2))
    
    if i+4 < len(y_divided):
      # print(vy[-2:])
      # print(next_vy[-2:])
      next_vy = y_divided[i+4]
      if last_word_1 == next_vy[-2:]:
        rhymes.append((i, i+4))

  # print(rhymes)
  return rhymes


def get_custom_loss(x_batch, y_batch):
  summed_custom_loss = 0
  # x_batch ha lo shape (200, 200) quindi ho 200 vettori con 200 lettere ognuno
  # le 200 lettere sono le feature

  # max numero di rime possibili (arbitrario)
  max_rhymes = 4

  print("Shape di x_batch e y_batch")
  print((len(x_batch), len(x_batch[0])))
  print((len(y_batch), len(y_batch[0])))

  x_bin_tot = np.ones(shape=(len(x_batch), max_rhymes), dtype='float32')
  y_bin_tot = np.ones(shape=(len(x_batch), max_rhymes), dtype='float32')

  # scorro i 200 vettori
  # for (x, y) in zip(x_batch, y_batch):  # Non funziona con i tensori
  for v in range(len(x_batch)):
    x = x_batch[v]
    y = y_batch[v]

    # given that the model returns a matrix with shape (150, 62) with the probability
    # for each of the 62 character i need to use a categorical to choose the best
    # then flatten the matrix into a list for evaluating
    #predicted_text = list(tf.random.categorical(x, num_samples=1).numpy())
    #x = np.concatenate(predicted_text).ravel().tolist()

    # dividio il vettore in versi utili
    x_divided = divide_versi(x)
    y_divided = divide_versi(y)

    print("Divisione in versi di x_batch e y_batch")
    print(x_divided)
    print(y_divided)

    # assicuro che il numero di versi siano uguali
    # !!! non posso perchè il generato può avere errori e quindi, per esempio,
    # avere più o meno versi
    # assert len(x_divided) == len(y_divided)

    # estraggo lo schema di rime
    x_rhymes = rhymes_extractor(x_divided)
    y_rhymes = rhymes_extractor(y_divided)

    print("Rime dei versi di x_batch e y_batch")
    print(x_rhymes)
    print(y_rhymes)

    # mi ritorna una lista con il numero delle righe che fanno rima
    # Esempio: [(1,3), (2,4)] significa che le righe 1 e 3 fanno rima e che le 
    # righe 2 e 4 pure 
    # TODO se avessimo due terzine intere si potrebbe valutare rime a 3 righe [aBaBcB]

    # creo un vettore di 1 per la y perchè le rime ci sono sempre
    y_bin = np.ones(max_rhymes, dtype='float32')
    # creo un vettore di 1 per le rime generate, metterò 0 se la rima 
    # NON è presente in dante, abbuono con uno 0.5 visto che c'è la rima almeno
    x_bin = np.ones(max_rhymes, dtype='float32')

    if x_rhymes == []:
      x_bin = np.zeros(max_rhymes, dtype='float32')

    # se la rima generata è nelle rime originali di Dante allora la segno come valida
    # tengo massimo max_ryhmes rime: posso perchè in 150-200 caratteri non ho più di 5-6 righe
    # quindi in Dante avrei 2 rime, eccedo di 2 per aiutare la rete a creare rime anche sbagliate
    for i in range(max_rhymes+1):
      if i < len(y_rhymes):
        if y_rhymes[i] not in x_rhymes:
          x_bin[i] = 0.0
        if i < len(x_rhymes) and x_rhymes[i] not in y_rhymes:
          x_bin[i] = 0.5

    print("Vettore che rappresenta il confronto delle rime tra il generato e Dante dei versi di x_batch e y_batch \n y è sempre 1 mentre il generato ha 1 se la rima c'è in dante o 0.5 se non c'è ")
    print(x_bin)
    print(y_bin)
      
    # concateno i vettori con l'encoding delle rime
    x_bin_tot[v] = x_bin
    y_bin_tot[v] = y_bin

  print("Matrice dei vettori su cui eseguo la MSE: (x,y)")
  print(x_bin_tot)
  print(y_bin_tot)
  r = tf.keras.losses.mean_squared_error(y_bin_tot, x_bin_tot)

  print("Risultato della MSE:")
  print(r)

  print("Loss finale fatta con la media della MSE")
  print(np.mean(r))
  # MSE sui vettori
  return np.mean(r)


custom_loss = get_custom_loss(x,y)